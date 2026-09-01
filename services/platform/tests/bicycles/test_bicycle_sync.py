from datetime import UTC, datetime

import pytest
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
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


def _mutation(
    mutation_id: str,
    entity_id: str,
    *,
    operation: str = "create",
    base_version: int | None = None,
    payload: dict[str, object] | None = None,
) -> MutationEnvelope:
    return MutationEnvelope(
        mutation_id=mutation_id,
        entity_type="bicycle",  # type: ignore[arg-type]
        entity_id=entity_id,
        operation=operation,  # type: ignore[arg-type]
        organization_id="org-1",
        location_id="loc-1",
        base_version=base_version,
        occurred_at=NOW,
        payload=payload or {},
    )


def test_bicycle_create_applies_and_writes_change_record() -> None:
    session = _build_session()
    try:
        _seed(session)

        result = SyncService(session).apply(
            _mutation(
                "mut-1",
                "bike-1",
                payload={
                    "customer_id": "customer-1",
                    "brand": "  Trek   Marlin ",
                    "model": "7",
                    "wheel_size": "29",
                },
            )
        )
        session.commit()

        assert result.status == "applied"
        assert result.entity_version == 1
        stored = SqlAlchemyBicycleRepository(session).get(
            bicycle_id="bike-1", organization_id="org-1"
        )
        assert stored is not None
        assert stored.brand == "Trek Marlin"
        assert stored.wheel_size == "29"
        feed = session.execute(text("SELECT entity_type, operation FROM sync_changes")).fetchall()
        assert ("bicycle", "create") in feed
    finally:
        session.close()


def test_bicycle_create_requires_existing_customer() -> None:
    session = _build_session()
    try:
        _seed(session)

        with pytest.raises(SyncConflict, match="customer does not exist"):
            SyncService(session).apply(
                _mutation("mut-2", "bike-2", payload={"customer_id": "ghost", "brand": "X"})
            )
    finally:
        session.close()


def test_bicycle_update_honors_base_version() -> None:
    session = _build_session()
    try:
        _seed(session)
        service = SyncService(session)
        service.apply(
            _mutation("mut-3", "bike-3", payload={"customer_id": "customer-1", "brand": "Cube"})
        )
        session.commit()

        updated = service.apply(
            _mutation(
                "mut-4",
                "bike-3",
                operation="update",
                base_version=1,
                payload={"brand": "Nueva"},
            )
        )
        session.commit()
        assert updated.entity_version == 2

        # Stale base version raises the domain conflict; the router converts
        # it into a per-mutation conflict result (same contract as customers).
        with pytest.raises(SyncConflict, match="base version"):
            service.apply(
                _mutation(
                    "mut-5",
                    "bike-3",
                    operation="update",
                    base_version=1,
                    payload={"brand": "Obsoleta"},
                )
            )
        stored = SqlAlchemyBicycleRepository(session).get(
            bicycle_id="bike-3", organization_id="org-1"
        )
        assert stored is not None
        assert stored.brand == "Nueva"
    finally:
        session.close()
