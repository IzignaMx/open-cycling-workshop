"""Add explicit owner identity, optimistic versions, and immutable audit history.

Revision ID: 0008
Revises: 0007

Existing grants, credentials, status, scope, and session versions are preserved.
No existing user is promoted to owner and no capability is granted implicitly.
Invalid legacy session versions require reviewed remediation before upgrading.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _create_audit_immutability_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_identity_audit_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Identity audit events are append-only' USING ERRCODE = '23514'; "
            "END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_identity_audit_immutable "
            "BEFORE UPDATE OR DELETE OR TRUNCATE ON identity_audit_events "
            "FOR EACH STATEMENT EXECUTE FUNCTION reject_identity_audit_mutation()"
        )
    elif dialect == "sqlite":
        # REPLACE can implicitly delete a conflicting row without DELETE
        # triggers when recursive_triggers is disabled (SQLite's default).
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
    if not context.is_offline_mode():
        invalid = (
            op.get_bind()
            .execute(sa.text("SELECT 1 FROM users WHERE session_version <= 0 LIMIT 1"))
            .first()
        )
        if invalid is not None:
            raise RuntimeError(
                "Identity migration 0008 blocked: invalid session versions exist. "
                "Take a verified backup and review affected identities before retrying. "
                "No users, grants, credentials, or session versions were changed."
            )

    # SQLite needs a table rebuild for the new constraints. Alembic preserves
    # the existing columns, foreign keys, indexes and rows during batch copy.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_users_version_positive", "version > 0")
        batch.create_check_constraint("ck_users_session_version_positive", "session_version > 0")
        batch.create_check_constraint(
            "ck_users_owner_organization_scope", "NOT is_owner OR location_id IS NULL"
        )
        batch.create_unique_constraint("uq_user_tenant", ["id", "organization_id"])

    op.create_table(
        "identity_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("target_type", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_identity_audit_actor_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_identity_audit_target_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "target_type IN ('user', 'location')", name="ck_identity_audit_target_type"
        ),
        sa.CheckConstraint(
            "target_type = 'user' OR target_id IS NULL", name="ck_identity_audit_target_reference"
        ),
    )
    op.create_index(
        "ix_identity_audit_org_time", "identity_audit_events", ["organization_id", "occurred_at"]
    )
    _create_audit_immutability_triggers()


def downgrade() -> None:
    # A schema rollback intentionally removes the new audit table and owner
    # metadata. It is an operator migration, never a supported audit API action.
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER trg_identity_audit_immutable ON identity_audit_events")
        op.execute("DROP FUNCTION reject_identity_audit_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER trg_identity_audit_no_replace")
        op.execute("DROP TRIGGER trg_identity_audit_no_update")
        op.execute("DROP TRIGGER trg_identity_audit_no_delete")
    op.drop_index("ix_identity_audit_org_time", table_name="identity_audit_events")
    op.drop_table("identity_audit_events")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_user_tenant", type_="unique")
        batch.drop_constraint("ck_users_owner_organization_scope", type_="check")
        batch.drop_constraint("ck_users_session_version_positive", type_="check")
        batch.drop_constraint("ck_users_version_positive", type_="check")
        batch.drop_column("version")
        batch.drop_column("is_owner")
