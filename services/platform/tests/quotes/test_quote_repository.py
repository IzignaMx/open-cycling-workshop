"""Transactional quote storage, without HTTP grants or operational enrollment."""

from dataclasses import replace
from datetime import timedelta

import pytest
from alembic import command as migrate
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    RecordQuoteDecisionCommand,
    ReviseQuoteCommand,
)
from cycling_workshop.quotes.decisions import DecisionCommand, DecisionEvidence
from cycling_workshop.quotes.domain import PartLine
from cycling_workshop.quotes.models import (
    QuoteLineageRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.quotes.repository import (
    QuoteConflictError,
    QuoteIntegrityError,
    QuoteRepository,
)
from cycling_workshop.service_orders.models import ServiceOrderRecord
from cycling_workshop.sync.writes import lock_writer
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_schema import seed_base
from test_quote_storage import NOW, quote, uid


def creation(**changes):
    lines = tuple(
        replace(line, product_id="product-a") if isinstance(line, PartLine) else line
        for line in quote().lines
    )
    return CreateQuoteCommand(
        **dict(
            operation_id=uid(200),
            quote_id=uid(1),
            organization_id="a",
            location_id="location-a",
            order_id="order-a",
            actor_id="actor-a",
            expected_order_version=1,
            currency="MXN",
            lines=lines,
        )
        | changes
    )


def revision(**changes):
    return ReviseQuoteCommand(
        **dict(
            operation_id=uid(201),
            quote_id=uid(2),
            organization_id="a",
            location_id="location-a",
            order_id="order-a",
            actor_id="actor-a",
            expected_order_version=1,
            lineage_id=uid(1),
            expected_head_id=uid(1),
            expected_head_version=1,
            expected_decision_sequence=0,
            lines=creation().lines,
        )
        | changes
    )


def decision(**changes):
    return RecordQuoteDecisionCommand(
        DecisionCommand(
            **dict(
                decision_id=uid(100),
                organization_id="a",
                location_id="location-a",
                order_id="order-a",
                lineage_id=uid(1),
                quote_id=uid(1),
                quote_version=1,
                expected_head_id=uid(1),
                expected_head_version=1,
                expected_decision_sequence=0,
                recorded_by_actor_id="actor-a",
                mode="initial",
                outcome="PARTIAL",
                approved_line_ids=(uid(10),),
                evidence=DecisionEvidence(
                    "customer", "customer-a", "phone", NOW, "call", "Private note"
                ),
                supersedes_entry_id=None,
                reason=None,
            )
            | changes
        ),
        expected_order_version=1,
    )


@pytest.fixture
def database(identity_migration_database):
    config, engine = identity_migration_database
    migrate.upgrade(config, "head")
    seed_base(engine)
    return engine


def admitted(session, suffix="a", location=None):
    return lock_writer(
        session,
        Principal(f"actor-{suffix}", suffix, location or f"location-{suffix}", frozenset()),
        WriteAdmission.for_fixtures(),
    )


def counts(session):
    return tuple(
        session.scalar(select(func.count()).select_from(model))
        for model in (QuoteLineageRecord, QuoteRevisionRecord, QuoteOperationRecord, OutboxRecord)
    )


def test_create_load_and_explicit_caller_commit(database):
    with Session(database) as session:
        admitted(session)
        result = QuoteRepository(session).apply(creation(), recorded_at=NOW)
        assert not result.replayed
        assert result.ledger.history.head.totals == quote().totals
        assert result.receipt.operation_id == uid(200)
        assert result.receipt.ordinal == 1
        assert result.order.state == "DIAGNOSIS" and result.order.version == 1
        assert QuoteRepository(session).load("a", "location-a", "order-a").ledger == result.ledger
        assert counts(session) == (1, 1, 1, 1)
        session.rollback()
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)


def test_restart_exact_replay_returns_original_receipt_and_current_projection(database):
    with Session(database) as session:
        admitted(session)
        first = QuoteRepository(session).apply(creation(), recorded_at=NOW)
        QuoteRepository(session).apply(decision(), recorded_at=NOW)
        QuoteRepository(session).apply(
            revision(expected_decision_sequence=1), recorded_at=NOW + timedelta(seconds=1)
        )
        session.commit()
    with Session(database) as session:
        admitted(session)
        order = session.get(ServiceOrderRecord, "order-a")
        order.version = 2
        order.state = "AUTHORIZED"
        replay = QuoteRepository(session).apply(creation(), recorded_at=NOW + timedelta(days=1))
        assert replay.replayed and replay.receipt == first.receipt
        assert replay.ledger.history.head.version == 2
        assert replay.ledger.projection.outcome == "NO_CURRENT_DECISION"
        assert replay.order.version == 2 and replay.order.state == "AUTHORIZED"
        old = QuoteRepository(session).apply(decision(), recorded_at=NOW + timedelta(days=1))
        assert old.replayed and old.receipt.ordinal == 2
        assert counts(session) == (1, 2, 3, 3)
        assert replay.ledger.history.revisions[0].superseded_at == NOW + timedelta(seconds=1)


@pytest.mark.parametrize(
    "change",
    [
        dict(currency="USD"),
        dict(expected_order_version=2),
        dict(quote_id=uid(5)),
        dict(lines=tuple(reversed(creation().lines))),
    ],
)
def test_operation_id_reuse_with_changed_semantics_conflicts(database, change):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        with pytest.raises(QuoteConflictError):
            repo.apply(creation(**change), recorded_at=NOW)
        assert counts(session) == (1, 1, 1, 1)


@pytest.mark.parametrize("operation", [creation(expected_order_version=2), revision(), decision()])
def test_stale_or_missing_lineage_has_no_effect(database, operation):
    with Session(database) as session:
        admitted(session)
        with pytest.raises(QuoteConflictError):
            QuoteRepository(session).apply(operation, recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)


def test_single_lineage_and_three_part_cas(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        for operation in (
            creation(operation_id=uid(300), quote_id=uid(3)),
            revision(expected_head_id=uid(3)),
            revision(expected_head_version=2),
            revision(expected_decision_sequence=1),
        ):
            with pytest.raises(QuoteConflictError):
                repo.apply(operation, recorded_at=NOW)
        assert counts(session) == (1, 1, 1, 1)


def test_correction_withdrawal_retains_all_evidence_without_order_effects(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        initial = repo.apply(decision(), recorded_at=NOW)
        corrected = decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Recording fix",
        )
        repo.apply(corrected, recorded_at=NOW)
        withdrawn = decision(
            decision_id=uid(102),
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Wrong record",
        )
        result = repo.apply(withdrawn, recorded_at=NOW)
        assert result.ledger.sequence == 3 and result.ledger.projection.outcome == "WITHDRAW"
        assert repo.apply(decision(), recorded_at=NOW).receipt == initial.receipt
        assert result.order.state == "DIAGNOSIS" and result.order.version == 1
        assert counts(session) == (1, 1, 4, 4)
        for op in session.scalars(select(QuoteOperationRecord)):
            assert (
                op.order_event_id,
                op.resulting_order_version,
                op.change_cursor,
                op.order_outbox_id,
            ) == (None,) * 4
        for outbox in session.scalars(select(OutboxRecord)):
            assert "Private note" not in str(outbox.payload) and "customer-a" not in str(
                outbox.payload
            )


def test_admission_required_and_transaction_scoped_even_on_replay(database):
    with Session(database) as session:
        repo = QuoteRepository(session)
        with pytest.raises(PermissionError):
            repo.apply(creation(), recorded_at=NOW)
        admitted(session)
        repo.apply(creation(), recorded_at=NOW)
        session.commit()
        with pytest.raises(PermissionError):
            repo.apply(creation(), recorded_at=NOW)
        admitted(session, "b")
        with pytest.raises(PermissionError):
            repo.apply(creation(), recorded_at=NOW)


def test_narrow_actor_location_scope_and_wrong_order_refused(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        with pytest.raises(PermissionError):
            repo.apply(creation(actor_id="actor-b"), recorded_at=NOW)
        with pytest.raises(PermissionError):
            repo.apply(creation(location_id="other-location-a"), recorded_at=NOW)
        with pytest.raises(QuoteConflictError):
            repo.apply(creation(order_id="order-b"), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)


def test_new_part_reference_is_scoped_but_replay_keeps_original_snapshot(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        invalid = tuple(
            replace(line, product_id="product-b") if isinstance(line, PartLine) else line
            for line in creation().lines
        )
        with pytest.raises(QuoteConflictError):
            repo.apply(creation(lines=invalid), recorded_at=NOW)
        repo.apply(creation(), recorded_at=NOW)
        session.execute(
            text(
                "UPDATE products SET location_id='other-location-a', name='Changed' "
                "WHERE id='product-a'"
            )
        )
        assert repo.apply(creation(), recorded_at=NOW).replayed


def test_published_outbox_delivery_metadata_does_not_change_receipt(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        first = repo.apply(creation(), recorded_at=NOW)
        row = session.get(OutboxRecord, first.receipt.quote_outbox_id)
        row.attempts = 2
        row.published_at = NOW
        assert repo.apply(creation(), recorded_at=NOW).receipt == first.receipt


def test_corrupt_outbox_content_fails_closed(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        first = repo.apply(creation(), recorded_at=NOW)
        row = session.get(OutboxRecord, first.receipt.quote_outbox_id)
        row.payload = {"tampered": True}
        with pytest.raises(QuoteIntegrityError):
            repo.load("a", "location-a", "order-a")


def test_late_outbox_failure_rolls_back_entire_operation_and_keeps_outer_transaction(
    database, monkeypatch
):
    from cycling_workshop.quotes import repository

    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        original = repository.enqueue_outbox

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("synthetic delivery preparation failure")

        monkeypatch.setattr(repository, "enqueue_outbox", fail)
        with pytest.raises(RuntimeError):
            repo.apply(creation(), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)
        monkeypatch.setattr(repository, "enqueue_outbox", original)
        repo.apply(creation(), recorded_at=NOW)
        session.commit()
    with Session(database) as session:
        assert counts(session) == (1, 1, 1, 1)


def test_new_revision_and_correction_cannot_precede_history(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        repo.apply(decision(), recorded_at=NOW + timedelta(seconds=1))
        with pytest.raises(QuoteConflictError):
            repo.apply(revision(expected_decision_sequence=1), recorded_at=NOW)
        repo.apply(revision(expected_decision_sequence=1), recorded_at=NOW + timedelta(seconds=2))
        correction = decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Old revision",
        )
        with pytest.raises(QuoteConflictError):
            repo.apply(correction, recorded_at=NOW + timedelta(seconds=3))
        assert counts(session) == (1, 2, 3, 3)


def test_late_expiry_rolls_back_new_operation(database, monkeypatch):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        original = repo._admitted
        calls = 0

        def expires(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError("synthetic expired admission")
            original(*args, **kwargs)

        monkeypatch.setattr(repo, "_admitted", expires)
        with pytest.raises(PermissionError):
            repo.apply(creation(), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)
        session.commit()
    with Session(database) as session:
        assert counts(session) == (0, 0, 0, 0)


def test_proof_and_result_share_one_bounded_logical_record(database):
    from cycling_workshop.quotes.domain import LaborLine

    with Session(database) as session:
        admitted(session)
        lines = tuple(LaborLine(uid(1000 + index), "🛞" * 500, 60, 1) for index in range(100))
        with pytest.raises(ValueError, match="record"):
            QuoteRepository(session).apply(creation(lines=lines), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)


@pytest.mark.parametrize("has_lineage", [False, True])
def test_load_rechecks_admission_after_waits_and_reconstruction(database, monkeypatch, has_lineage):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        if has_lineage:
            repo.apply(creation(), recorded_at=NOW)
        original = repo._admitted
        calls = 0

        def expires(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise PermissionError("expired while waiting or reconstructing")
            original(*args, **kwargs)

        monkeypatch.setattr(repo, "_admitted", expires)
        with pytest.raises(PermissionError):
            repo.load("a", "location-a", "order-a")


def test_outbox_decision_contract_has_distinct_delivery_and_domain_identity(database):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        created = repo.apply(creation(), recorded_at=NOW)
        result = repo.apply(decision(), recorded_at=NOW)
        row = session.get(OutboxRecord, result.receipt.quote_outbox_id)
        payload = row.payload
        assert payload["decision_id"] == payload["domain_event_id"] == uid(100)
        assert row.event_id == result.receipt.quote_outbox_id != uid(100)
        assert payload["kind"] == "decision"
        assert payload["organization_id"] == "a" and payload["location_id"] == "location-a"
        assert payload["approved_line_ids"] == [uid(10)]
        assert payload["declined_line_ids"] == [uid(11)]
        assert payload["pricing"] == dict(
            currency="MXN", subtotal_minor=120, discount_minor=11, tax_minor=17, total_minor=126
        )
        assert not {"evidence", "note", "source_reference", "reason", "party_id"} & payload.keys()
        root = session.get(OutboxRecord, created.receipt.quote_outbox_id).payload
        assert root["kind"] == "create"
        assert root["pricing"] == dict(
            currency="MXN", subtotal_minor=220, discount_minor=20, tax_minor=32, total_minor=232
        )


@pytest.mark.parametrize("location", ["location-a", "other-location-a"])
def test_receipt_collisions_outside_order_scope_do_not_read_foreign_proof(database, location):
    with Session(database) as session:
        admitted(session)
        repo = QuoteRepository(session)
        repo.apply(creation(), recorded_at=NOW)
        session.add(
            ServiceOrderRecord(
                id="second-order",
                organization_id="a",
                location_id=location,
                customer_id="customer-a",
                state="DIAGNOSIS",
                reported_problem="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        admitted(session, location=location)
        candidate = creation(
            quote_id=uid(2),
            order_id="second-order",
            location_id=location,
            lines=(creation().lines[0],),
        )
        with pytest.raises(
            QuoteConflictError, match=r"^quote operation conflicts with stored identity or scope$"
        ):
            repo.apply(candidate, recorded_at=NOW)
        assert counts(session) == (1, 1, 1, 1)
        session.commit()
    with Session(database) as session:
        assert counts(session) == (1, 1, 1, 1)
