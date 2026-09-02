from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from cycling_workshop.inventory.domain import InventoryMovement, Product
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyInventoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # products -------------------------------------------------------------

    def add_product(self, product: Product) -> None:
        self._session.add(
            ProductRecord(
                id=product.product_id,
                organization_id=product.organization_id,
                location_id=product.location_id,
                sku=product.sku,
                name=product.name,
                unit=product.unit,
                created_at=product.created_at,
                updated_at=product.updated_at,
                version=product.version,
            )
        )

    def get_product(self, *, product_id: str, organization_id: str) -> Product | None:
        statement: Select[tuple[ProductRecord]] = select(ProductRecord).where(
            ProductRecord.id == product_id,
            ProductRecord.organization_id == organization_id,
        )
        record = self._session.scalar(statement)
        if record is None:
            return None
        return Product(
            product_id=record.id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            sku=record.sku,
            name=record.name,
            unit=record.unit,
            created_at=_as_utc(record.created_at),
            updated_at=_as_utc(record.updated_at),
            version=record.version,
        )

    # ledger ---------------------------------------------------------------

    def record(self, movement: InventoryMovement) -> InventoryMovement:
        self._session.add(
            InventoryMovementRecord(
                movement_id=movement.movement_id,
                organization_id=movement.organization_id,
                location_id=movement.location_id,
                product_id=movement.product_id,
                kind=movement.kind.value,
                quantity=movement.quantity,
                order_id=movement.order_id,
                reference_movement_id=movement.reference_movement_id,
                actor_id=movement.actor_id,
                note=movement.note,
                occurred_at=movement.occurred_at,
            )
        )
        return movement

    def available_quantity(self, *, product_id: str, organization_id: str) -> int:
        total = self._session.scalar(
            select(func.coalesce(func.sum(InventoryMovementRecord.quantity), 0)).where(
                InventoryMovementRecord.product_id == product_id,
                InventoryMovementRecord.organization_id == organization_id,
            )
        )
        return int(total or 0)

    def list_by_product(
        self, *, product_id: str, organization_id: str, limit: int = 200
    ) -> list[InventoryMovement]:
        statement = (
            select(InventoryMovementRecord)
            .where(
                InventoryMovementRecord.product_id == product_id,
                InventoryMovementRecord.organization_id == organization_id,
            )
            .order_by(InventoryMovementRecord.occurred_at, InventoryMovementRecord.movement_id)
            .limit(limit)
        )
        return [self._to_domain(record) for record in self._session.scalars(statement)]

    def list_by_order(
        self, *, order_id: str, organization_id: str, limit: int = 200
    ) -> list[InventoryMovement]:
        statement = (
            select(InventoryMovementRecord)
            .where(
                InventoryMovementRecord.order_id == order_id,
                InventoryMovementRecord.organization_id == organization_id,
            )
            .order_by(InventoryMovementRecord.occurred_at, InventoryMovementRecord.movement_id)
            .limit(limit)
        )
        return [self._to_domain(record) for record in self._session.scalars(statement)]

    def released_reservation_ids(
        self, *, organization_id: str, reference_movement_id: str
    ) -> list[str]:
        statement = select(InventoryMovementRecord.movement_id).where(
            InventoryMovementRecord.organization_id == organization_id,
            InventoryMovementRecord.reference_movement_id == reference_movement_id,
            InventoryMovementRecord.kind == "RELEASE",
        )
        return list(self._session.scalars(statement))

    @staticmethod
    def _to_domain(record: InventoryMovementRecord) -> InventoryMovement:
        from cycling_workshop.inventory.domain import MovementKind

        return InventoryMovement(
            movement_id=record.movement_id,
            product_id=record.product_id,
            organization_id=record.organization_id,
            location_id=record.location_id,
            kind=MovementKind(record.kind),
            quantity=record.quantity,
            order_id=record.order_id,
            reference_movement_id=record.reference_movement_id,
            actor_id=record.actor_id,
            note=record.note,
            occurred_at=_as_utc(record.occurred_at),
        )
