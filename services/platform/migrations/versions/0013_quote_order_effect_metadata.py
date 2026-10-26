"""Version reserved quote effects and add generated order-payload byte metadata.

Revision ID: 0013
Revises: 0012

Preparation candidate, unexecuted. PostgreSQL rewrites BOTH generic tables and
their indexes under ACCESS EXCLUSIVE locks. Require drained writers, verified
backup/isolated restore and separately approved resource/lock/cleanup envelopes.
SQLite is a UTF-8 functional-test surrogate and uses VIRTUAL counts, not STORED.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Keep migration definitions independent of later application/model changes.
_EFFECT_CHECK = (
    "(order_event_id IS NULL AND resulting_order_version IS NULL AND "
    "change_cursor IS NULL AND order_outbox_id IS NULL AND order_effect_version IS NULL) "
    "OR (kind = 'decision' AND order_event_id IS NOT NULL AND "
    "resulting_order_version IS NOT NULL AND change_cursor IS NOT NULL AND "
    "order_outbox_id IS NOT NULL AND order_effect_version IS NOT NULL AND "
    "order_effect_version = 1)"
)


def upgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("Quote migration 0013 requires online metadata preflight")
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect == "postgresql":
        version = int(connection.scalar(sa.text("SHOW server_version_num")))
        if not 180000 <= version < 190000:
            raise RuntimeError("Quote migration 0013 requires PostgreSQL 18 qualification")
        if any(
            connection.scalar(sa.text(f"SHOW {setting}")) != "UTF8"
            for setting in ("server_encoding", "client_encoding")
        ):
            raise RuntimeError("Quote migration 0013 requires UTF8 server/client encodings")
        connection.execute(
            sa.text(
                "LOCK TABLE quote_operations, sync_changes, outbox_events IN ACCESS EXCLUSIVE MODE"
            )
        )
    elif dialect == "sqlite" and connection.dialect.driver == "pysqlite":
        if connection.scalar(sa.text("PRAGMA encoding")) != "UTF-8":
            raise RuntimeError("Quote migration 0013 SQLite tests require UTF-8 encoding")
        sqlite_version = str(connection.scalar(sa.text("SELECT sqlite_version()")))
        if tuple(int(part) for part in sqlite_version.split(".")) < (3, 37, 0):
            raise RuntimeError("Quote migration 0013 SQLite tests require SQLite 3.37 or newer")
        # A zero-row DML starts/acquires the real write transaction even with
        # sqlite3 legacy transaction control; SQLAlchemy in_transaction alone
        # is insufficient. Preserve every revision/receipt byte and never commit
        # internally, disable FK checks, swallow BUSY or issue nested BEGIN.
        connection.exec_driver_sql("UPDATE alembic_version SET version_num = version_num WHERE 0")
        driver = connection.connection.driver_connection
        if getattr(driver, "in_transaction", False) is not True:
            raise RuntimeError("Quote migration 0013 requires a retained SQLite write transaction")
    else:
        raise RuntimeError("Quote migration 0013 supports PostgreSQL or pysqlite tests only")

    # Scalar-only inventory before ANY DDL. Conservatively refuse even a complete
    # old tuple: fitting bytes/IDs do not establish effect-version provenance.
    unsupported = connection.execute(
        sa.text(
            "SELECT 1 FROM quote_operations WHERE order_event_id IS NOT NULL "
            "OR resulting_order_version IS NOT NULL OR change_cursor IS NOT NULL "
            "OR order_outbox_id IS NOT NULL LIMIT 1"
        )
    ).first()
    if unsupported is not None:
        raise RuntimeError(
            "Quote migration 0013 blocked: unsupported populated legacy order-effect "
            "tuple; preserve source and backup, do not backfill versions or delete history"
        )

    # An inline named CHECK avoids SQLite table recreation and preserves all
    # existing retention triggers/FKs. Both dialects enforce the same tuple rule.
    op.execute(
        "ALTER TABLE quote_operations ADD COLUMN order_effect_version SMALLINT "
        f"CONSTRAINT ck_quote_operation_effect_version CHECK ({_EFFECT_CHECK})"
    )
    for table, discriminator in (
        ("sync_changes", "entity_type"),
        ("outbox_events", "aggregate_type"),
    ):
        if dialect == "postgresql":
            predicate = (
                f"{discriminator}::pg_catalog.text OPERATOR(pg_catalog.=) "
                "'service_order'::pg_catalog.text"
            )
            expression = "pg_catalog.octet_length(payload::pg_catalog.text)::pg_catalog.int8"
            storage = "STORED"
        else:
            predicate = f"{discriminator} = 'service_order'"
            expression = "length(CAST(payload AS BLOB))"
            storage = "VIRTUAL"
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN order_payload_raw_octets BIGINT "
            f"GENERATED ALWAYS AS (CASE WHEN {predicate} "
            f"THEN {expression} ELSE NULL END) {storage}"
        )


def downgrade() -> None:
    raise RuntimeError(
        "Quote migration 0013 is forward-only; preserve evidence and use a "
        "schema-compatible rollback or reviewed forward fix"
    )
