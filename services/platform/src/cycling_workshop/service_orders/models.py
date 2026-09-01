from __future__ import annotations

from datetime import datetime

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


class ServiceOrderRecord(Base):
    __tablename__ = "service_orders"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_service_order_tenant"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_service_order_location_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["customer_id", "organization_id"],
            ["customers.id", "customers.organization_id"],
            name="fk_service_order_customer_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_service_orders_org_state", "organization_id", "state"),
        Index("ix_service_orders_org_customer", "organization_id", "customer_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False)
    bicycle_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("bicycles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    reported_problem: Mapped[str] = mapped_column(Text, nullable=False)
    intake_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    accessories: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ServiceOrderEventRecord(Base):
    """Append-only timeline: rows are only ever inserted, never updated."""

    __tablename__ = "service_order_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "organization_id"],
            ["service_orders.id", "service_orders.organization_id"],
            name="fk_service_order_event_order_tenant",
            ondelete="CASCADE",
        ),
        UniqueConstraint("order_id", "event_id", name="uq_service_order_event_order"),
        Index("ix_service_order_events_order", "order_id", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_state: Mapped[str] = mapped_column(String(30), nullable=False)
    to_state: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
