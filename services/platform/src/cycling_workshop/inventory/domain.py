from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum


def _now() -> datetime:
    return datetime.now(UTC)


def _required(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} must not be blank")
    return " ".join(value.split())


class MovementKind(StrEnum):
    ADJUST = "ADJUST"
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    CONSUME = "CONSUME"


_SIGNED_KINDS = {
    # kind -> effective sign of a positive input quantity on stock.
    # CONSUME finalizes a reservation: the hold already deducted the stock,
    # so consuming returns the hold (+n) instead of deducting twice. Direct
    # stock deductions use ADJUST, which accepts signed quantities as-is.
    MovementKind.RESERVE: -1,
    MovementKind.RELEASE: +1,
    MovementKind.CONSUME: +1,
}


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    organization_id: str
    location_id: str
    sku: str
    name: str
    unit: str
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        product_id: str,
        organization_id: str,
        location_id: str,
        sku: str,
        name: str,
        unit: str = "pieza",
        now: datetime | None = None,
    ) -> Product:
        timestamp = now or _now()
        return cls(
            product_id=_required(product_id, "product_id"),
            organization_id=_required(organization_id, "organization_id"),
            location_id=_required(location_id, "location_id"),
            sku=_required(sku, "sku").upper().replace(" ", "-"),
            name=_required(name, "name"),
            unit=_required(unit, "unit"),
            created_at=timestamp,
            updated_at=timestamp,
            version=1,
        )

    def rename(self, name: str, *, now: datetime | None = None) -> Product:
        return replace(
            self,
            name=_required(name, "name"),
            updated_at=now or _now(),
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class InventoryMovement:
    """Append-only stock ledger entry. Corrections are compensating
    movements; records are never updated or deleted."""

    movement_id: str
    product_id: str
    organization_id: str
    location_id: str
    kind: MovementKind
    quantity: int
    order_id: str | None
    reference_movement_id: str | None
    actor_id: str
    note: str | None
    occurred_at: datetime

    @classmethod
    def record(
        cls,
        *,
        movement_id: str,
        product_id: str,
        organization_id: str,
        location_id: str,
        kind: str,
        quantity: int,
        actor_id: str,
        order_id: str | None = None,
        reference_movement_id: str | None = None,
        note: str | None = None,
        previously_released: list[str] | None = None,
        now: datetime | None = None,
    ) -> InventoryMovement:
        try:
            parsed_kind = MovementKind(kind)
        except ValueError as exc:
            raise ValueError(f"unknown movement kind: {kind}") from exc

        if quantity == 0:
            raise ValueError("quantity must not be zero")
        if parsed_kind is not MovementKind.ADJUST and quantity < 0:
            raise ValueError(
                "quantity must be a positive integer; the kind determines the sign "
                "(only ADJUST accepts signed quantities)"
            )

        if parsed_kind is MovementKind.RESERVE and order_id is None:
            raise ValueError("reserve requires the order it holds stock for")

        if parsed_kind in (MovementKind.RELEASE, MovementKind.CONSUME):
            if reference_movement_id is None:
                raise ValueError(f"{parsed_kind.value.lower()} requires a reference reservation")
            if previously_released and reference_movement_id in previously_released:
                raise ValueError(f"reservation {reference_movement_id} already released")

        signed = (
            quantity
            if parsed_kind is MovementKind.ADJUST
            else quantity * _SIGNED_KINDS[parsed_kind]
        )

        return cls(
            movement_id=_required(movement_id, "movement_id"),
            product_id=_required(product_id, "product_id"),
            organization_id=_required(organization_id, "organization_id"),
            location_id=_required(location_id, "location_id"),
            kind=parsed_kind,
            quantity=signed,
            order_id=order_id,
            reference_movement_id=reference_movement_id,
            actor_id=_required(actor_id, "actor_id"),
            note=" ".join(note.split()) if note and note.strip() else None,
            occurred_at=now or _now(),
        )
