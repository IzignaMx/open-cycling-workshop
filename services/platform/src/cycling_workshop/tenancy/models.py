from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cycling_workshop.db.base import Base


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    locations: Mapped[list[LocationRecord]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class LocationRecord(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_location_tenant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    organization: Mapped[OrganizationRecord] = relationship(back_populates="locations")
