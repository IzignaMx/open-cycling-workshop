"""Inventory: products and the append-only stock ledger.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("sku", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_product_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_product_tenant"),
        sa.UniqueConstraint("organization_id", "sku", name="uq_product_sku_per_org"),
    )
    op.create_index("ix_products_organization_id", "products", ["organization_id"])
    op.create_index("ix_products_org_name", "products", ["organization_id", "name"])

    op.create_table(
        "inventory_movements",
        sa.Column("movement_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(36), nullable=True),
        sa.Column("reference_movement_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_inventory_movement_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["products.id", "products.organization_id"],
            name="fk_inventory_movement_product_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_inventory_movements_product",
        "inventory_movements",
        ["organization_id", "product_id"],
    )
    op.create_index(
        "ix_inventory_movements_order",
        "inventory_movements",
        ["organization_id", "order_id"],
    )
    op.create_index(
        "ix_inventory_movements_reference",
        "inventory_movements",
        ["organization_id", "reference_movement_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_reference", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_order", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_product", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_products_org_name", table_name="products")
    op.drop_index("ix_products_organization_id", table_name="products")
    op.drop_table("products")
