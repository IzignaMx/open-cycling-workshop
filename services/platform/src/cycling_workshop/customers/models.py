from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


class CustomerRecord(Base):
    __tablename__ = "customers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_customer_location_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_customers_org_name", "organization_id", "display_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
