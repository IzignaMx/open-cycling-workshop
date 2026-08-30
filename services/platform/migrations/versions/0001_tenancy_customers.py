"""Create organizations, locations, and customers.

Revision ID: 0001
Revises: None
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
    )
    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "organization_id", name="uq_location_tenant"),
    )
    op.create_index("ix_locations_organization_id", "locations", ["organization_id"])
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_customer_location_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_customers_organization_id", "customers", ["organization_id"])
    op.create_index("ix_customers_org_name", "customers", ["organization_id", "display_name"])


def downgrade() -> None:
    op.drop_index("ix_customers_org_name", table_name="customers")
    op.drop_index("ix_customers_organization_id", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_locations_organization_id", table_name="locations")
    op.drop_table("locations")
    op.drop_table("organizations")
