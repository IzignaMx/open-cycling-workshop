"""Add sync mutation receipts and change feed.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_mutation_receipts",
        sa.Column("mutation_id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_sync_mutation_receipts_organization_id", "sync_mutation_receipts", ["organization_id"]
    )
    op.create_index(
        "ix_sync_receipts_org_entity",
        "sync_mutation_receipts",
        ["organization_id", "entity_type", "entity_id"],
    )
    op.create_table(
        "sync_changes",
        sa.Column("cursor", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=24), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_sync_changes_org_cursor", "sync_changes", ["organization_id", "cursor"])
    op.create_index(
        "ix_sync_changes_org_location_cursor",
        "sync_changes",
        ["organization_id", "location_id", "cursor"],
    )


def downgrade() -> None:
    op.drop_index("ix_sync_changes_org_location_cursor", table_name="sync_changes")
    op.drop_index("ix_sync_changes_org_cursor", table_name="sync_changes")
    op.drop_table("sync_changes")
    op.drop_index("ix_sync_receipts_org_entity", table_name="sync_mutation_receipts")
    op.drop_index("ix_sync_mutation_receipts_organization_id", table_name="sync_mutation_receipts")
    op.drop_table("sync_mutation_receipts")
