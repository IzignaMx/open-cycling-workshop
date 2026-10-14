"""Add shared workshop branding without backfilling profiles or changing grants.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _digest_check() -> str:
    remaining = "logo_sha256"
    for character in "0123456789abcdef":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"logo_sha256 IS NULL OR (length(logo_sha256) = 64 AND {remaining} = '')"


def upgrade() -> None:
    op.create_table(
        "workshop_brand_profiles",
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("palette_id", sa.String(16), nullable=False),
        sa.Column("logo_key", sa.String(128), nullable=True),
        sa.Column("logo_sha256", sa.String(64), nullable=True),
        sa.Column("logo_byte_count", sa.Integer(), nullable=True),
        sa.Column("logo_width", sa.Integer(), nullable=True),
        sa.Column("logo_height", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", "location_id"),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_branding_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_branding_actor_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("schema_version = 1", name="ck_branding_schema_version"),
        sa.CheckConstraint("version > 0", name="ck_branding_version_positive"),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 160", name="ck_branding_display_name"
        ),
        sa.CheckConstraint(
            "palette_id IN "
            "('bosque','arcilla','tinta','cobalto','petroleo','indigo','malva','frambuesa','jade','lima','hielo','lavanda')",
            name="ck_branding_palette",
        ),
        sa.CheckConstraint(
            "(logo_key IS NULL AND logo_sha256 IS NULL AND logo_byte_count IS NULL AND "
            "logo_width IS NULL AND logo_height IS NULL) OR (logo_key IS NOT NULL AND "
            "logo_sha256 IS NOT NULL AND logo_byte_count IS NOT NULL AND logo_width IS NOT "
            "NULL AND logo_height IS NOT NULL)",
            name="ck_branding_logo_complete",
        ),
        sa.CheckConstraint(
            "logo_byte_count IS NULL OR logo_byte_count BETWEEN 1 AND 262144",
            name="ck_branding_logo_bytes",
        ),
        sa.CheckConstraint(
            "logo_width IS NULL OR logo_width BETWEEN 1 AND 512", name="ck_branding_logo_width"
        ),
        sa.CheckConstraint(
            "logo_height IS NULL OR logo_height BETWEEN 1 AND 512", name="ck_branding_logo_height"
        ),
        sa.CheckConstraint(_digest_check(), name="ck_branding_logo_digest"),
        sa.CheckConstraint(
            "logo_key IS NULL OR logo_key = substr(logo_sha256, 1, 2) || '/' || logo_sha256",
            name="ck_branding_logo_key",
        ),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Branding migration 0011 is forward-only; use a compatible rollback or forward fix."
    )
