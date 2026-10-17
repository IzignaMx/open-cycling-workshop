"""Quote storage constraints on migrated SQLite and isolated PostgreSQL schemas.

SQLite evidence establishes functional constraints only, never row-lock behavior.
PostgreSQL uses the existing validated loopback *_test/*_e2e fixture and owns only
an unpredictable disposable schema. No actual installation is changed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from sqlite3 import IntegrityError as SQLiteIntegrityError

import pytest
from alembic import command
from cycling_workshop.db.base import Base
from cycling_workshop.db.registry import register_models
from psycopg.errors import StringDataRightTruncation
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Engine,
    MetaData,
    UniqueConstraint,
    inspect,
    select,
    text,
)
from sqlalchemy.exc import DataError, IntegrityError
from test_identity_migration import identity_migration_database as identity_migration_database

TABLES = {
    "quote_lineages",
    "quote_revisions",
    "quote_lines",
    "quote_line_targets",
    "quote_decisions",
    "quote_operations",
}


def test_quote_models_registered() -> None:
    register_models()
    assert Base.metadata.tables.keys() >= TABLES


def test_additive_quote_migration_and_forward_only_retention(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0011")
    seed_base(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id,name,dataset_incarnation) "
                "VALUES ('preserved','Existing "
                "organization','00000000-0000-0000-0000-000000000001')"
            )
        )
        insert(
            connection,
            "inventory_movements",
            movement_id="retained-stock",
            organization_id="a",
            location_id="location-a",
            product_id="product-a",
            kind="ADJUST",
            quantity=10,
            order_id="order-a",
            actor_id="actor-a",
            occurred_at=NOW,
        )
    with engine.connect() as connection:
        before = {
            table: list(connection.execute(text(f"SELECT * FROM {table}")).mappings())
            for table in inspect(engine).get_table_names()
            if table != "alembic_version"
        }
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) >= TABLES
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
        for table, rows in before.items():
            current = list(connection.execute(text(f"SELECT * FROM {table}")).mappings())
            assert len(current) == len(rows)
            assert [
                {key: row[key] for key in old}
                for old, row in zip(rows, current, strict=True)
            ] == rows
        assert (
            connection.scalar(text("SELECT name FROM organizations WHERE id='preserved'"))
            == "Existing organization"
        )


NOW = datetime(2026, 10, 15, tzinfo=UTC)
MAX_SAFE = 9_007_199_254_740_991


def insert(connection, table: str, **values):
    connection.execute(Base.metadata.tables[table].insert().values(**values))


def retained_quote_rows(engine):
    with engine.connect() as connection:
        return {
            name: list(
                connection.execute(
                    select(Base.metadata.tables[name]).order_by(
                        *Base.metadata.tables[name].primary_key.columns
                    )
                ).mappings()
            )
            for name in sorted(TABLES)
        }


def lineage_values(suffix="a", **changes):
    return {
        "lineage_id": f"root-{suffix}",
        "organization_id": suffix,
        "location_id": f"location-{suffix}",
        "order_id": f"order-{suffix}",
        "currency": "USD",
        "root_quote_id": f"root-{suffix}",
        "head_quote_id": f"root-{suffix}",
        "head_version": 1,
        "decision_sequence": 0,
        **changes,
    }


def revision_values(suffix="a", **changes):
    return {
        "quote_id": f"root-{suffix}",
        "lineage_id": f"root-{suffix}",
        "organization_id": suffix,
        "version": 1,
        "predecessor_id": None,
        "created_at": NOW,
        "actor_id": f"actor-{suffix}",
        "subtotal_minor": 200,
        "discount_minor": 10,
        "tax_minor": 19,
        "total_minor": 209,
        "line_amounts": [["labor", 100], ["part", 100], ["discount", -10], ["tax", 19]],
        **changes,
    }


def line_values(suffix="a", **changes):
    return {
        "revision_id": f"root-{suffix}",
        "line_id": "extra",
        "organization_id": suffix,
        "lineage_id": f"root-{suffix}",
        "position": 4,
        "kind": "labor",
        "description": "Labor",
        "minutes": 60,
        "hourly_rate_minor": 100,
        "product_id": None,
        "quantity": None,
        "unit_price_minor": None,
        "rate_bps": None,
        "amount_minor": None,
        **changes,
    }


def decision_values(suffix="a", **changes):
    return {
        "decision_id": f"decision-{suffix}",
        "lineage_id": f"root-{suffix}",
        "organization_id": suffix,
        "quote_id": f"root-{suffix}",
        "quote_version": 1,
        "sequence": 1,
        "actor_id": f"actor-{suffix}",
        "recorded_at": NOW,
        "reason": None,
        "supersedes_entry_id": None,
        "line_decisions": [],
        "pricing": {},
        **changes,
    }


def operation_values(suffix="a", **changes):
    return {
        "organization_id": suffix,
        "operation_id": f"create-{suffix}",
        "lineage_id": f"root-{suffix}",
        "kind": "create",
        "quote_id": f"root-{suffix}",
        "quote_version": 1,
        "resulting_decision_sequence": 0,
        "ordinal": 1,
        "decision_id": None,
        "proof_version": 1,
        "proof": {},
        "actor_id": f"actor-{suffix}",
        "recorded_at": NOW,
        "quote_outbox_id": f"outbox-create-{suffix}",
        "order_event_id": None,
        "resulting_order_version": None,
        "change_cursor": None,
        "order_outbox_id": None,
        **changes,
    }


def seed_base(engine: Engine):
    register_models()
    with engine.begin() as connection:
        for suffix in ("a", "b"):
            insert(connection, "organizations", id=suffix, name="Synthetic")
            insert(
                connection,
                "locations",
                id=f"location-{suffix}",
                organization_id=suffix,
                name="Synthetic",
            )
            insert(
                connection,
                "locations",
                id=f"other-location-{suffix}",
                organization_id=suffix,
                name="Other",
            )
            insert(
                connection,
                "users",
                id=f"actor-{suffix}",
                organization_id=suffix,
                username=suffix,
                display_name="Synthetic",
                password_hash="unused",
                capabilities=[],
            )
            insert(
                connection,
                "customers",
                id=f"customer-{suffix}",
                organization_id=suffix,
                location_id=f"location-{suffix}",
                display_name="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )
            insert(
                connection,
                "service_orders",
                id=f"order-{suffix}",
                organization_id=suffix,
                location_id=f"location-{suffix}",
                customer_id=f"customer-{suffix}",
                state="DIAGNOSIS",
                reported_problem="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )
            insert(
                connection,
                "products",
                id=f"product-{suffix}",
                organization_id=suffix,
                location_id=f"location-{suffix}",
                sku=f"sku-{suffix}",
                name="Synthetic",
                created_at=NOW,
                updated_at=NOW,
            )


def seed_history(engine: Engine):
    with engine.begin() as connection:
        for suffix in ("a", "b"):
            insert(connection, "quote_lineages", **lineage_values(suffix))
            insert(connection, "quote_revisions", **revision_values(suffix))
            insert(connection, "quote_lines", **line_values(suffix, line_id="labor", position=0))
            insert(
                connection,
                "quote_lines",
                **line_values(
                    suffix,
                    line_id="part",
                    position=1,
                    kind="part",
                    minutes=None,
                    hourly_rate_minor=None,
                    product_id=f"product-{suffix}",
                    quantity=1,
                    unit_price_minor=100,
                ),
            )
            insert(
                connection,
                "quote_lines",
                **line_values(
                    suffix,
                    line_id="discount",
                    position=2,
                    kind="discount",
                    minutes=None,
                    hourly_rate_minor=None,
                    amount_minor=10,
                ),
            )
            insert(
                connection,
                "quote_lines",
                **line_values(
                    suffix,
                    line_id="tax",
                    position=3,
                    kind="tax",
                    minutes=None,
                    hourly_rate_minor=None,
                    rate_bps=1000,
                ),
            )
            for source in ("tax", "discount"):
                for target in ("part", "labor"):
                    insert(
                        connection,
                        "quote_line_targets",
                        revision_id=f"root-{suffix}",
                        source_line_id=source,
                        target_line_id=target,
                    )
            insert(connection, "quote_decisions", **decision_values(suffix))
            for kind in ("create", "decision"):
                insert(
                    connection,
                    "outbox_events",
                    event_id=f"outbox-{kind}-{suffix}",
                    event_type="quote.test",
                    aggregate_type="quote",
                    aggregate_id=f"root-{suffix}",
                    organization_id=suffix,
                    location_id=f"location-{suffix}",
                    payload={},
                    occurred_at=NOW,
                )
                values = operation_values(suffix)
                if kind == "decision":
                    values.update(
                        kind=kind,
                        operation_id=f"decision-{suffix}",
                        decision_id=f"decision-{suffix}",
                        resulting_decision_sequence=1,
                        ordinal=2,
                        quote_outbox_id=f"outbox-decision-{suffix}",
                    )
                insert(connection, "quote_operations", **values)
            connection.execute(
                text("UPDATE quote_lineages SET decision_sequence=1 WHERE lineage_id=:id"),
                {"id": f"root-{suffix}"},
            )


@pytest.fixture
def quote_database(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    seed_base(engine)
    seed_history(engine)
    return config, engine


def test_root_head_are_deferred_and_nonnull_without_committed_orphan(quote_database):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(
            connection,
            "quote_revisions",
            **revision_values(quote_id="revision-a", version=2, predecessor_id="root-a"),
        )
        connection.execute(
            text(
                "UPDATE quote_lineages SET head_quote_id='revision-a',head_version=2 "
                "WHERE lineage_id='root-a'"
            )
        )
    for statement in (
        "UPDATE quote_lineages SET head_quote_id='absent' WHERE lineage_id='root-a'",
        "UPDATE quote_lineages SET head_quote_id='root-b',head_version=1 WHERE lineage_id='root-a'",
        "UPDATE quote_lineages SET head_version=1 WHERE lineage_id='root-a'",
        "UPDATE quote_lineages SET head_quote_id=NULL WHERE lineage_id='root-a'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT head_version FROM quote_lineages WHERE lineage_id='root-a'")
            )
            == 2
        )


@pytest.mark.parametrize("table", sorted(TABLES - {"quote_lineages"}))
@pytest.mark.parametrize("verb", ["UPDATE", "DELETE"])
def test_financial_history_update_delete_are_refused(quote_database, table, verb):
    _, engine = quote_database
    first = next(iter(Base.metadata.tables[table].columns)).name
    statement = (
        f"UPDATE {table} SET {first}={first}" if verb == "UPDATE" else f"DELETE FROM {table}"
    )
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(text(statement))


@pytest.mark.parametrize(
    "column,value",
    [
        ("lineage_id", "other"),
        ("organization_id", "b"),
        ("location_id", "other-location-a"),
        ("order_id", "order-b"),
        ("currency", "EUR"),
        ("root_quote_id", "other"),
    ],
)
def test_lineage_identity_cannot_change(quote_database, column, value):
    _, engine = quote_database
    with pytest.raises(IntegrityError, match="immutable"), engine.begin() as connection:
        connection.execute(
            text(f"UPDATE quote_lineages SET {column}=:value WHERE lineage_id='root-a'"),
            {"value": value},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM quote_lineages",
        "DELETE FROM service_orders WHERE id='order-a'",
        "DELETE FROM organizations WHERE id='a'",
        "DELETE FROM users WHERE id='actor-a'",
        "DELETE FROM products WHERE id='product-a'",
        "DELETE FROM outbox_events WHERE event_id='outbox-create-a'",
    ],
)
def test_retention_blocks_parent_deletion(quote_database, statement):
    _, engine = quote_database
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(statement))


@pytest.mark.parametrize(
    "changes",
    [
        {"minutes": 0},
        {"minutes": 1_000_001},
        {"hourly_rate_minor": -1},
        {"hourly_rate_minor": MAX_SAFE + 1},
        {"hourly_rate_minor": None},
        {"description": ""},
        {"description": "x" * 501},
        {"position": 100},
        {"kind": "other"},
        {"quantity": 1},
        {"minutes": None},
        {
            "kind": "part",
            "minutes": None,
            "hourly_rate_minor": None,
            "product_id": "product-b",
            "quantity": 1,
            "unit_price_minor": 1,
        },
        {
            "kind": "part",
            "minutes": None,
            "hourly_rate_minor": None,
            "product_id": "product-a",
            "quantity": 0,
            "unit_price_minor": 1,
        },
        {"kind": "tax", "minutes": None, "hourly_rate_minor": None, "rate_bps": 10_001},
        {"kind": "discount", "minutes": None, "hourly_rate_minor": None, "amount_minor": 0},
        {"lineage_id": "root-b"},
        {"organization_id": "b"},
    ],
)
def test_line_discriminator_numeric_description_and_tenant_constraints(quote_database, changes):
    _, engine = quote_database
    before = retained_quote_rows(engine)
    postgres_varchar_overflow = engine.dialect.name == "postgresql" and changes == {
        "description": "x" * 501
    }
    expected = DataError if postgres_varchar_overflow else IntegrityError
    with pytest.raises(expected) as rejection, engine.begin() as connection:
        insert(connection, "quote_lines", **line_values(**changes))
    if postgres_varchar_overflow:
        assert type(rejection.value.orig) is StringDataRightTruncation
        assert rejection.value.orig.sqlstate == "22001"
    elif engine.dialect.name == "sqlite":
        assert type(rejection.value.orig) is SQLiteIntegrityError
    assert retained_quote_rows(engine) == before


def test_bigint_money_accepts_safe_max_and_zero_without_float_storage(quote_database):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(connection, "quote_lines", **line_values(hourly_rate_minor=MAX_SAFE))
        insert(
            connection,
            "quote_lines",
            **line_values(line_id="zero", position=5, hourly_rate_minor=0),
        )
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT hourly_rate_minor FROM quote_lines WHERE line_id='extra'")
            )
            == MAX_SAFE
        )
    assert isinstance(Base.metadata.tables["quote_revisions"].c.total_minor.type, BigInteger)


@pytest.mark.parametrize(
    "changes",
    [
        {"actor_id": "actor-b"},
        {"organization_id": "b"},
        {"lineage_id": "root-b"},
        {"version": 0},
        {"total_minor": MAX_SAFE + 1},
        {"total_minor": -1},
        {"predecessor_id": "root-b"},
        {"predecessor_id": None},
    ],
)
def test_revision_scope_root_predecessor_and_money_constraints(quote_database, changes):
    _, engine = quote_database
    values = revision_values(quote_id="revision-a", version=2, predecessor_id="root-a")
    values.update(changes)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(connection, "quote_revisions", **values)


def test_targets_cannot_reference_missing_or_other_revision_lines(quote_database):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(connection, "quote_lines", **line_values("b", line_id="foreign-only"))
    for target in ("foreign-only", "absent", "tax"):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            insert(
                connection,
                "quote_line_targets",
                revision_id="root-a",
                source_line_id="tax",
                target_line_id=target,
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"quote_id": "root-b"},
        {"quote_version": 2},
        {"actor_id": "actor-b"},
        {"supersedes_entry_id": "decision-b"},
        {"supersedes_entry_id": "correction"},
        {"sequence": 0},
        {"reason": "x" * 501},
    ],
)
def test_decision_scope_and_correction_reference(quote_database, changes):
    _, engine = quote_database
    before = retained_quote_rows(engine)
    values = decision_values(decision_id="correction", sequence=2, supersedes_entry_id="decision-a")
    values.update(changes)
    postgres_varchar_overflow = engine.dialect.name == "postgresql" and changes == {
        "reason": "x" * 501
    }
    expected = DataError if postgres_varchar_overflow else IntegrityError
    with pytest.raises(expected) as rejection, engine.begin() as connection:
        insert(connection, "quote_decisions", **values)
    if postgres_varchar_overflow:
        assert type(rejection.value.orig) is StringDataRightTruncation
        assert rejection.value.orig.sqlstate == "22001"
    elif engine.dialect.name == "sqlite":
        assert type(rejection.value.orig) is SQLiteIntegrityError
    assert retained_quote_rows(engine) == before


def test_decision_correction_branches_are_refused(quote_database):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(
            connection,
            "quote_decisions",
            **decision_values(
                decision_id="correction", sequence=2, supersedes_entry_id="decision-a"
            ),
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(
            connection,
            "quote_decisions",
            **decision_values(decision_id="branch", sequence=3, supersedes_entry_id="decision-a"),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "unknown"},
        {"proof_version": 2},
        {"decision_id": "decision-b"},
        {"actor_id": "actor-b"},
        {"ordinal": 4},
        {"resulting_decision_sequence": -1},
        {"kind": "decision", "decision_id": None},
        {"kind": "create", "quote_version": 2},
        {"order_event_id": "event"},
        {"change_cursor": 1},
        {"quote_outbox_id": None},
    ],
)
def test_operation_result_proof_and_effect_completeness(quote_database, changes):
    _, engine = quote_database
    values = operation_values(
        operation_id="new",
        kind="decision",
        decision_id="new",
        ordinal=3,
        resulting_decision_sequence=2,
        quote_outbox_id="outbox-new",
    )
    values.update(changes)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(connection, "quote_decisions", **decision_values(decision_id="new", sequence=2))
        insert(
            connection,
            "outbox_events",
            event_id="outbox-new",
            event_type="quote.test",
            aggregate_type="quote",
            aggregate_id="root-a",
            organization_id="a",
            payload={},
            occurred_at=NOW,
        )
        insert(connection, "quote_operations", **values)


@pytest.mark.parametrize("table", sorted(TABLES))
def test_sqlite_replace_cannot_erase_financial_evidence(quote_database, table):
    _, engine = quote_database
    if engine.dialect.name != "sqlite":
        pytest.skip("INSERT OR REPLACE is SQLite-specific")
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(text(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table} LIMIT 1"))


def test_postgres_truncate_guards(quote_database):
    _, engine = quote_database
    if engine.dialect.name != "postgresql":
        pytest.skip("TRUNCATE guard requires PostgreSQL")
    # CASCADE includes all mutually referencing quote tables; the statement
    # trigger must still reject it before any retained row can disappear.
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(text("TRUNCATE quote_lineages CASCADE"))


def test_model_schema_and_migration_columns_match(quote_database):
    _, engine = quote_database
    reflected = MetaData()
    reflected.reflect(engine, only=sorted(TABLES))
    for name in TABLES:
        assert set(reflected.tables[name].columns.keys()) == set(
            Base.metadata.tables[name].columns.keys()
        )
        for column in Base.metadata.tables[name].columns:
            actual = reflected.tables[name].c[column.name]
            assert actual.nullable == column.nullable
            assert actual.type._type_affinity == column.type._type_affinity
        expected_fks = {
            (tuple(fk.column_keys), tuple(element.target_fullname for element in fk.elements))
            for fk in Base.metadata.tables[name].foreign_key_constraints
        }
        actual_fks = {
            (tuple(fk.column_keys), tuple(element.target_fullname for element in fk.elements))
            for fk in reflected.tables[name].foreign_key_constraints
        }
        assert actual_fks == expected_fks
        expected_table = Base.metadata.tables[name]
        actual_table = reflected.tables[name]
        assert {
            (item.name, tuple(column.name for column in item.columns))
            for item in actual_table.constraints
            if isinstance(item, UniqueConstraint)
        } == {
            (item.name, tuple(column.name for column in item.columns))
            for item in expected_table.constraints
            if isinstance(item, UniqueConstraint)
        }
        # PostgreSQL rewrites equivalent CHECK expressions during reflection;
        # compare the complete named set rather than its pretty-printed SQL.
        assert {
            item.name for item in actual_table.constraints if isinstance(item, CheckConstraint)
        } == {item.name for item in expected_table.constraints if isinstance(item, CheckConstraint)}
        assert all(
            fk.ondelete == "RESTRICT" for fk in reflected.tables[name].foreign_key_constraints
        )
    for fk in inspect(engine).get_foreign_keys("quote_lineages"):
        if fk["name"] in {"fk_quote_lineage_head", "fk_quote_lineage_root"}:
            assert fk["options"]["deferrable"] is True
            assert fk["options"]["initially"] == "DEFERRED"


def test_downgrade_refuses_before_changes(quote_database):
    config, engine = quote_database
    with engine.connect() as connection:
        before = {
            table: connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES
        }
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(config, "0011")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0013"
        assert {
            table: connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in TABLES
        } == before


def test_new_lineage_must_match_exact_order_location_and_tenant(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    seed_base(engine)
    for changes in (
        {"location_id": "other-location-a"},
        {"location_id": "location-b"},
        {"order_id": "order-b"},
        {"currency": "usd"},
        {"currency": "US1"},
        {"currency": "AÉZ"},
        {"currency": "USD\x00"},
        {"root_quote_id": "different"},
        {"head_quote_id": "absent"},
        {"head_version": 2},
    ):
        with pytest.raises((DataError, IntegrityError)), engine.begin() as connection:
            insert(connection, "quote_lineages", **lineage_values(**changes))
            insert(connection, "quote_revisions", **revision_values())
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(connection, "quote_lineages", **lineage_values())
        # Root and head cannot be absent at COMMIT, despite deferred references.
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM quote_lineages")) == 0


def test_revision_successor_and_line_positions_are_unique(quote_database):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(
            connection,
            "quote_revisions",
            **revision_values(quote_id="second", version=2, predecessor_id="root-a"),
        )
    for values in (
        revision_values(quote_id="branch", version=3, predecessor_id="root-a"),
        revision_values(quote_id="duplicate-version", version=2, predecessor_id="second"),
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            insert(connection, "quote_revisions", **values)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(connection, "quote_lines", **line_values(position=0))


def test_sqlite_replace_alternate_keys_cannot_discard_other_rows(quote_database):
    _, engine = quote_database
    if engine.dialect.name != "sqlite":
        pytest.skip("INSERT OR REPLACE is SQLite-specific")
    # Different PK, conflicting presentation position: an UPDATE/DELETE-only
    # trigger is insufficient with SQLite's default recursive_triggers=OFF.
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(
            Base.metadata.tables["quote_lines"]
            .insert()
            .prefix_with("OR REPLACE")
            .values(**line_values(line_id="replacement", position=0))
        )
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM quote_lines WHERE line_id='labor'")) == 2
        )


def test_postgresql_migration_sql_has_cyclic_fk_and_statement_guards(tmp_path, monkeypatch):
    from io import StringIO

    from test_identity_migration import _clear_connection_environment, _config

    _clear_connection_environment(monkeypatch)
    config = _config("postgresql+psycopg://unused/unused_test")
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "0011:0012", sql=True)
    rendered = output.getvalue()
    assert "ALTER TABLE quote_lineages ADD CONSTRAINT fk_quote_lineage_root" in rendered
    assert "ALTER TABLE quote_lineages ADD CONSTRAINT fk_quote_lineage_head" in rendered
    assert rendered.count("DEFERRABLE INITIALLY DEFERRED") == 2
    for table in TABLES:
        assert f"CREATE TRIGGER trg_{table}_immutable" in rendered
    assert "BEFORE UPDATE OR DELETE OR TRUNCATE" in rendered
    assert "FOR EACH STATEMENT EXECUTE FUNCTION reject_quote_history_mutation()" in rendered
    # SQL generation is useful dialect evidence, not a live PostgreSQL claim.


def test_complete_order_effect_tuple_is_retained_but_delivery_bookkeeping_can_change(
    quote_database,
):
    _, engine = quote_database
    with engine.begin() as connection:
        insert(connection, "quote_decisions", **decision_values(decision_id="new", sequence=2))
        for event_id in ("quote-outbox-new", "order-outbox-new"):
            insert(
                connection,
                "outbox_events",
                event_id=event_id,
                event_type="synthetic.test",
                aggregate_type="service_order",
                aggregate_id="order-a",
                organization_id="a",
                location_id="location-a",
                payload={},
                occurred_at=NOW,
            )
        insert(
            connection,
            "service_order_events",
            event_id="order-event-new",
            order_id="order-a",
            organization_id="a",
            from_state="DIAGNOSIS",
            to_state="AUTHORIZED",
            action="authorize",
            actor_id="actor-a",
            occurred_at=NOW,
        )
        insert(
            connection,
            "sync_changes",
            cursor=100,
            organization_id="a",
            location_id="location-a",
            entity_type="service_order",
            entity_id="order-a",
            operation="update",
            entity_version=2,
            occurred_at=NOW,
            payload={},
        )
        insert(
            connection,
            "quote_operations",
            **operation_values(
                operation_id="new",
                kind="decision",
                decision_id="new",
                ordinal=3,
                resulting_decision_sequence=2,
                quote_outbox_id="quote-outbox-new",
                order_event_id="order-event-new",
                resulting_order_version=2,
                order_effect_version=1,
                change_cursor=100,
                order_outbox_id="order-outbox-new",
            ),
        )
        connection.execute(
            text("UPDATE outbox_events SET attempts=2 WHERE event_id='quote-outbox-new'")
        )
    for statement in (
        "DELETE FROM service_order_events WHERE event_id='order-event-new'",
        "DELETE FROM sync_changes WHERE cursor=100",
        "DELETE FROM outbox_events WHERE event_id='order-outbox-new'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT attempts FROM outbox_events WHERE event_id='quote-outbox-new'")
            )
            == 2
        )
        assert (
            connection.scalar(
                text("SELECT change_cursor FROM quote_operations WHERE operation_id='new'")
            )
            == 100
        )
