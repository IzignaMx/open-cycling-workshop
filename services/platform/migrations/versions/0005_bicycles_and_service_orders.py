"""Bicycles, service orders and append-only timeline events.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prerequisite for the composite tenant foreign keys added below (the
    # locations table already follows this pattern). Batch mode keeps SQLite
    # (test surrogate) compatible with the constraint ALTER.
    with op.batch_alter_table("customers") as batch:
        batch.create_unique_constraint("uq_customer_tenant", ["id", "organization_id"])

    op.create_table(
        "bicycles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("brand", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("bicycle_type", sa.String(60), nullable=True),
        sa.Column("wheel_size", sa.String(30), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_bicycle_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id", "organization_id"],
            ["customers.id", "customers.organization_id"],
            name="fk_bicycle_customer_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_bicycles_organization_id", "bicycles", ["organization_id"])
    op.create_index("ix_bicycles_org_customer", "bicycles", ["organization_id", "customer_id"])

    op.create_table(
        "service_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column(
            "bicycle_id",
            sa.String(36),
            sa.ForeignKey("bicycles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("reported_problem", sa.Text(), nullable=False),
        sa.Column("intake_condition", sa.Text(), nullable=True),
        sa.Column("accessories", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(30), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_service_order_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id", "organization_id"],
            ["customers.id", "customers.organization_id"],
            name="fk_service_order_customer_tenant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organization_id", name="uq_service_order_tenant"),
    )
    op.create_index("ix_service_orders_organization_id", "service_orders", ["organization_id"])
    op.create_index("ix_service_orders_org_state", "service_orders", ["organization_id", "state"])
    op.create_index(
        "ix_service_orders_org_customer", "service_orders", ["organization_id", "customer_id"]
    )

    op.create_table(
        "service_order_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("from_state", sa.String(30), nullable=False),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id", "organization_id"],
            ["service_orders.id", "service_orders.organization_id"],
            name="fk_service_order_event_order_tenant",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("order_id", "event_id", name="uq_service_order_event_order"),
    )
    op.create_index(
        "ix_service_order_events_order", "service_order_events", ["order_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_service_order_events_order", table_name="service_order_events")
    op.drop_table("service_order_events")
    op.drop_index("ix_service_orders_org_customer", table_name="service_orders")
    op.drop_index("ix_service_orders_org_state", table_name="service_orders")
    op.drop_index("ix_service_orders_organization_id", table_name="service_orders")
    op.drop_table("service_orders")
    op.drop_index("ix_bicycles_org_customer", table_name="bicycles")
    op.drop_index("ix_bicycles_organization_id", table_name="bicycles")
    op.drop_table("bicycles")
    with op.batch_alter_table("customers") as batch:
        batch.drop_constraint("uq_customer_tenant", type_="unique")
