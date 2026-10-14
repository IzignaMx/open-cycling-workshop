"""One versioned workshop brand per tenant/location, with private asset references."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


def _digest_check() -> str:
    remaining = "logo_sha256"
    for character in "0123456789abcdef":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"logo_sha256 IS NULL OR (length(logo_sha256) = 64 AND {remaining} = '')"


class WorkshopBrandProfileRecord(Base):
    __tablename__ = "workshop_brand_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_branding_location_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["updated_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_branding_actor_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("schema_version = 1", name="ck_branding_schema_version"),
        CheckConstraint("version > 0", name="ck_branding_version_positive"),
        CheckConstraint("length(display_name) BETWEEN 1 AND 160", name="ck_branding_display_name"),
        CheckConstraint(
            "palette_id IN "
            "('bosque','arcilla','tinta','cobalto','petroleo','indigo','malva','frambuesa','jade','lima','hielo','lavanda')",
            name="ck_branding_palette",
        ),
        CheckConstraint(
            "(logo_key IS NULL AND logo_sha256 IS NULL AND logo_byte_count IS NULL AND "
            "logo_width IS NULL AND logo_height IS NULL) OR (logo_key IS NOT NULL AND "
            "logo_sha256 IS NOT NULL AND logo_byte_count IS NOT NULL AND logo_width IS NOT "
            "NULL AND logo_height IS NOT NULL)",
            name="ck_branding_logo_complete",
        ),
        CheckConstraint(
            "logo_byte_count IS NULL OR logo_byte_count BETWEEN 1 AND 262144",
            name="ck_branding_logo_bytes",
        ),
        CheckConstraint(
            "logo_width IS NULL OR logo_width BETWEEN 1 AND 512", name="ck_branding_logo_width"
        ),
        CheckConstraint(
            "logo_height IS NULL OR logo_height BETWEEN 1 AND 512", name="ck_branding_logo_height"
        ),
        CheckConstraint(_digest_check(), name="ck_branding_logo_digest"),
        CheckConstraint(
            "logo_key IS NULL OR logo_key = substr(logo_sha256, 1, 2) || '/' || logo_sha256",
            name="ck_branding_logo_key",
        ),
    )
    organization_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    location_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    palette_id: Mapped[str] = mapped_column(String(16), nullable=False)
    logo_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    logo_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logo_byte_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logo_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logo_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
