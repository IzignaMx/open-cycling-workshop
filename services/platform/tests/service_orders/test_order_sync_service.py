from datetime import UTC, datetime

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.sync.domain import MutationEnvelope, SyncConflict
from cycling_workshop.sync.service import SyncService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def _build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _seed(session: Session) -> None:
    session.add(OrganizationRecord(id="org-1", name="Taller"))
    session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
    session.add(
        CustomerRecord(
            id="customer-1",
            organization_id="org-1",
            location_id="loc-1",
            display_name="Ana Rivera",
            created_at=NOW,
            updated_at=NOW,
            version=1,
        )
    )
    session.commit()


def _order_mutation(
    mutation_id: str,
    entity_id: str,
    *,
    operation: str = "create",
    base_version: int | None = None,
    payload: dict[str, object] | None = None,
) -> MutationEnvelope:
    return MutationEnvelope(
        mutation_id=mutation_id,
        entity_type="service_order",  # type: ignore[arg-type]
        entity_id=entity_id,
        operation=operation,  # type: ignore[arg-type]
        organization_id="org-1",
        location_id="loc-1",
        base_version=base_version,
        occurred_at=NOW,
        payload=payload or {},
    )


CREATE_PAYLOAD: dict[str, object] = {
    "customer_id": "customer-1",
    "reported_problem": "Cadena saltando",
    "intake_condition": "Rayado leve",
    "accessories": "Canasto",
    "priority": "high",
}


def _create_order(service: SyncService, order_id: str = "order-1") -> None:
    service.apply(_order_mutation("mut-create-" + order_id, order_id, payload=CREATE_PAYLOAD))


def test_order_create_starts_at_intake_and_feeds_change_record() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)

        result = service.apply(_order_mutation("mut-1", "order-1", payload=CREATE_PAYLOAD))
        session.commit()

        assert result.status == "applied"
        assert result.entity_version == 1
        row = session.execute(
            text("SELECT state, reported_problem FROM service_orders WHERE id='order-1'")
        ).fetchone()
        assert row is not None
        assert row[0] == "INTAKE"
        assert row[1] == "Cadena saltando"
        feed = session.execute(text("SELECT entity_type, operation FROM sync_changes")).fetchall()
        assert ("service_order", "create") in feed
    finally:
        session.close()


def test_order_create_requires_existing_customer() -> None:
    session = _build_session()
    try:
        _seed(session)

        with pytest.raises(SyncConflict, match="customer does not exist"):
            SyncService(session).apply(
                _order_mutation(
                    "mut-2",
                    "order-2",
                    payload={**CREATE_PAYLOAD, "customer_id": "ghost"},
                )
            )
    finally:
        session.close()


def test_order_transition_applies_and_appends_timeline_event() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)
        _create_order(service)
        session.commit()

        result = service.apply(
            _order_mutation(
                "mut-t1",
                "order-1",
                operation="update",
                base_version=1,
                payload={"transition": {"action": "start_diagnosis", "actor_id": "user-1"}},
            )
        )
        session.commit()

        assert result.status == "applied"
        assert result.entity_version == 2
        state = session.execute(
            text("SELECT state FROM service_orders WHERE id='order-1'")
        ).scalar()
        assert state == "DIAGNOSIS"
        events = session.execute(
            text(
                "SELECT from_state, to_state, action FROM service_order_events"
                " WHERE order_id='order-1'"
            )
        ).fetchall()
        assert events == [("INTAKE", "DIAGNOSIS", "start_diagnosis")]
    finally:
        session.close()


def test_invalid_transition_is_a_permanent_sync_conflict() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)
        _create_order(service)
        session.commit()

        with pytest.raises(SyncConflict, match="invalid_state_transition"):
            service.apply(
                _order_mutation(
                    "mut-t2",
                    "order-1",
                    operation="update",
                    base_version=1,
                    payload={"transition": {"action": "mark_ready", "actor_id": "user-1"}},
                )
            )
        # the order is untouched and no event was written
        state = session.execute(
            text("SELECT state, version FROM service_orders WHERE id='order-1'")
        ).fetchone()
        assert state == ("INTAKE", 1)
        events = session.execute(
            text("SELECT count(*) FROM service_order_events WHERE order_id='order-1'")
        ).scalar()
        assert events == 0
    finally:
        session.close()


def test_order_transition_with_stale_base_version_conflicts() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)
        _create_order(service)
        service.apply(
            _order_mutation(
                "mut-t3",
                "order-1",
                operation="update",
                base_version=1,
                payload={"transition": {"action": "start_diagnosis", "actor_id": "user-1"}},
            )
        )
        session.commit()

        with pytest.raises(SyncConflict, match="base version"):
            service.apply(
                _order_mutation(
                    "mut-t4",
                    "order-1",
                    operation="update",
                    base_version=1,
                    payload={"transition": {"action": "authorize", "actor_id": "user-1"}},
                )
            )
    finally:
        session.close()


def test_update_without_transition_and_without_fields_is_rejected() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)
        _create_order(service)
        session.commit()

        with pytest.raises(SyncConflict, match="unsupported order update"):
            service.apply(_order_mutation("mut-t5", "order-1", operation="update", base_version=1))
    finally:
        session.close()
