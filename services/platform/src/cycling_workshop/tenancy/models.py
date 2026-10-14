from __future__ import annotations

from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cycling_workshop.db.base import Base


def _incarnation_check() -> str:
    hex_only = "replace(dataset_incarnation, '-', '')"
    for character in "0123456789abcdef":
        hex_only = f"replace({hex_only}, '{character}', '')"
    return (
        "length(dataset_incarnation) = 36 AND "
        "substr(dataset_incarnation, 9, 1) = '-' AND "
        "substr(dataset_incarnation, 14, 1) = '-' AND "
        "substr(dataset_incarnation, 19, 1) = '-' AND "
        "substr(dataset_incarnation, 24, 1) = '-' AND "
        "length(replace(dataset_incarnation, '-', '')) = 32 AND "
        f"{hex_only} = ''"
    )


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("minimum_write_protocol IN (0, 1)", name="ck_organizations_write_protocol"),
        CheckConstraint(_incarnation_check(), name="ck_organizations_dataset_incarnation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    minimum_write_protocol: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    dataset_incarnation: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid4())
    )

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
