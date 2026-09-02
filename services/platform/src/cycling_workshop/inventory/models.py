from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


class ProductRecord(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_product_tenant"),
        UniqueConstraint("organization_id", "sku", name="uq_product_sku_per_org"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_product_location_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_products_org_name", "organization_id", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="pieza")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class InventoryMovementRecord(Base):
    """Append-only stock ledger: rows are only ever inserted."""

    __tablename__ = "inventory_movements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_inventory_movement_location_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["products.id", "products.organization_id"],
            name="fk_inventory_movement_product_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_inventory_movements_product", "organization_id", "product_id"),
        Index("ix_inventory_movements_order", "organization_id", "order_id"),
        Index(
            "ix_inventory_movements_reference",
            "organization_id",
            "reference_movement_id",
        ),
    )

    movement_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference_movement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
