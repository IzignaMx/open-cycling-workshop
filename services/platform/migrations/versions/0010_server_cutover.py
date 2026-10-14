"""Persist the forward-only server cutover and authenticated receipt proofs.

Revision ID: 0010
Revises: 0009

Run only with every writer drained. This schema cannot fence older binaries.
Existing columns and historical values are preserved, including legacy receipts.
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import context, op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _hex_only(expression: str) -> str:
    for character in "0123456789abcdef":
        expression = f"replace({expression}, '{character}', '')"
    return f"{expression} = ''"


def _restore_sqlite_audit_guards() -> None:
    op.execute(
        "CREATE TRIGGER trg_identity_audit_no_replace "
        "BEFORE INSERT ON identity_audit_events FOR EACH ROW "
        "WHEN EXISTS (SELECT 1 FROM identity_audit_events WHERE id = NEW.id) BEGIN "
        "SELECT RAISE(ABORT, 'Identity audit events are append-only'); END"
    )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER trg_identity_audit_no_{operation.lower()} "
            f"BEFORE {operation} ON identity_audit_events FOR EACH ROW BEGIN "
            "SELECT RAISE(ABORT, 'Identity audit events are append-only'); END"
        )


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Cutover migration requires online per-organization initialization.")
    connection = op.get_bind()
    op.add_column(
        "organizations",
        sa.Column("minimum_write_protocol", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("organizations", sa.Column("dataset_incarnation", sa.String(36), nullable=True))
    # Never derive provenance from preexisting history or use one installation-wide
    # value. No ordinary request creates missing metadata after this migration.
    for organization_id in connection.scalars(sa.text("SELECT id FROM organizations")):
        connection.execute(
            sa.text("UPDATE organizations SET dataset_incarnation=:incarnation WHERE id=:id"),
            {"id": organization_id, "incarnation": str(uuid4())},
        )
    with op.batch_alter_table("organizations") as batch:
        batch.alter_column("dataset_incarnation", existing_type=sa.String(36), nullable=False)
        batch.create_check_constraint(
            "ck_organizations_write_protocol", "minimum_write_protocol IN (0, 1)"
        )
        batch.create_check_constraint(
            "ck_organizations_dataset_incarnation",
            "length(dataset_incarnation) = 36 AND "
            "substr(dataset_incarnation, 9, 1) = '-' AND "
            "substr(dataset_incarnation, 14, 1) = '-' AND "
            "substr(dataset_incarnation, 19, 1) = '-' AND "
            "substr(dataset_incarnation, 24, 1) = '-' AND "
            "length(replace(dataset_incarnation, '-', '')) = 32 AND "
            + _hex_only("replace(dataset_incarnation, '-', '')"),
        )
    with op.batch_alter_table("sync_mutation_receipts") as batch:
        batch.add_column(sa.Column("actor_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("command_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("proof_version", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_sync_receipt_proof_complete",
            "(actor_id IS NULL AND command_digest IS NULL AND proof_version IS NULL) OR "
            "(actor_id IS NOT NULL AND command_digest IS NOT NULL AND proof_version IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_sync_receipt_proof_version", "proof_version IS NULL OR proof_version = 1"
        )
        batch.create_check_constraint(
            "ck_sync_receipt_proof_digest",
            "command_digest IS NULL OR (length(command_digest) = 64 AND "
            + _hex_only("command_digest")
            + ")",
        )
    with op.batch_alter_table("identity_audit_events") as batch:
        batch.drop_constraint("ck_identity_audit_target_type", type_="check")
        batch.create_check_constraint(
            "ck_identity_audit_target_type", "target_type IN ('user', 'location', 'organization')"
        )
    if connection.dialect.name == "sqlite":
        # Batch rebuild removes triggers. Reinstall every original append-only
        # guard, including protection against INSERT OR REPLACE's implicit delete.
        _restore_sqlite_audit_guards()


def downgrade() -> None:
    # Deliberately unconditional and before any database access or DDL/DML.
    raise RuntimeError(
        "Cutover migration 0010 is forward-only; use a schema-compatible rollback or forward fix."
    )
