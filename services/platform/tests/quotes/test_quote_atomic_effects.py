"""Tiny atomic-effect specifications, prepared without executing a test process.

SQLite is a functional surrogate only. These cases do not qualify concurrency,
request cancellation, capacity, route exposure, or production activation.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes.decisions import QuoteDecisionLedger, plan_initial_transition
from cycling_workshop.quotes.effects import QuoteOrderEffects
from cycling_workshop.quotes.models import QuoteDecisionRecord, QuoteOperationRecord
from cycling_workshop.quotes.reconstruction import (
    QuoteIntegrityError,
    _reconstruct_with_bytes,
    reconstruct,
)
from cycling_workshop.quotes.repository import QuoteConflictError, QuoteRepository
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.projections import order_payload
from cycling_workshop.sync.writes import append_change
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_repository import admitted, counts, creation, decision
from test_quote_repository import database as database
from test_quote_single_pass import collect_rows
from test_quote_storage import NOW

pytestmark = pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True)


def refuse(*args):
    raise RuntimeError("new command unavailable")


def accept(order, snapshot):
    assert order.state == "DIAGNOSIS"


def transition_effects(session, order, ledger, fresh):
    assert fresh is not None and fresh.ledger is ledger and not fresh.replayed
    repository = SqlAlchemyServiceOrderRepository(session)
    domain = repository._to_domain(order)
    plan = plan_initial_transition(ledger, domain, fresh)
    result = domain.transition(
        plan.action, actor_id="actor-a", event_id=fresh.entry.command.decision_id, now=NOW
    )
    repository.save(result.order)
    repository.add_event(result.event)
    appended = append_change(
        session,
        organization_id=domain.organization_id,
        location_id=domain.location_id,
        entity_type="service_order",
        entity_id=domain.order_id,
        operation="update",
        entity_version=result.order.version,
        occurred_at=NOW,
        payload=order_payload(result.order),
    )
    return QuoteOrderEffects(
        result.event.event_id, result.order.version, appended.cursor, appended.outbox_event_id
    )


def apply_decision(session, effects=None):
    return QuoteRepository(session)._apply_application(
        decision(),
        recorded_at=NOW,
        admit_new=accept,
        apply_effects=effects
        or (lambda order, ledger, fresh: transition_effects(session, order, ledger, fresh)),
    )


def effect_counts(session):
    return tuple(
        session.scalar(select(func.count()).select_from(model))
        for model in (QuoteDecisionRecord, ServiceOrderEventRecord, ChangeRecord, OutboxRecord)
    )


def test_actual_fresh_result_and_complete_receipt_exist_on_first_insert(database, monkeypatch):
    fresh_results = []
    record = QuoteDecisionLedger.record

    def capture(self, *args, **kwargs):
        result = record(self, *args, **kwargs)
        fresh_results.append(result)
        return result

    monkeypatch.setattr(QuoteDecisionLedger, "record", capture)
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        inserted = []

        def inspect_insert(mapper, connection, target):
            inserted.append(
                (
                    target.order_event_id,
                    target.resulting_order_version,
                    target.change_cursor,
                    target.order_outbox_id,
                    target.quote_outbox_id,
                )
            )

        def effects(order, ledger, fresh):
            assert fresh is fresh_results[-1]
            return transition_effects(session, order, ledger, fresh)

        event.listen(QuoteOperationRecord, "before_insert", inspect_insert)
        try:
            result = apply_decision(session, effects)
        finally:
            event.remove(QuoteOperationRecord, "before_insert", inspect_insert)
        receipt = result.receipt
        effect = receipt.order_effects
        assert effect is not None
        assert inserted == [
            (
                effect.order_event_id,
                2,
                effect.change_cursor,
                effect.order_outbox_id,
                receipt.quote_outbox_id,
            )
        ]
        assert effect.order_outbox_id != receipt.quote_outbox_id
        assert effect.order_event_id == receipt.operation_id
        assert result.order.state == "AUTHORIZED" and result.order.version == 2
        assert effect_counts(session) == (1, 1, 1, 3)
        assert repository.load("a", "location-a", "order-a").receipts[-1] == receipt
        session.commit()
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        replay = repository._apply_application(
            decision(), recorded_at=NOW + timedelta(days=1), admit_new=refuse, apply_effects=refuse
        )
        assert replay.replayed and replay.receipt == receipt
        assert effect_counts(session) == (1, 1, 1, 3)


def test_historical_null_effect_replay_never_creates_transition(database):
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        historical = repository.apply(decision(), recorded_at=NOW)
        replay = repository._apply_application(
            decision(), recorded_at=NOW, admit_new=refuse, apply_effects=refuse
        )
        assert replay.replayed and replay.receipt == historical.receipt
        assert replay.receipt.order_effects is None
        assert replay.order.state == "DIAGNOSIS" and effect_counts(session) == (1, 0, 0, 2)


def test_absent_operation_policy_runs_before_stale_cas_and_any_effect(database):
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        before = counts(session)
        with pytest.raises(RuntimeError, match="new command unavailable"):
            repository._apply_application(
                creation(expected_order_version=99),
                recorded_at=NOW,
                admit_new=refuse,
                apply_effects=refuse,
            )
        assert counts(session) == before


def test_failure_after_order_effects_rolls_back_complete_operation(database):
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        before = counts(session)

        def effects(order, ledger, fresh):
            transition_effects(session, order, ledger, fresh)
            raise RuntimeError("injected late failure")

        with pytest.raises(RuntimeError, match="injected late failure"):
            apply_decision(session, effects)
        assert counts(session) == before
        assert effect_counts(session) == (0, 0, 0, 1)
        order = session.get(ServiceOrderRecord, "order-a")
        assert (order.state, order.version) == ("DIAGNOSIS", 1)
        assert repository.load("a", "location-a", "order-a").ledger.sequence == 0


@pytest.fixture
def effect_records(database):
    with Session(database) as session:
        admitted(session)
        QuoteRepository(session).apply(creation(), recorded_at=NOW)
        applied = apply_decision(session)
        data = collect_rows(session)
        data[6] = [row for row in data[6] if row.aggregate_type == "quote"]
        effects = dict(
            order_events=list(session.scalars(select(ServiceOrderEventRecord))),
            changes=list(session.scalars(select(ChangeRecord))),
            order_outboxes=list(
                session.scalars(select(OutboxRecord).where(OutboxRecord.aggregate_type != "quote"))
            ),
        )
        session.expunge_all()
    return data, effects, applied.receipt


@pytest.mark.parametrize(
    "group,field,value",
    [
        ("order_events", "actor_id", "actor-b"),
        ("order_events", "order_id", "order-b"),
        ("order_events", "organization_id", "b"),
        ("order_events", "action", "reject"),
        ("order_events", "occurred_at", NOW + timedelta(seconds=1)),
        ("changes", "location_id", "other-location-a"),
        ("changes", "organization_id", "b"),
        ("changes", "entity_id", "order-b"),
        ("changes", "entity_version", 3),
        ("changes", "payload", {"state": "AUTHORIZED"}),
        ("order_outboxes", "event_type", "service_order.created"),
        ("order_outboxes", "organization_id", "b"),
        ("order_outboxes", "location_id", "other-location-a"),
        ("order_outboxes", "aggregate_id", "order-b"),
        ("order_outboxes", "payload", {"unexpected": True}),
    ],
)
def test_corrupt_effect_association_has_normalized_integrity_error(
    effect_records, group, field, value
):
    data, effects, _receipt = effect_records
    setattr(effects[group][0], field, value)
    with pytest.raises(QuoteIntegrityError, match=r"^stored quote history is invalid$"):
        reconstruct(*data, **effects)


def test_missing_or_boolean_tuple_field_is_not_treated_as_historical(effect_records):
    data, effects, _receipt = effect_records
    operation = data[5][-1]
    operation.change_cursor = True
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*data, **effects)
    operation.change_cursor = None
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*data, **effects)


def test_foreign_cursor_is_refused_without_materializing_its_payload(database):
    with Session(database) as session:
        admitted(session)
        QuoteRepository(session).apply(creation(), recorded_at=NOW)
        foreign = ChangeRecord(
            organization_id="b",
            location_id="location-b",
            entity_type="service_order",
            entity_id="order-b",
            operation="update",
            entity_version=2,
            occurred_at=NOW,
            payload={"private": "foreign projection must not be loaded"},
        )
        session.add(foreign)
        session.flush()
        foreign_cursor = foreign.cursor
        session.expunge(foreign)
        materialized = []

        def observe(_session, instance):
            if isinstance(instance, ChangeRecord) and instance.cursor == foreign_cursor:
                materialized.append(instance)

        def effects(order, ledger, fresh):
            own = transition_effects(session, order, ledger, fresh)
            return replace(own, change_cursor=foreign_cursor)

        event.listen(session, "loaded_as_persistent", observe)
        try:
            with pytest.raises(QuoteIntegrityError, match=r"^stored quote history is invalid$"):
                apply_decision(session, effects)
        finally:
            event.remove(session, "loaded_as_persistent", observe)
        assert materialized == []
        assert effect_counts(session) == (0, 0, 1, 1)


@pytest.mark.parametrize("group", ["order_events", "changes", "order_outboxes"])
def test_missing_or_duplicate_effect_is_not_repaired(effect_records, group):
    data, effects, _receipt = effect_records
    duplicate = deepcopy(effects)
    duplicate[group].append(deepcopy(duplicate[group][0]))
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*data, **duplicate)
    effects[group].clear()
    with pytest.raises(QuoteIntegrityError):
        reconstruct(*data, **effects)


def test_delivery_bookkeeping_does_not_change_receipt(effect_records):
    data, effects, receipt = effect_records
    for row in (*data[6], *effects["order_outboxes"]):
        row.attempts = 12
        row.published_at = NOW + timedelta(days=1)
    assert reconstruct(*data, **effects).receipts[-1] == receipt


def test_application_decision_requires_complete_effects(database):
    with Session(database) as session:
        admitted(session)
        QuoteRepository(session).apply(creation(), recorded_at=NOW)
        with pytest.raises(QuoteConflictError):
            apply_decision(session, lambda order, ledger, fresh: None)
        assert effect_counts(session) == (0, 0, 0, 1)


def test_late_checkpoint_rolls_back_effects_without_integrity_normalization(database):
    expired = False

    def checkpoint():
        if expired:
            raise TimeoutError("synthetic expiry")

    with Session(database) as session:
        admitted(session)
        QuoteRepository(session).apply(creation(), recorded_at=NOW)

        def effects(order, ledger, fresh):
            nonlocal expired
            result = transition_effects(session, order, ledger, fresh)
            expired = True
            return result

        with pytest.raises(TimeoutError, match="synthetic expiry"):
            QuoteRepository(session)._apply_application(
                decision(),
                recorded_at=NOW,
                admit_new=accept,
                apply_effects=effects,
                checkpoint=checkpoint,
            )
        assert effect_counts(session) == (0, 0, 0, 1)


def test_reconstruction_checkpoint_escapes_integrity_normalization(effect_records):
    data, effects, _receipt = effect_records

    def expired():
        raise TimeoutError("synthetic expiry")

    with pytest.raises(TimeoutError, match="synthetic expiry"):
        _reconstruct_with_bytes(*data, **effects, checkpoint=expired)


def test_replay_after_later_cancellation_retains_original_transition(database):
    with Session(database) as session:
        admitted(session)
        repository = QuoteRepository(session)
        repository.apply(creation(), recorded_at=NOW)
        original = apply_decision(session)
        orders = SqlAlchemyServiceOrderRepository(session)
        current = orders.get(order_id="order-a", organization_id="a")
        cancelled = current.transition("cancel", actor_id="actor-a", now=NOW + timedelta(days=1))
        orders.save(cancelled.order)
        orders.add_event(cancelled.event)
        append_change(
            session,
            organization_id="a",
            location_id="location-a",
            entity_type="service_order",
            entity_id="order-a",
            operation="update",
            entity_version=cancelled.order.version,
            occurred_at=cancelled.order.updated_at,
            payload=order_payload(cancelled.order),
        )
        session.commit()
    with Session(database) as session:
        admitted(session)
        replay = QuoteRepository(session)._apply_application(
            decision(), recorded_at=NOW + timedelta(days=2), admit_new=refuse, apply_effects=refuse
        )
        assert replay.replayed and replay.receipt == original.receipt
        assert (replay.order.state, replay.order.version) == ("CANCELLED", 3)
        assert effect_counts(session) == (1, 2, 2, 4)
