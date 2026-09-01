from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.models import BicycleRecord


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyBicycleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, bicycle: Bicycle) -> None:
        self._session.add(self._to_record(bicycle))

    def save(self, bicycle: Bicycle) -> None:
        record = self._session.get(BicycleRecord, bicycle.bicycle_id)
        if record is None:
            self.add(bicycle)
            return
        if record.organization_id != bicycle.organization_id:
            raise ValueError("bicycle tenant cannot change")
        record.location_id = bicycle.location_id
        record.customer_id = bicycle.customer_id
        record.brand = bicycle.brand
        record.model = bicycle.model
        record.bicycle_type = bicycle.bicycle_type
        record.wheel_size = bicycle.wheel_size
        record.notes = bicycle.notes
        record.updated_at = bicycle.updated_at
        record.version = bicycle.version

    def get(self, *, bicycle_id: str, organization_id: str) -> Bicycle | None:
        statement: Select[tuple[BicycleRecord]] = select(BicycleRecord).where(
            BicycleRecord.id == bicycle_id,
            BicycleRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def list_by_customer(
        self, *, customer_id: str, organization_id: str, limit: int = 100
    ) -> list[Bicycle]:
        statement = (
            select(BicycleRecord)
            .where(
                BicycleRecord.customer_id == customer_id,
                BicycleRecord.organization_id == organization_id,
            )
            .order_by(BicycleRecord.brand, BicycleRecord.id)
            .limit(limit)
        )
        return [self._to_domain(record) for record in self._session.scalars(statement)]

    @staticmethod
    def _to_record(bicycle: Bicycle) -> BicycleRecord:
        return BicycleRecord(
            id=bicycle.bicycle_id,
            organization_id=bicycle.organization_id,
            location_id=bicycle.location_id,
            customer_id=bicycle.customer_id,
            brand=bicycle.brand,
            model=bicycle.model,
            bicycle_type=bicycle.bicycle_type,
            wheel_size=bicycle.wheel_size,
            notes=bicycle.notes,
            created_at=bicycle.created_at,
            updated_at=bicycle.updated_at,
            version=bicycle.version,
        )

    @staticmethod
    def _to_domain(record: BicycleRecord) -> Bicycle:
        return Bicycle(
            bicycle_id=record.id,
            customer_id=record.customer_id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            brand=record.brand,
            model=record.model,
            bicycle_type=record.bicycle_type,
            wheel_size=record.wheel_size,
            notes=record.notes,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            version=record.version,
        )
