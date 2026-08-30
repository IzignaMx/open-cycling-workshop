from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.models import CustomerRecord


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyCustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, customer: Customer) -> None:
        self._session.add(self._to_record(customer))

    def save(self, customer: Customer) -> None:
        record = self._session.get(CustomerRecord, customer.customer_id)
        if record is None:
            self.add(customer)
            return
        if record.organization_id != customer.organization_id:
            raise ValueError("customer tenant cannot change")
        record.location_id = customer.location_id
        record.display_name = customer.display_name
        record.email = customer.email
        record.phone = customer.phone
        record.updated_at = customer.updated_at
        record.version = customer.version

    def get(self, *, customer_id: str, organization_id: str) -> Customer | None:
        statement: Select[tuple[CustomerRecord]] = select(CustomerRecord).where(
            CustomerRecord.id == customer_id,
            CustomerRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def list_for_organization(self, *, organization_id: str, limit: int = 100) -> list[Customer]:
        statement = (
            select(CustomerRecord)
            .where(CustomerRecord.organization_id == organization_id)
            .order_by(CustomerRecord.display_name, CustomerRecord.id)
            .limit(limit)
        )
        return [self._to_domain(record) for record in self._session.scalars(statement)]

    @staticmethod
    def _to_record(customer: Customer) -> CustomerRecord:
        return CustomerRecord(
            id=customer.customer_id,
            organization_id=customer.organization_id,
            location_id=customer.location_id,
            display_name=customer.display_name,
            email=customer.email,
            phone=customer.phone,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
            version=customer.version,
        )

    @staticmethod
    def _to_domain(record: CustomerRecord) -> Customer:
        return Customer(
            customer_id=record.id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            display_name=record.display_name,
            email=record.email,
            phone=record.phone,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            version=record.version,
        )
