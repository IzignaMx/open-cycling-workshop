"""Add bounded authoritative pagination, preserving all existing business history.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name

    def byte_check(column: str, limit: int) -> str:
        size = (
            f"length(CAST({column} AS BLOB))" if dialect == "sqlite" else f"octet_length({column})"
        )
        return f"{size} <= {limit}"

    op.create_table(
        "sync_baseline_families",
        sa.Column("reference_hash", sa.String(64), primary_key=True),
        sa.Column("baseline_id", sa.String(36), nullable=False, unique=True),
        *[
            sa.Column(name, sa.String(36), nullable=False)
            for name in ("organization_id", "user_id", "location_id", "request_id")
        ],
        sa.Column("epoch", sa.String(64), nullable=False),
        *[
            sa.Column(name, sa.DateTime(timezone=True), nullable=False)
            for name in (
                "created_at",
                "baseline_expires_at",
                "family_expires_at",
                "retention_until",
            )
        ],
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("start_json", sa.Text(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("predecessor_hash", sa.String(64), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("activation_hash", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_baseline_user_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_baseline_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("sequence >= 0", name="ck_baseline_sequence_positive"),
        sa.CheckConstraint("sequence <= 9007199254740991", name="ck_baseline_sequence_safe"),
        *[
            sa.CheckConstraint(byte_check(column, limit), name=f"ck_baseline_{label}_bytes")
            for column, limit, label in (
                ("start_json", 16384, "start"),
                ("state_json", 16384, "state"),
                ("response_json", 1048576, "response"),
            )
        ],
    )
    op.create_index(
        "uq_baseline_start",
        "sync_baseline_families",
        ["organization_id", "user_id", "location_id", "epoch", "request_id"],
        unique=True,
    )
    op.create_index(
        "ix_baseline_org_user_location",
        "sync_baseline_families",
        ["organization_id", "user_id", "location_id", "phase"],
    )
    op.create_index(
        "ix_baseline_org_retention",
        "sync_baseline_families",
        ["organization_id", "retention_until"],
    )
    op.create_index("ix_baseline_user", "sync_baseline_families", ["user_id"])
    for table in ("customers", "bicycles", "service_orders"):
        collated = sa.text('id COLLATE "C"') if dialect == "postgresql" else "id"
        op.create_index(
            f"ix_{table}_baseline_scan", table, ["organization_id", "location_id", collated]
        )
    op.create_index(
        "ix_sync_changes_org_location_type_cursor",
        "sync_changes",
        ["organization_id", "location_id", "entity_type", "cursor"],
    )


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Baseline downgrade requires an online emptiness check.")
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Held through Alembic's migration transaction: no family can appear
        # between the emptiness check and dropping metadata. Maintenance only.
        connection.execute(sa.text("LOCK TABLE sync_baseline_families IN ACCESS EXCLUSIVE MODE"))
    if (
        connection.execute(sa.text("SELECT 1 FROM sync_baseline_families LIMIT 1")).first()
        is not None
    ):
        raise RuntimeError("Baseline proofs remain; use a schema-compatible rollback.")
    op.drop_index("ix_sync_changes_org_location_type_cursor", table_name="sync_changes")
    for table in ("customers", "bicycles", "service_orders"):
        op.drop_index(f"ix_{table}_baseline_scan", table_name=table)
    op.drop_table("sync_baseline_families")
