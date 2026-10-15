"""Bounded public ledger projection, separate from command/domain hydration."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from cycling_workshop.inventory.cursor import (
    InventoryCursor,
    canonical_timestamp,
    encode_cursor,
    parse_timestamp,
)
from cycling_workshop.inventory.models import InventoryMovementRecord
from cycling_workshop.inventory.schemas import (
    InventoryMovementPageResponse,
    InventoryMovementReadResponse,
)


def movement_statement(
    *,
    organization_id: str,
    location_id: str,
    product_id: str,
    limit: int,
    before: InventoryCursor | None,
    dialect: str,
) -> Select[tuple[str, str, str, str, str, int, datetime]]:
    ledger = InventoryMovementRecord
    # UTF-8 binary ordering equals Unicode code-point ordering for scalar text.
    # Apply the SAME explicit collation in both ORDER and cursor predicate.
    movement_id = ledger.movement_id.collate("C" if dialect == "postgresql" else "BINARY")
    statement = select(
        ledger.movement_id,
        ledger.product_id,
        ledger.organization_id,
        ledger.location_id,
        ledger.kind,
        ledger.quantity,
        ledger.occurred_at,
    ).where(
        ledger.organization_id == organization_id,
        ledger.location_id == location_id,
        ledger.product_id == product_id,
    )
    if before is not None:
        timestamp = parse_timestamp(before.before_occurred_at)
        statement = statement.where(
            or_(
                ledger.occurred_at < timestamp,
                and_(ledger.occurred_at == timestamp, movement_id < before.before_movement_id),
            )
        )
    return statement.order_by(ledger.occurred_at.desc(), movement_id.desc()).limit(limit + 1)


def read_movement_page(
    session: Session,
    *,
    organization_id: str,
    location_id: str,
    product_id: str,
    limit: int,
    before: InventoryCursor | None,
) -> InventoryMovementPageResponse:
    rows = (
        session.execute(
            movement_statement(
                organization_id=organization_id,
                location_id=location_id,
                product_id=product_id,
                limit=limit,
                before=before,
                dialect=session.get_bind().dialect.name,
            )
        )
        .mappings()
        .all()
    )
    items = [
        InventoryMovementReadResponse(
            movement_id=row["movement_id"],
            product_id=row["product_id"],
            organization_id=row["organization_id"],
            location_id=row["location_id"],
            kind=row["kind"],
            quantity=row["quantity"],
            occurred_at=canonical_timestamp(row["occurred_at"]),
        )
        for row in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        next_cursor = encode_cursor(
            InventoryCursor(
                organization_id=organization_id,
                location_id=location_id,
                product_id=product_id,
                before_occurred_at=last.occurred_at,
                before_movement_id=last.movement_id,
            )
        )
    return InventoryMovementPageResponse(items=items, next_cursor=next_cursor)
