"""Tiny PR55 differential proof for discarded operation-result codec calls."""

from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest
import quote_reconstruction_pr55_oracle as oracle
from cycling_workshop.quotes import reconstruction, repository, storage
from cycling_workshop.quotes.commands import RecordQuoteDecisionCommand
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_reconstruction import records as records
from test_quote_repository import admitted, creation, decision, revision
from test_quote_repository import database as database
from test_quote_single_pass import collect_rows, quote_only_oracle_adapter
from test_quote_storage import NOW, uid


def row_values(rows):
    return [
        [
            {
                column.key: deepcopy(getattr(row, column.key))
                for column in inspect(row).mapper.columns
            }
            for row in (group if isinstance(group, list) else [group])
        ]
        for group in rows
    ]


def traced(module, rows):
    """Retain actual objects, not reusable ids, at each local and final binding."""
    calls, logical, final_calls = [], [], []
    in_logical = False
    original_formatter = module._logical_record
    before = row_values(rows)

    def encoder(original, name, target):
        def counted(value):
            saved = deepcopy(value)
            result = original(value)
            assert value == saved
            target.append((name, value, saved, in_logical, storage.canonical_bytes(result)))
            return result

        return counted

    def formatter(command, head, entry):
        nonlocal in_logical
        target = entry if entry is not None else head
        saved = deepcopy(target)
        start = len(calls)
        in_logical = True
        try:
            result = original_formatter(command, head, entry)
        finally:
            in_logical = False
        assert target == saved
        assert len(calls) == start + 1
        assert calls[-1][1] is target
        assert head.superseded_at is None and head.superseded_by is None
        logical.append((command, head, entry, storage.canonical_bytes(result), deepcopy(result)))
        return result

    with ExitStack() as stack:
        for name in ("encode_quote", "encode_entry"):
            stack.enter_context(
                patch.object(module, name, encoder(getattr(module, name), name, calls))
            )
            stack.enter_context(
                patch.object(storage, name, encoder(getattr(storage, name), name, final_calls))
            )
        stack.enter_context(patch.object(module, "_logical_record", formatter))
        snapshot, size = module._reconstruct_with_bytes(*rows)
    assert row_values(rows) == before
    for _, value, saved, _, _ in calls + final_calls:
        assert value == saved
    assert size == len(storage.canonical_bytes([item[4] for item in logical]))
    assert len(logical) == len(rows[5])
    return snapshot, size, calls, logical, final_calls


def equivalent(rows):
    old, new = traced(oracle, rows), traced(reconstruction, rows)
    assert old[0].ledger == new[0].ledger
    assert [asdict(item) | {"order_effects": None} for item in old[0].receipts] == [
        asdict(item) for item in new[0].receipts
    ]
    assert old[1] == new[1]
    assert [item[3] for item in old[3]] == [item[3] for item in new[3]]
    for previous, current in zip(old[3], new[3], strict=True):
        assert previous[:3] == current[:3]
    return old, new


def test_frozen_pr55_oracle_has_exact_reviewed_source_bytes():
    assert sha256(Path(oracle.__file__).read_bytes()).hexdigest() == (
        "113eab84cdfb5fc33babb0427de0f31339e2a79bbb934da742ffddbf6b41521c"
    )


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_one_codec_per_result_retains_predecessor_and_final_codecs(records):
    old, new = equivalent(records)
    revision_count, decision_count = len(records[1]), len(records[4])
    assert Counter(call[0] for call in old[2]) == {
        "encode_quote": 3 * revision_count - 1,
        "encode_entry": 2 * decision_count,
    }
    assert Counter(call[0] for call in new[2]) == {
        "encode_quote": 2 * revision_count - 1,
        "encode_entry": decision_count,
    }
    for trace, expected_calls in ((old, 2), (new, 1)):
        for command, head, entry, _, _ in trace[3]:
            target = entry if isinstance(command, RecordQuoteDecisionCommand) else head
            matching = [call for call in trace[2] if call[1] is target]
            assert len(matching) == expected_calls
            assert sum(call[3] for call in matching) == 1
            assert len({call[4] for call in matching}) == 1
        predecessors = [call for call in trace[2] if call[0] == "encode_quote" and not call[3]]
        predecessors = [call[1] for call in predecessors if call[1].superseded_by is not None]
        assert tuple(predecessors) == trace[0].ledger.history.revisions[:-1]
        final = trace[4]
        assert Counter(call[0] for call in final) == {
            "encode_quote": revision_count,
            "encode_entry": decision_count,
        }
        expected = (*trace[0].ledger.history.revisions, *trace[0].ledger.entries)
        assert len(final) == len(expected)
        assert all(call[1] is value for call, value in zip(final, expected, strict=True))


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("budget", ["MAX_RECORD_BYTES", "MAX_HISTORY_BYTES"])
def test_exact_lowered_limits_and_one_byte_over_match_pr55(records, monkeypatch, budget):
    baseline = traced(oracle, records)
    exact = (
        baseline[1] if budget == "MAX_HISTORY_BYTES" else max(len(item[3]) for item in baseline[3])
    )
    assert exact < getattr(storage, budget)
    monkeypatch.setattr(storage, budget, exact)
    equivalent(records)
    monkeypatch.setattr(storage, budget, exact - 1)
    for module in (oracle, reconstruction):
        before = row_values(records)
        with pytest.raises(module.QuoteIntegrityError) as error:
            module._reconstruct_with_bytes(*records)
        assert type(error.value) is module.QuoteIntegrityError
        assert str(error.value) == "stored quote history is invalid"
        assert row_values(records) == before


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize(
    "corruption",
    ["stale_prefix", "bool_ordinal", "proof", "revision", "decision", "outbox"],
)
def test_malformed_prefixes_keep_public_error_and_inputs(records, corruption):
    if corruption == "stale_prefix":
        records[5][-1].proof = deepcopy(records[5][-1].proof) | {"expected_decision_sequence": 0}
    elif corruption == "bool_ordinal":
        records[5][0].ordinal = True
    elif corruption == "proof":
        records[5][0].proof = deepcopy(records[5][0].proof) | {"unknown": None}
    elif corruption == "revision":
        records[1][0].total_minor += 1
    elif corruption == "decision":
        records[4][0].sequence = 2
    else:
        records[6][0].payload = {"corrupt": "café 🚲"}
    before = row_values(records)
    for module in (oracle, reconstruction):
        for function in (module.reconstruct, module._reconstruct_with_bytes):
            with pytest.raises(module.QuoteIntegrityError) as error:
                function(*records)
            assert type(error.value) is module.QuoteIntegrityError
            assert isinstance(error.value, ValueError)
            assert str(error.value) == "stored quote history is invalid"
            assert row_values(records) == before


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("name", ["_logical_record", "_event_payload"])
def test_pr55_local_formatters_are_bidirectionally_independent(records, monkeypatch, name):
    assert getattr(oracle, name) is not getattr(reconstruction, name)

    def broken(*args):
        raise ValueError("synthetic local formatter contamination")

    for changed, independent in ((oracle, reconstruction), (reconstruction, oracle)):
        with monkeypatch.context() as isolated:
            isolated.setattr(changed, name, broken)
            independent.reconstruct(*records)
            with pytest.raises(
                changed.QuoteIntegrityError, match=r"^stored quote history is invalid$"
            ):
                changed.reconstruct(*records)


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
def test_unicode_mixed_correction_withdrawal_revision_and_initial(database):
    first = creation()
    first = replace(
        first,
        lines=tuple(replace(line, description="Revisión café 🚲") for line in first.lines),
    )
    evidence = replace(decision().command.evidence, note='Nota café 🚲\n"exacta"')
    commands = [
        first,
        decision(evidence=evidence),
        decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Corrección café 🚲",
            evidence=evidence,
        ),
        decision(
            decision_id=uid(102),
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Retiro café 🚲",
        ),
        revision(expected_decision_sequence=3),
        decision(
            decision_id=uid(103),
            quote_id=uid(2),
            quote_version=2,
            expected_head_id=uid(2),
            expected_head_version=2,
            expected_decision_sequence=3,
            evidence=evidence,
        ),
    ]
    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        for command in commands:
            repo.apply(command, recorded_at=NOW)
        rows = collect_rows(session)
        assert len(rows[1]) == 2 and len(rows[2]) == 8
        _, current = equivalent(rows)
        assert b"\xf0\x9f\x9a\xb2" in current[3][0][3]
        assert current[0].ledger.sequence == 4
        for command in commands:
            assert repo.apply(command, recorded_at=NOW).replayed
        session.rollback()


@pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)
@pytest.mark.parametrize("module", [oracle, reconstruction], ids=["pr55", "current"])
def test_corrupt_history_rejection_has_zero_database_writes(database, monkeypatch, module):
    from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
    from cycling_workshop.sync.models import ChangeRecord

    def saved(session):
        rows = collect_rows(session)
        rows.extend(
            list(session.scalars(select(model)))
            for model in (
                ServiceOrderRecord,
                ServiceOrderEventRecord,
                ChangeRecord,
            )
        )
        return row_values(rows)

    with Session(database) as session:
        admitted(session)
        repo = repository.QuoteRepository(session)
        initial = repo.apply(creation(), recorded_at=NOW)
        # Outbox delivery rows are mutable. Persist corruption before measuring
        # the rejected load, as if external restore supplied invalid evidence.
        outbox = next(
            row
            for row in collect_rows(session)[6]
            if row.event_id == initial.receipt.quote_outbox_id
        )
        outbox.payload = {"corrupt": True}
        session.flush()
        baseline = saved(session)
        writes = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().split(None, 1)[0].upper() in {
                "INSERT",
                "UPDATE",
                "DELETE",
                "REPLACE",
            }:
                writes.append(statement)

        monkeypatch.setattr(
            repository,
            "_reconstruct_with_bytes",
            quote_only_oracle_adapter(oracle)
            if module is oracle
            else module._reconstruct_with_bytes,
        )
        event.listen(database, "before_cursor_execute", capture)
        try:
            for command in (creation(), revision()):
                with pytest.raises(
                    module.QuoteIntegrityError, match=r"^stored quote history is invalid$"
                ):
                    repo.apply(command, recorded_at=NOW)
            assert writes == []
            assert saved(session) == baseline
        finally:
            event.remove(database, "before_cursor_execute", capture)
        session.rollback()
