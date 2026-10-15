"""Add immutable quote history and terminal operation receipts, without activation.

Revision ID: 0012
Revises: 0011

No quote routes, capabilities, backfill, enrollment or existing grants are changed.
All table definitions are frozen here, independent of future ORM model changes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _currency_check() -> str:
    # Exact ASCII membership, independent of a PostgreSQL locale collation.
    remaining = "currency"
    for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"length(currency) = 3 AND {remaining} = ''"


def _lineage_revision_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["root_quote_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_lineage_root",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["head_quote_id", "lineage_id", "organization_id", "head_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_lineage_head",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
    ]


def upgrade() -> None:
    op.create_index(
        "uq_service_order_scope",
        "service_orders",
        ["id", "organization_id", "location_id"],
        unique=True,
    )
    op.create_table(
        "quote_lineages",
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("root_quote_id", sa.String(length=36), nullable=False),
        sa.Column("head_quote_id", sa.String(length=36), nullable=False),
        sa.Column("head_version", sa.BigInteger(), nullable=False),
        sa.Column("decision_sequence", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(_currency_check(), name="ck_quote_lineage_currency"),
        sa.CheckConstraint(
            "decision_sequence BETWEEN 0 AND 9007199254740991", name="ck_quote_lineage_sequence"
        ),
        sa.CheckConstraint(
            "head_version BETWEEN 1 AND 9007199254740991", name="ck_quote_lineage_head_version"
        ),
        sa.CheckConstraint("root_quote_id = lineage_id", name="ck_quote_lineage_root"),
        sa.ForeignKeyConstraint(
            ["order_id", "organization_id", "location_id"],
            ["service_orders.id", "service_orders.organization_id", "service_orders.location_id"],
            name="fk_quote_lineage_order_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        *(_lineage_revision_constraints() if op.get_bind().dialect.name == "sqlite" else []),
        sa.PrimaryKeyConstraint("lineage_id"),
        sa.UniqueConstraint("lineage_id", "organization_id", name="uq_quote_lineage_tenant"),
        sa.UniqueConstraint("organization_id", "order_id", name="uq_quote_lineage_order"),
    )
    op.create_table(
        "quote_revisions",
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("predecessor_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tax_minor", sa.BigInteger(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("line_amounts", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "(version = 1 AND predecessor_id IS NULL AND quote_id = lineage_id) OR "
            "(version > 1 AND predecessor_id IS NOT NULL AND quote_id <> lineage_id AND "
            "quote_id <> predecessor_id)",
            name="ck_quote_revision_root",
        ),
        sa.CheckConstraint(
            "discount_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_revision_discount_minor"
        ),
        sa.CheckConstraint(
            "subtotal_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_revision_subtotal_minor"
        ),
        sa.CheckConstraint(
            "tax_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_revision_tax_minor"
        ),
        sa.CheckConstraint(
            "total_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_revision_total_minor"
        ),
        sa.CheckConstraint(
            "version BETWEEN 1 AND 9007199254740991", name="ck_quote_revision_version"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_revision_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lineage_id", "organization_id"],
            ["quote_lineages.lineage_id", "quote_lineages.organization_id"],
            name="fk_quote_revision_lineage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_revision_predecessor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("quote_id"),
        sa.UniqueConstraint("lineage_id", "version", name="uq_quote_revision_version"),
        sa.UniqueConstraint("predecessor_id", name="uq_quote_revision_successor"),
        sa.UniqueConstraint(
            "quote_id",
            "lineage_id",
            "organization_id",
            "version",
            name="uq_quote_revision_scope_version",
        ),
        sa.UniqueConstraint(
            "quote_id", "lineage_id", "organization_id", name="uq_quote_revision_scope"
        ),
    )
    op.create_table(
        "quote_lines",
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("line_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("hourly_rate_minor", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("rate_bps", sa.Integer(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "(kind = 'labor' AND minutes IS NOT NULL AND hourly_rate_minor IS NOT NULL "
            "AND product_id IS NULL AND quantity IS NULL AND unit_price_minor IS NULL "
            "AND rate_bps IS NULL AND amount_minor IS NULL) OR (kind = 'part' AND "
            "product_id IS NOT NULL AND quantity IS NOT NULL AND unit_price_minor IS NOT "
            "NULL AND minutes IS NULL AND hourly_rate_minor IS NULL AND rate_bps IS NULL "
            "AND amount_minor IS NULL) OR (kind = 'tax' AND rate_bps IS NOT NULL AND "
            "product_id IS NULL AND quantity IS NULL AND unit_price_minor IS NULL AND "
            "minutes IS NULL AND hourly_rate_minor IS NULL AND amount_minor IS NULL) OR "
            "(kind = 'discount' AND amount_minor IS NOT NULL AND product_id IS NULL AND "
            "quantity IS NULL AND unit_price_minor IS NULL AND minutes IS NULL AND "
            "hourly_rate_minor IS NULL AND rate_bps IS NULL)",
            name="ck_quote_line_kind_fields",
        ),
        sa.CheckConstraint(
            "amount_minor BETWEEN 1 AND 9007199254740991", name="ck_quote_line_discount"
        ),
        sa.CheckConstraint(
            "hourly_rate_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_line_hourly_rate"
        ),
        sa.CheckConstraint(
            "length(description) BETWEEN 1 AND 500", name="ck_quote_line_description"
        ),
        sa.CheckConstraint("minutes BETWEEN 1 AND 1000000", name="ck_quote_line_minutes"),
        sa.CheckConstraint("position BETWEEN 0 AND 99", name="ck_quote_line_position"),
        sa.CheckConstraint("quantity BETWEEN 1 AND 1000000", name="ck_quote_line_quantity"),
        sa.CheckConstraint("rate_bps BETWEEN 0 AND 10000", name="ck_quote_line_rate"),
        sa.CheckConstraint(
            "unit_price_minor BETWEEN 0 AND 9007199254740991", name="ck_quote_line_unit_price"
        ),
        sa.ForeignKeyConstraint(
            ["product_id", "organization_id"],
            ["products.id", "products.organization_id"],
            name="fk_quote_line_product",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "lineage_id", "organization_id"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
            ],
            name="fk_quote_line_revision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("revision_id", "line_id"),
        sa.UniqueConstraint("revision_id", "position", name="uq_quote_line_position"),
    )
    op.create_table(
        "quote_line_targets",
        sa.Column("revision_id", sa.String(length=36), nullable=False),
        sa.Column("source_line_id", sa.String(length=36), nullable=False),
        sa.Column("target_line_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("source_line_id <> target_line_id", name="ck_quote_target_distinct"),
        sa.ForeignKeyConstraint(
            ["revision_id", "source_line_id"],
            ["quote_lines.revision_id", "quote_lines.line_id"],
            name="fk_quote_target_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revision_id", "target_line_id"],
            ["quote_lines.revision_id", "quote_lines.line_id"],
            name="fk_quote_target_target",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("revision_id", "source_line_id", "target_line_id"),
    )
    op.create_table(
        "quote_decisions",
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("quote_version", sa.BigInteger(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("supersedes_entry_id", sa.String(length=36), nullable=True),
        sa.Column("line_decisions", sa.JSON(), nullable=False),
        sa.Column("pricing", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "quote_version BETWEEN 1 AND 9007199254740991", name="ck_quote_decision_version"
        ),
        sa.CheckConstraint(
            "reason IS NULL OR length(reason) BETWEEN 1 AND 500", name="ck_quote_decision_reason"
        ),
        sa.CheckConstraint(
            "sequence BETWEEN 1 AND 9007199254740991", name="ck_quote_decision_sequence"
        ),
        sa.CheckConstraint(
            "supersedes_entry_id IS NULL OR supersedes_entry_id <> decision_id",
            name="ck_quote_decision_distinct",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_decision_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id", "lineage_id", "organization_id", "quote_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_decision_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_entry_id", "lineage_id", "organization_id", "quote_id", "quote_version"],
            [
                "quote_decisions.decision_id",
                "quote_decisions.lineage_id",
                "quote_decisions.organization_id",
                "quote_decisions.quote_id",
                "quote_decisions.quote_version",
            ],
            name="fk_quote_decision_predecessor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "decision_id",
            "lineage_id",
            "organization_id",
            "quote_id",
            "quote_version",
            name="uq_quote_decision_scope",
        ),
        sa.UniqueConstraint("lineage_id", "sequence", name="uq_quote_decision_sequence"),
        sa.UniqueConstraint("supersedes_entry_id", name="uq_quote_decision_successor"),
    )
    op.create_table(
        "quote_operations",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("quote_version", sa.BigInteger(), nullable=False),
        sa.Column("resulting_decision_sequence", sa.BigInteger(), nullable=False),
        sa.Column("ordinal", sa.BigInteger(), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=True),
        sa.Column("proof_version", sa.Integer(), nullable=False),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quote_outbox_id", sa.String(length=36), nullable=False),
        sa.Column("order_event_id", sa.String(length=36), nullable=True),
        sa.Column("resulting_order_version", sa.BigInteger(), nullable=True),
        sa.Column("change_cursor", sa.BigInteger(), nullable=True),
        sa.Column("order_outbox_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "(kind = 'create' AND quote_version = 1 AND resulting_decision_sequence = 0 "
            "AND decision_id IS NULL) OR (kind = 'revise' AND quote_version > 1 AND "
            "decision_id IS NULL) OR (kind = 'decision' AND decision_id IS NOT NULL AND "
            "decision_id = operation_id AND resulting_decision_sequence > 0)",
            name="ck_quote_operation_result",
        ),
        sa.CheckConstraint(
            "(order_event_id IS NULL AND resulting_order_version IS NULL AND "
            "change_cursor IS NULL AND order_outbox_id IS NULL) OR (kind = 'decision' "
            "AND order_event_id IS NOT NULL AND resulting_order_version IS NOT NULL AND "
            "change_cursor IS NOT NULL AND order_outbox_id IS NOT NULL)",
            name="ck_quote_operation_order_effects",
        ),
        sa.CheckConstraint(
            "change_cursor BETWEEN 1 AND 9007199254740991", name="ck_quote_operation_cursor"
        ),
        sa.CheckConstraint(
            "order_outbox_id IS NULL OR order_outbox_id <> quote_outbox_id",
            name="ck_quote_operation_distinct_outboxes",
        ),
        sa.CheckConstraint(
            "ordinal BETWEEN 1 AND 9007199254740991 AND ordinal = quote_version + "
            "resulting_decision_sequence",
            name="ck_quote_operation_ordinal",
        ),
        sa.CheckConstraint("proof_version = 1", name="ck_quote_operation_proof_version"),
        sa.CheckConstraint(
            "quote_version BETWEEN 1 AND 9007199254740991", name="ck_quote_operation_version"
        ),
        sa.CheckConstraint(
            "resulting_decision_sequence BETWEEN 0 AND 9007199254740991",
            name="ck_quote_operation_sequence",
        ),
        sa.CheckConstraint(
            "resulting_order_version BETWEEN 1 AND 9007199254740991",
            name="ck_quote_operation_order_version",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_quote_operation_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["change_cursor"], ["sync_changes.cursor"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["decision_id", "lineage_id", "organization_id", "quote_id", "quote_version"],
            [
                "quote_decisions.decision_id",
                "quote_decisions.lineage_id",
                "quote_decisions.organization_id",
                "quote_decisions.quote_id",
                "quote_decisions.quote_version",
            ],
            name="fk_quote_operation_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_event_id"], ["service_order_events.event_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_outbox_id"], ["outbox_events.event_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quote_id", "lineage_id", "organization_id", "quote_version"],
            [
                "quote_revisions.quote_id",
                "quote_revisions.lineage_id",
                "quote_revisions.organization_id",
                "quote_revisions.version",
            ],
            name="fk_quote_operation_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quote_outbox_id"], ["outbox_events.event_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("organization_id", "operation_id"),
        sa.UniqueConstraint("change_cursor", name="uq_quote_operation_change"),
        sa.UniqueConstraint("decision_id", name="uq_quote_operation_decision"),
        sa.UniqueConstraint("lineage_id", "ordinal", name="uq_quote_operation_ordinal"),
        sa.UniqueConstraint("order_event_id", name="uq_quote_operation_order_event"),
        sa.UniqueConstraint("order_outbox_id", name="uq_quote_operation_order_outbox"),
        sa.UniqueConstraint("quote_outbox_id", name="uq_quote_operation_outbox"),
    )

    if op.get_bind().dialect.name == "postgresql":
        # The cyclic tables exist before PostgreSQL adds the deferred root/head links.
        for constraint in _lineage_revision_constraints():
            op.create_foreign_key(
                constraint.name,
                "quote_lineages",
                "quote_revisions",
                constraint.column_keys,
                [element.target_fullname.rsplit(".", 1)[1] for element in constraint.elements],
                ondelete="RESTRICT",
                deferrable=True,
                initially="DEFERRED",
            )
    _install_retention_guards()


def downgrade() -> None:
    raise RuntimeError(
        "Quote migration 0012 is forward-only; preserve evidence with a compatible "
        "rollback or forward fix."
    )


# Every unique conflict is protected, including SQLite INSERT OR REPLACE when
# recursive_triggers is off. A conflict may not silently remove an older record.
_UNIQUE_KEYS = {
    "quote_lineages": (("lineage_id",), ("organization_id", "order_id")),
    "quote_revisions": (("quote_id",), ("lineage_id", "version"), ("predecessor_id",)),
    "quote_lines": (("revision_id", "line_id"), ("revision_id", "position")),
    "quote_line_targets": (("revision_id", "source_line_id", "target_line_id"),),
    "quote_decisions": (("decision_id",), ("lineage_id", "sequence"), ("supersedes_entry_id",)),
    "quote_operations": (
        ("organization_id", "operation_id"),
        ("lineage_id", "ordinal"),
        ("quote_outbox_id",),
        ("order_event_id",),
        ("order_outbox_id",),
        ("change_cursor",),
        ("decision_id",),
    ),
}
_LINEAGE_IMMUTABLE = (
    "lineage_id",
    "organization_id",
    "location_id",
    "order_id",
    "currency",
    "root_quote_id",
)


def _install_retention_guards() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION reject_quote_history_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'Quote history is append-only' USING ERRCODE = '23514'; "
            "END; $$"
        )
        for table in _UNIQUE_KEYS:
            operations = (
                "DELETE OR TRUNCATE"
                if table == "quote_lineages"
                else "UPDATE OR DELETE OR TRUNCATE"
            )
            op.execute(
                f"CREATE TRIGGER trg_{table}_immutable BEFORE {operations} ON {table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION reject_quote_history_mutation()"
            )
        changed = " OR ".join(
            f"NEW.{column} IS DISTINCT FROM OLD.{column}" for column in _LINEAGE_IMMUTABLE
        )
        op.execute(
            "CREATE FUNCTION reject_quote_lineage_identity_update() RETURNS trigger "
            f"LANGUAGE plpgsql AS $$ BEGIN IF {changed} THEN "
            "RAISE EXCEPTION 'Quote lineage identity is immutable' USING ERRCODE = '23514'; "
            "END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER trg_quote_lineage_identity BEFORE UPDATE ON quote_lineages "
            "FOR EACH ROW EXECUTE FUNCTION reject_quote_lineage_identity_update()"
        )
    elif dialect == "sqlite":
        for table, keys in _UNIQUE_KEYS.items():
            conflicts = " OR ".join(
                "(" + " AND ".join(f"{column} = NEW.{column}" for column in key) + ")"
                for key in keys
            )
            op.execute(
                f"CREATE TRIGGER trg_{table}_no_replace BEFORE INSERT ON {table} "
                f"FOR EACH ROW WHEN EXISTS (SELECT 1 FROM {table} WHERE {conflicts}) "
                "BEGIN SELECT RAISE(ABORT, 'Quote history is append-only'); END"
            )
            operations = ("DELETE",) if table == "quote_lineages" else ("UPDATE", "DELETE")
            for operation in operations:
                op.execute(
                    f"CREATE TRIGGER trg_{table}_no_{operation.lower()} "
                    f"BEFORE {operation} ON {table} "
                    "FOR EACH ROW BEGIN SELECT RAISE(ABORT, 'Quote history is append-only'); END"
                )
        changed = " OR ".join(f"NEW.{column} IS NOT OLD.{column}" for column in _LINEAGE_IMMUTABLE)
        op.execute(
            "CREATE TRIGGER trg_quote_lineage_identity BEFORE UPDATE ON quote_lineages "
            f"FOR EACH ROW WHEN {changed} "
            "BEGIN SELECT RAISE(ABORT, 'Quote lineage identity is immutable'); END"
        )
