from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from cycling_workshop.service_orders.domain import ServiceOrder, ServiceOrderEvent
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyServiceOrderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, order: ServiceOrder) -> None:
        self._session.add(self._to_record(order))

    def save(self, order: ServiceOrder) -> None:
        record = self._session.get(ServiceOrderRecord, order.order_id)
        if record is None:
            self.add(order)
            return
        if record.organization_id != order.organization_id:
            raise ValueError("service order tenant cannot change")
        record.location_id = order.location_id
        record.customer_id = order.customer_id
        record.bicycle_id = order.bicycle_id
        record.state = order.state
        record.reported_problem = order.reported_problem
        record.intake_condition = order.intake_condition
        record.accessories = order.accessories
        record.priority = order.priority
        record.diagnosis = order.diagnosis
        record.updated_at = order.updated_at
        record.version = order.version

    def get(self, *, order_id: str, organization_id: str) -> ServiceOrder | None:
        statement: Select[tuple[ServiceOrderRecord]] = select(ServiceOrderRecord).where(
            ServiceOrderRecord.id == order_id,
            ServiceOrderRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        return self._to_domain(record) if record is not None else None

    def add_event(self, event: ServiceOrderEvent) -> None:
        self._session.add(
            ServiceOrderEventRecord(
                event_id=event.event_id,
                order_id=event.order_id,
                organization_id=event.organization_id,
                from_state=event.from_state,
                to_state=event.to_state,
                action=event.action,
                actor_id=event.actor_id,
                note=event.note,
                occurred_at=event.occurred_at,
            )
        )

    def list_events(
        self, *, order_id: str, organization_id: str, limit: int = 200
    ) -> list[ServiceOrderEvent]:
        statement = (
            select(ServiceOrderEventRecord)
            .where(
                ServiceOrderEventRecord.order_id == order_id,
                ServiceOrderEventRecord.organization_id == organization_id,
            )
            .order_by(ServiceOrderEventRecord.occurred_at, ServiceOrderEventRecord.event_id)
            .limit(limit)
        )
        return [
            ServiceOrderEvent(
                event_id=record.event_id,
                order_id=record.order_id,
                organization_id=record.organization_id,
                from_state=record.from_state,
                to_state=record.to_state,
                action=record.action,
                actor_id=record.actor_id,
                note=record.note,
                occurred_at=_as_utc(record.occurred_at),
            )
            for record in self._session.scalars(statement)
        ]

    @staticmethod
    def _to_record(order: ServiceOrder) -> ServiceOrderRecord:
        return ServiceOrderRecord(
            id=order.order_id,
            organization_id=order.organization_id,
            location_id=order.location_id,
            customer_id=order.customer_id,
            bicycle_id=order.bicycle_id,
            state=order.state,
            reported_problem=order.reported_problem,
            intake_condition=order.intake_condition,
            accessories=order.accessories,
            priority=order.priority,
            diagnosis=order.diagnosis,
            created_at=order.created_at,
            updated_at=order.updated_at,
            version=order.version,
        )

    @staticmethod
    def _to_domain(record: ServiceOrderRecord) -> ServiceOrder:
        return ServiceOrder(
            order_id=record.id,
            customer_id=record.customer_id,
            bicycle_id=record.bicycle_id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            state=record.state,
            reported_problem=record.reported_problem,
            intake_condition=record.intake_condition,
            accessories=record.accessories,
            priority=record.priority,
            diagnosis=record.diagnosis,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            version=record.version,
        )
