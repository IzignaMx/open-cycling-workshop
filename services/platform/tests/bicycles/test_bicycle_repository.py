from datetime import UTC, datetime

import pytest
from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def _build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _seed_tenant(session: Session) -> None:
    session.add(OrganizationRecord(id="org-1", name="Taller Uno"))
    session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
    session.add(
        CustomerRecord(
            id="customer-1",
            organization_id="org-1",
            location_id="loc-1",
            display_name="Ana Rivera",
            created_at=datetime(2026, 8, 31, tzinfo=UTC),
            updated_at=datetime(2026, 8, 31, tzinfo=UTC),
            version=1,
        )
    )
    session.commit()


def _bicycle(
    bicycle_id: str,
    *,
    customer_id: str = "customer-1",
    brand: str = "Trek Marlin",
    model: str | None = "7",
) -> Bicycle:
    return Bicycle.create(
        bicycle_id=bicycle_id,
        customer_id=customer_id,
        organization_id="org-1",
        location_id="loc-1",
        brand=brand,
        model=model,
    )


def test_repository_add_get_roundtrip() -> None:
    session = _build_session()
    try:
        _seed_tenant(session)
        repository = SqlAlchemyBicycleRepository(session)
        bicycle = _bicycle("bike-1")
        repository.add(bicycle)
        session.commit()

        stored = repository.get(bicycle_id="bike-1", organization_id="org-1")

        assert stored == bicycle
    finally:
        session.close()


def test_repository_is_tenant_scoped() -> None:
    session = _build_session()
    try:
        _seed_tenant(session)
        repository = SqlAlchemyBicycleRepository(session)
        repository.add(_bicycle("bike-1"))
        session.commit()

        assert repository.get(bicycle_id="bike-1", organization_id="org-other") is None
    finally:
        session.close()


def test_repository_lists_only_the_customers_bicycles_ordered() -> None:
    session = _build_session()
    try:
        _seed_tenant(session)
        session.add(
            CustomerRecord(
                id="customer-2",
                organization_id="org-1",
                location_id="loc-1",
                display_name="Beto Luna",
                created_at=datetime(2026, 8, 31, tzinfo=UTC),
                updated_at=datetime(2026, 8, 31, tzinfo=UTC),
                version=1,
            )
        )
        session.commit()
        repository = SqlAlchemyBicycleRepository(session)
        repository.add(_bicycle("bike-2", brand="Giant"))
        repository.add(_bicycle("bike-1", brand="Cube"))
        repository.add(_bicycle("bike-3", customer_id="customer-2", brand="Scott"))
        session.commit()

        listed = repository.list_by_customer(customer_id="customer-1", organization_id="org-1")

        assert [bicycle.bicycle_id for bicycle in listed] == ["bike-1", "bike-2"]
        assert all(bicycle.customer_id == "customer-1" for bicycle in listed)
    finally:
        session.close()


def test_repository_save_updates_and_rejects_tenant_change() -> None:
    session = _build_session()
    try:
        _seed_tenant(session)
        repository = SqlAlchemyBicycleRepository(session)
        bicycle = _bicycle("bike-1")
        repository.add(bicycle)
        session.commit()

        updated = bicycle.update(model="9")
        repository.save(updated)
        session.commit()

        stored = repository.get(bicycle_id="bike-1", organization_id="org-1")
        assert stored is not None
        assert stored.model == "9"
        assert stored.version == 2

        with pytest.raises(ValueError, match="tenant"):
            repository.save(
                Bicycle.create(
                    bicycle_id="bike-1",
                    customer_id="customer-1",
                    organization_id="org-other",
                    location_id="loc-1",
                    brand="X",
                )
            )
    finally:
        session.close()
