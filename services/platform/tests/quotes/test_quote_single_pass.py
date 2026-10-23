"""Small differential tests against the frozen PR52 reconstruction and formatters."""

from copy import deepcopy
from dataclasses import asdict
from unittest.mock import patch

import pytest
import quote_reconstruction_pr52_oracle as oracle
from cycling_workshop.quotes import reconstruction
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_reconstruction import records as records
from test_quote_repository import database as database


def quote_only_oracle_adapter(module):
    """Bridge repository keywords without extending the frozen oracle's domain."""

    def adapted(
        lineage,
        revisions,
        lines,
        targets,
        decisions,
        operations,
        outboxes,
        *,
        order_events,
        changes,
        order_outboxes,
        checkpoint,
    ):
        checkpoint()
        if order_events or changes or order_outboxes:
            raise AssertionError("frozen quote-only oracle cannot validate linked source rows")
        if any(
            value is not None
            for operation in operations
            for value in (
                operation.order_event_id,
                operation.resulting_order_version,
                operation.change_cursor,
                operation.order_outbox_id,
                operation.order_effect_version,
            )
        ):
            raise AssertionError("frozen quote-only oracle cannot validate order effects")
        result = module._reconstruct_with_bytes(
            lineage, revisions, lines, targets, decisions, operations, outboxes
        )
        checkpoint()
        return result

    return adapted


def equivalent(rows):
    from cycling_workshop.quotes.storage import canonical_bytes

    old_records, new_records = [], []
    old_formatter = oracle.logical_record
    new_formatter = reconstruction._logical_record

    def old_record(*args):
        result = old_formatter(*args)
        old_records.append(canonical_bytes(result))
        return result

    def new_record(*args):
        result = new_formatter(*args)
        new_records.append(canonical_bytes(result))
        return result

    with patch.object(oracle, "logical_record", old_record):
        old, old_bytes = oracle._reconstruct_with_bytes(*deepcopy(rows))
    with patch.object(reconstruction, "_logical_record", new_record):
        new, new_bytes = reconstruction._reconstruct_with_bytes(*deepcopy(rows))
    assert old_records == new_records
    assert len(new_records) == len(rows[5])
    assert old.ledger == new.ledger
    assert [asdict(item) | {"order_effects": None} for item in old.receipts] == [
        asdict(item) for item in new.receipts
    ]
    assert old_bytes == new_bytes
    return new


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_no_complete_prefix_advance_and_exact_old_result(records, monkeypatch):
    calls = []
    original = reconstruction.advance

    def counted(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(reconstruction, "advance", counted)
    equivalent(records)
    assert calls == []


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize(
    "index,field,value",
    [
        (0, "head_version", True),
        (1, "total_minor", 1),
        (2, "description", "altered"),
        (3, "target_line_id", "bad"),
        (4, "sequence", 2),
        (5, "ordinal", 2),
        (6, "event_type", "bad"),
    ],
)
def test_corruption_rejection_matches_frozen_oracle(records, index, field, value):
    row = records[0] if index == 0 else records[index][0]
    setattr(row, field, value)
    for module in (oracle, reconstruction):
        with pytest.raises(module.QuoteIntegrityError, match=r"^stored quote history is invalid$"):
            module.reconstruct(*deepcopy(records))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_constant_final_constructors_and_every_operation_checked(records, monkeypatch):
    from collections import Counter

    from cycling_workshop.quotes import decisions, history

    calls = Counter()
    for module, name, label in [
        (history.QuoteHistory, "__post_init__", "history"),
        (decisions.QuoteDecisionLedger, "__post_init__", "ledger"),
        (reconstruction, "command_from_proof", "proof"),
        (reconstruction, "_event_payload", "event"),
        (reconstruction, "_logical_record", "logical"),
        (reconstruction, "_admit", "step_admit"),
        (decisions, "_admit", "final_admit"),
    ]:
        original = getattr(module, name)

        def counted(*args, _original=original, _label=label, **kwargs):
            calls[_label] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)
    payload_ids = {id(row.payload) for row in records[6]}
    canonical = reconstruction.canonical_bytes

    def counted_bytes(value):
        if id(value) in payload_ids:
            calls["outbox"] += 1
        return canonical(value)

    monkeypatch.setattr(reconstruction, "canonical_bytes", counted_bytes)
    reconstruction.reconstruct(*records)
    assert calls == dict(
        history=3, ledger=2, proof=3, event=3, logical=3, step_admit=1, final_admit=2, outbox=3
    )


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_head_id", "01900000-0000-7000-8000-000000000099"),
        ("expected_head_version", 2),
        ("expected_decision_sequence", 0),
    ],
)
def test_later_revision_prefix_preconditions_cannot_be_repaired(records, field, value):
    proof = deepcopy(records[5][2].proof)
    proof[field] = value
    records[5][2].proof = proof
    for module in (oracle, reconstruction):
        with pytest.raises(module.QuoteIntegrityError):
            module.reconstruct(*deepcopy(records))


def collect_rows(session):
    from cycling_workshop.events.models import OutboxRecord
    from cycling_workshop.quotes.models import (
        QuoteDecisionRecord,
        QuoteLineageRecord,
        QuoteLineRecord,
        QuoteLineTargetRecord,
        QuoteOperationRecord,
        QuoteRevisionRecord,
    )
    from sqlalchemy import select

    return [
        session.scalar(select(QuoteLineageRecord)),
        list(session.scalars(select(QuoteRevisionRecord).order_by(QuoteRevisionRecord.version))),
        list(session.scalars(select(QuoteLineRecord))),
        list(session.scalars(select(QuoteLineTargetRecord))),
        list(session.scalars(select(QuoteDecisionRecord))),
        list(session.scalars(select(QuoteOperationRecord).order_by(QuoteOperationRecord.ordinal))),
        list(session.scalars(select(OutboxRecord))),
    ]


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_correction_updates_latest_customer_time_and_withdrawal_preserves_it(database):
    from dataclasses import replace
    from datetime import timedelta

    from cycling_workshop.quotes.repository import QuoteRepository
    from sqlalchemy.orm import Session
    from test_quote_repository import admitted, creation, decision
    from test_quote_storage import NOW, uid

    evidence = decision().command.evidence
    commands = [
        decision(evidence=replace(evidence, decided_at=NOW + timedelta(seconds=4))),
        decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Corrección café 🚲",
            evidence=replace(evidence, decided_at=NOW + timedelta(seconds=2)),
        ),
        decision(
            decision_id=uid(102),
            mode="customer_change",
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Cambio",
            evidence=replace(evidence, decided_at=NOW + timedelta(seconds=3)),
        ),
        decision(
            decision_id=uid(103),
            mode="withdraw_record",
            expected_decision_sequence=3,
            supersedes_entry_id=uid(102),
            reason="Retiro",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
        ),
        decision(
            decision_id=uid(104),
            mode="customer_change",
            expected_decision_sequence=4,
            supersedes_entry_id=uid(103),
            reason="Cambio tras retiro",
            evidence=replace(evidence, decided_at=NOW + timedelta(seconds=3)),
        ),
    ]
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        for ordinal, command in enumerate(commands, 5):
            repo.apply(command, recorded_at=NOW + timedelta(seconds=ordinal))
        rows = collect_rows(session)
        equivalent(rows)
        # A customer change older than the last non-null evidence must still fail
        # after a withdrawal. Final row/projection plausibility cannot repair it.
        proof = deepcopy(rows[5][-1].proof)
        proof["command"]["evidence"]["decided_at"] = (
            (NOW + timedelta(seconds=2)).isoformat(timespec="microseconds").replace("+00:00", "Z")
        )
        rows[5][-1].proof = proof
        for module in (oracle, reconstruction):
            with pytest.raises(module.QuoteIntegrityError):
                module.reconstruct(*deepcopy(rows))
        session.rollback()


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("budget", ["MAX_HISTORY_BYTES", "MAX_RECORD_BYTES"])
def test_exact_and_one_byte_over_limits_match_old_path(records, monkeypatch, budget):
    from cycling_workshop.quotes import storage

    snapshot, exact_history = oracle._reconstruct_with_bytes(*deepcopy(records))
    prefix = None
    logical = []
    for receipt in snapshot.receipts:
        prefix = oracle.advance(prefix, receipt.command, receipt.recorded_at)
        logical.append(oracle.logical_record(receipt.command, prefix))
    exact = (
        exact_history
        if budget == "MAX_HISTORY_BYTES"
        else max(len(storage.canonical_bytes(record)) for record in logical)
    )
    monkeypatch.setattr(storage, budget, exact)
    equivalent(records)
    monkeypatch.setattr(storage, budget, exact - 1)
    for module in (oracle, reconstruction):
        with pytest.raises(module.QuoteIntegrityError, match=r"^stored quote history is invalid$"):
            module.reconstruct(*deepcopy(records))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("old_path", [False, True])
def test_byte_failure_and_outer_rollback_on_both_paths(database, monkeypatch, old_path):
    from cycling_workshop.quotes import repository, storage
    from sqlalchemy.orm import Session
    from test_quote_repository import admitted, counts, creation, revision
    from test_quote_storage import NOW

    if old_path:
        monkeypatch.setattr(
            repository, "_reconstruct_with_bytes", quote_only_oracle_adapter(oracle)
        )
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        snapshot, size = repo._load_with_bytes(repo._lineage("a", "order-a"))
        next_ledger = oracle.advance(snapshot.ledger, revision(), NOW)
        exact = (
            size + 1 + len(storage.canonical_bytes(oracle.logical_record(revision(), next_ledger)))
        )
        monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", exact - 1)
        with pytest.raises(
            ValueError, match=r"^quote storage complete-history byte limit exceeded$"
        ):
            repo.apply(revision(), recorded_at=NOW)
        assert counts(session) == (1, 1, 1, 1)
        monkeypatch.setattr(storage, "MAX_HISTORY_BYTES", exact)
        repo.apply(revision(), recorded_at=NOW)
        assert counts(session) == (1, 2, 2, 2)
        session.rollback()
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize(
    "old_name,new_name",
    [
        ("event_payload", "_event_payload"),
        ("logical_record", "_logical_record"),
    ],
)
def test_oracle_and_new_formatters_are_not_shared(records, monkeypatch, old_name, new_name):
    def broken(*args):
        raise ValueError("synthetic formatter contamination")

    with monkeypatch.context() as patch:
        patch.setattr(reconstruction, new_name, broken)
        oracle.reconstruct(*deepcopy(records))
        with pytest.raises(reconstruction.QuoteIntegrityError):
            reconstruction.reconstruct(*deepcopy(records))
    with monkeypatch.context() as patch:
        patch.setattr(oracle, old_name, broken)
        reconstruction.reconstruct(*deepcopy(records))
        with pytest.raises(oracle.QuoteIntegrityError):
            oracle.reconstruct(*deepcopy(records))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_frozen_advance_is_independent_of_new_path(records, monkeypatch):
    def broken(*args):
        raise ValueError("synthetic advance contamination")

    with monkeypatch.context() as patch:
        patch.setattr(reconstruction, "advance", broken)
        oracle.reconstruct(*deepcopy(records))
        reconstruction.reconstruct(*deepcopy(records))
    with monkeypatch.context() as patch:
        patch.setattr(oracle, "advance", broken)
        reconstruction.reconstruct(*deepcopy(records))
        with pytest.raises(oracle.QuoteIntegrityError):
            oracle.reconstruct(*deepcopy(records))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("order", [(2, 0, 1), (1, 0, 2), (0, 2, 1), (0, 0, 2)])
def test_out_of_order_and_duplicate_commands_fail_closed(records, order):
    records[5] = [deepcopy(records[5][index]) for index in order]
    for module in (oracle, reconstruction):
        with pytest.raises(module.QuoteIntegrityError, match=r"^stored quote history is invalid$"):
            module.reconstruct(*deepcopy(records))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_correction_withdrawal_revision_and_new_initial_are_per_quote(database):
    from cycling_workshop.quotes.repository import QuoteRepository
    from sqlalchemy.orm import Session
    from test_quote_repository import admitted, creation, decision, revision
    from test_quote_storage import NOW, uid

    commands = [
        creation(),
        decision(),
        decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Corrección",
        ),
        decision(
            decision_id=uid(102),
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Retiro",
        ),
        revision(expected_decision_sequence=3),
        decision(
            decision_id=uid(103),
            quote_id=uid(2),
            quote_version=2,
            expected_head_id=uid(2),
            expected_head_version=2,
            expected_decision_sequence=3,
        ),
    ]
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        for command in commands:
            repo.apply(command, recorded_at=NOW)
        equivalent(collect_rows(session))
        for command in commands:
            assert repo.apply(command, recorded_at=NOW).replayed
        session.rollback()


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_coherent_reordering_reaches_current_head_rejection(records):
    create, decision, revision = records[5]
    revision.ordinal = 2
    revision.resulting_decision_sequence = 0
    revision.proof = deepcopy(revision.proof) | {"expected_decision_sequence": 0}
    event = next(row for row in records[6] if row.event_id == revision.quote_outbox_id)
    event.payload = deepcopy(event.payload) | {"decision_sequence": 0, "ordinal": 2}
    decision.ordinal = 3
    records[5] = [create, revision, decision]
    for module in (oracle, reconstruction):
        with pytest.raises(module.QuoteIntegrityError) as failure:
            module.reconstruct(*deepcopy(records))
        assert str(failure.value.__cause__) == "stale quote head or decision sequence"
