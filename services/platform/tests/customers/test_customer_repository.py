from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.db.base import Base
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def seed_tenant(session: Session) -> None:
    session.add_all(
        [
            OrganizationRecord(id="org-1", name="Taller Uno"),
            OrganizationRecord(id="org-2", name="Taller Dos"),
            LocationRecord(id="loc-1", organization_id="org-1", name="Principal"),
            LocationRecord(id="loc-2", organization_id="org-2", name="Principal"),
        ]
    )
    session.commit()


def test_repository_round_trip_preserves_customer_domain() -> None:
    with build_session() as session:
        seed_tenant(session)
        repository = SqlAlchemyCustomerRepository(session)
        customer = Customer.create(
            customer_id="customer-1",
            organization_id="org-1",
            location_id="loc-1",
            display_name="Ana Rivera",
            email="ana@example.com",
        )

        repository.add(customer)
        session.commit()
        loaded = repository.get(
            customer_id="customer-1",
            organization_id="org-1",
        )

        assert loaded == customer


def test_repository_denies_cross_organization_lookup() -> None:
    with build_session() as session:
        seed_tenant(session)
        repository = SqlAlchemyCustomerRepository(session)
        customer = Customer.create(
            customer_id="customer-1",
            organization_id="org-1",
            location_id="loc-1",
            display_name="Ana Rivera",
        )
        repository.add(customer)
        session.commit()

        assert repository.get(customer_id="customer-1", organization_id="org-2") is None
