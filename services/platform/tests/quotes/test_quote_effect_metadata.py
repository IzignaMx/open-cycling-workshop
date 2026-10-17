"""UNEXECUTED candidate: finite schema evidence, never service/containment proof.

PostgreSQL parametrizations use the existing isolated-schema fixture. The one
logical-restore node uses its separate owned-database fixture and client tools.
SQLite parametrizations prove only functional surrogate behavior.
"""

from __future__ import annotations

from io import StringIO

import pytest
from alembic import command
from cycling_workshop.db.base import Base
from cycling_workshop.db.registry import register_models
from sqlalchemy import MetaData, Table, create_engine, event, inspect, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateTable
from test_backup_postgres_integration import disposable_databases as disposable_databases
from test_identity_migration import _clear_connection_environment, _config
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_schema import (
    NOW,
    decision_values,
    insert,
    operation_values,
    seed_base,
    seed_history,
)

PAIRS = (("sync_changes", "entity_type"), ("outbox_events", "aggregate_type"))
RAW = ' { "text" : "é🚲", "escaped" : "\\u0061", "empty" : null } '


def snapshot(engine):
    """Preserve every base field, casting JSON to text before driver decoding."""
    result = {}
    for name in inspect(engine).get_table_names():
        columns = inspect(engine).get_columns(name)
        expressions = []
        for column in columns:
            column_name = column["name"]
            if column.get("computed") or column_name == "order_effect_version":
                continue
            if str(column["type"]).upper() == "JSON":
                expressions.append(f'CAST("{column_name}" AS TEXT) AS "{column_name}"')
            else:
                expressions.append(f'"{column_name}"')
        with engine.connect() as connection:
            rows = connection.execute(text(f'SELECT {", ".join(expressions)} FROM "{name}"'))
            result[name] = sorted((dict(row) for row in rows.mappings()), key=repr)
    return result


def seed_payload_pair(engine, raw=RAW, *, scope="service_order"):
    cast = "CAST(:raw AS JSON)" if engine.dialect.name == "postgresql" else ":raw"
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sync_changes (cursor,organization_id,location_id,entity_type,"
                "entity_id,operation,entity_version,occurred_at,payload) VALUES "
                f"(100,'a','location-a',:scope,'order-a','update',2,:now,{cast})"
            ),
            {"scope": scope, "now": NOW, "raw": raw},
        )
        connection.execute(
            text(
                "INSERT INTO outbox_events (event_id,event_type,aggregate_type,aggregate_id,"
                "organization_id,location_id,payload,occurred_at,attempts) VALUES "
                f"('order-outbox','synthetic.test',:scope,'order-a','a','location-a',{cast},:now,0)"
            ),
            {"scope": scope, "now": NOW, "raw": raw},
        )


def seed_effect_dependencies(engine):
    with engine.begin() as connection:
        insert(connection, "quote_decisions", **decision_values(decision_id="new", sequence=2))
        insert(
            connection,
            "outbox_events",
            event_id="quote-outbox",
            event_type="synthetic.test",
            aggregate_type="quote",
            aggregate_id="root-a",
            organization_id="a",
            location_id="location-a",
            payload={},
            occurred_at=NOW,
        )
        insert(
            connection,
            "service_order_events",
            event_id="order-event",
            order_id="order-a",
            organization_id="a",
            from_state="DIAGNOSIS",
            to_state="AUTHORIZED",
            action="authorize",
            actor_id="actor-a",
            occurred_at=NOW,
        )


def effect_values(**changes):
    return operation_values(
        operation_id="new",
        kind="decision",
        decision_id="new",
        ordinal=3,
        resulting_decision_sequence=2,
        quote_outbox_id="quote-outbox",
        order_event_id="order-event",
        resulting_order_version=2,
        change_cursor=100,
        order_outbox_id="order-outbox",
    ) | changes


def assert_generated_schema(engine):
    from cycling_workshop.db.order_payload_size import require_order_payload_count_schema

    with engine.connect() as connection:
        require_order_payload_count_schema(connection)
    for table, discriminator in PAIRS:
        columns = {column["name"]: column for column in inspect(engine).get_columns(table)}
        count = columns["order_payload_raw_octets"]
        assert count["nullable"] is True
        assert count["computed"]["persisted"] is (engine.dialect.name == "postgresql")
        if engine.dialect.name == "postgresql":
            with engine.connect() as connection:
                actual = connection.execute(
                    text(
                        "SELECT a.attgenerated, pg_get_expr(d.adbin,d.adrelid) AS expression "
                        "FROM pg_attribute a JOIN pg_attrdef d "
                        "ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
                        "WHERE a.attrelid=CAST(:table AS regclass) "
                        "AND a.attname='order_payload_raw_octets'"
                    ),
                    {"table": table},
                ).one()
            assert actual.attgenerated == "s"
            assert " ".join(actual.expression.split()) == (
                f"CASE WHEN (({discriminator})::text = 'service_order'::text) "
                "THEN (octet_length((payload)::text))::bigint ELSE NULL::bigint END"
            )
        else:
            assert " ".join(count["computed"]["sqltext"].split()) == (
                f"CASE WHEN {discriminator} = 'service_order' "
                "THEN length(CAST(payload AS BLOB)) ELSE NULL END"
            )


def test_empty_upgrade_has_generated_dialect_schema(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    assert_generated_schema(engine)
    version = next(
        column for column in inspect(engine).get_columns("quote_operations")
        if column["name"] == "order_effect_version"
    )
    assert version["nullable"] is True and version["default"] is None
    assert "ck_quote_operation_effect_version" in {
        constraint["name"] for constraint in inspect(engine).get_check_constraints("quote_operations")
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0013"


def test_seeded_upgrade_preserves_bytes_and_regenerates_counts(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0012")
    seed_base(engine)
    seed_history(engine)
    seed_payload_pair(engine)
    before = snapshot(engine)
    command.upgrade(config, "head")
    after = snapshot(engine)
    before.pop("alembic_version")
    after.pop("alembic_version")
    assert before == after
    assert_generated_schema(engine)
    with engine.connect() as connection:
        assert set(connection.scalars(text("SELECT order_effect_version FROM quote_operations"))) == {None}
        for table, _ in PAIRS:
            row = connection.execute(text(
                f"SELECT CAST(payload AS TEXT), order_payload_raw_octets FROM {table} "
                "WHERE order_payload_raw_octets IS NOT NULL"
            )).one()
            assert row == (RAW, len(RAW.encode("utf-8")))
        assert connection.scalar(text(
            "SELECT count(*) FROM outbox_events WHERE aggregate_type='quote' "
            "AND order_payload_raw_octets IS NOT NULL"
        )) == 0
    changed = '{"x":"éé"}'
    cast = "CAST(:raw AS JSON)" if engine.dialect.name == "postgresql" else ":raw"
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE sync_changes SET payload={cast} WHERE cursor=100"), {"raw": changed})
        connection.execute(text(f"UPDATE outbox_events SET payload={cast} WHERE event_id='order-outbox'"), {"raw": changed})
        connection.execute(text("UPDATE outbox_events SET attempts=3, published_at=:now WHERE event_id='order-outbox'"), {"now": NOW})
    with engine.connect() as connection:
        for table, discriminator in PAIRS:
            assert connection.scalar(text(
                f"SELECT order_payload_raw_octets FROM {table} WHERE {discriminator}='service_order'"
            )) == len(changed.encode("utf-8"))
    for table, _ in PAIRS:
        with pytest.raises(DBAPIError), engine.begin() as connection:
            connection.execute(text(f"UPDATE {table} SET order_payload_raw_octets=0"))


def test_legacy_populated_tuple_refuses_before_any_ddl(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0012")
    seed_base(engine)
    seed_history(engine)
    seed_payload_pair(engine)
    seed_effect_dependencies(engine)
    with engine.begin() as connection:
        # Reflect 0012: no fabricated version or mutated old receipt is needed.
        old = Table("quote_operations", MetaData(), autoload_with=connection)
        connection.execute(old.insert(), effect_values())
    before = snapshot(engine)
    statements = []

    def observed(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine.__class__, "before_cursor_execute", observed)
    try:
        with pytest.raises(RuntimeError, match="unsupported populated legacy"):
            command.upgrade(config, "head")
    finally:
        event.remove(engine.__class__, "before_cursor_execute", observed)
    assert not any(statement.lstrip().upper().startswith("ALTER TABLE") for statement in statements)
    assert snapshot(engine) == before
    assert "order_effect_version" not in {column["name"] for column in inspect(engine).get_columns("quote_operations")}
    for table, _ in PAIRS:
        assert "order_payload_raw_octets" not in {column["name"] for column in inspect(engine).get_columns(table)}


def test_effect_version_constraint_retains_dependencies_and_immutability(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    seed_base(engine)
    seed_history(engine)
    seed_payload_pair(engine)
    seed_effect_dependencies(engine)
    for version in (None, 0, 2, -1):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            insert(connection, "quote_operations", **effect_values(order_effect_version=version))
    fields = ("order_event_id", "resulting_order_version", "change_cursor", "order_outbox_id")
    # Each incomplete arm and a versioned quote-only arm must fail. Presence
    # checks avoid SQL UNKNOWN admitting the otherwise-complete version-null row.
    for field in fields:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            insert(connection, "quote_operations", **effect_values(order_effect_version=1, **{field: None}))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert(connection, "quote_operations", **effect_values(order_effect_version=1, **dict.fromkeys(fields)))
    with engine.begin() as connection:
        insert(connection, "quote_operations", **effect_values(order_effect_version=1))
    for statement in (
        "UPDATE quote_operations SET order_effect_version=1 WHERE operation_id='new'",
        "DELETE FROM service_order_events WHERE event_id='order-event'",
        "DELETE FROM sync_changes WHERE cursor=100",
        "DELETE FROM outbox_events WHERE event_id='order-outbox'",
        "DELETE FROM outbox_events WHERE event_id='quote-outbox'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT order_effect_version FROM quote_operations WHERE operation_id='new'")) == 1
    before = snapshot(engine)
    with pytest.raises(RuntimeError, match="forward-only"):
        command.downgrade(config, "0012")
    assert snapshot(engine) == before


def test_upgrade_failure_rolls_back_all_added_columns(identity_migration_database):
    config, engine = identity_migration_database
    command.upgrade(config, "0012")
    seed_base(engine)
    seed_history(engine)
    seed_payload_pair(engine)
    before = snapshot(engine)

    def fail_after_counts(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("ALTER TABLE outbox_events ADD COLUMN order_payload_raw_octets"):
            raise RuntimeError("synthetic failure after generated DDL")

    event.listen(engine.__class__, "after_cursor_execute", fail_after_counts)
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            command.upgrade(config, "head")
    finally:
        event.remove(engine.__class__, "after_cursor_execute", fail_after_counts)
    assert snapshot(engine) == before
    assert "order_effect_version" not in {column["name"] for column in inspect(engine).get_columns("quote_operations")}
    for table, _ in PAIRS:
        assert "order_payload_raw_octets" not in {column["name"] for column in inspect(engine).get_columns(table)}
    command.upgrade(config, "head")
    assert_generated_schema(engine)


def test_model_ddl_has_explicit_dialect_generation():
    register_models()
    for dialect, keyword in ((postgresql.dialect(), "STORED"), (sqlite.dialect(), "VIRTUAL")):
        for table, _ in PAIRS:
            ddl = str(CreateTable(Base.metadata.tables[table]).compile(dialect=dialect))
            assert "GENERATED ALWAYS AS" in ddl and keyword in ddl
            column = Base.metadata.tables[table].c.order_payload_raw_octets
            assert column.default is None and column.computed is not None


def test_metadata_migration_rejects_offline_output(monkeypatch):
    _clear_connection_environment(monkeypatch)
    config = _config("postgresql+psycopg://unused/unused_test")
    output = StringIO()
    config.output_buffer = output
    with pytest.raises(RuntimeError, match="online metadata preflight"):
        command.upgrade(config, "0012:0013", sql=True)
    assert "ADD COLUMN" not in output.getvalue()


def test_real_logical_restore_recomputes_generated_counts(disposable_databases, tmp_path):
    from scripts.database.backup_postgres import create_backup_bundle, restore_backup_bundle

    source_url, target_url = disposable_databases
    source, target = create_engine(source_url), create_engine(target_url)
    try:
        command.upgrade(_config(source_url), "head")
        seed_base(source)
        seed_history(source)
        seed_payload_pair(source)
        seed_effect_dependencies(source)
        with source.begin() as connection:
            insert(connection, "quote_operations", **effect_values(order_effect_version=1))
        before = snapshot(source)
        bundle = create_backup_bundle(source_url, tmp_path / "generated-metadata")
        result = restore_backup_bundle(bundle, target_url, confirm_empty_target=True)
        assert result["status"] == "database_restore_checked"
        assert snapshot(target) == before
        assert_generated_schema(target)
        with target.connect() as connection:
            assert connection.scalar(text("SELECT order_effect_version FROM quote_operations WHERE operation_id='new'")) == 1
            for table, discriminator in PAIRS:
                row = connection.execute(text(
                    f"SELECT CAST(payload AS TEXT), order_payload_raw_octets FROM {table} "
                    f"WHERE {discriminator}='service_order'"
                )).one()
                assert row == (RAW, len(RAW.encode("utf-8")))
        # This is schema/base-value preservation. It deliberately does NOT call
        # these toy payloads valid quote effects or qualify restore/replay service.
    finally:
        source.dispose()
        target.dispose()


@pytest.mark.parametrize("table,discriminator", PAIRS)
@pytest.mark.parametrize("fault", ["mutable", "wrong_type", "wrong_expression", "wrong_discriminator", "jsonb", "virtual", "inherited"])
def test_runtime_count_verifier_refuses_malformed_postgres_metadata(
    identity_migration_database, table, discriminator, fault,
):
    from cycling_workshop.db.order_payload_size import (
        OrderPayloadCountSchemaError,
        require_order_payload_count_schema,
    )

    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("actual PostgreSQL catalogue negative")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        require_order_payload_count_schema(connection)
        connection.execute(text(f"ALTER TABLE {table} DROP COLUMN order_payload_raw_octets"))
        if fault == "jsonb":
            connection.execute(text(f"ALTER TABLE {table} ALTER COLUMN payload TYPE JSONB USING payload::jsonb"))
        if fault == "mutable":
            declaration = "BIGINT"
        else:
            kind = "INTEGER" if fault == "wrong_type" else "BIGINT"
            expression = "octet_length(payload::text)::bigint"
            if fault == "wrong_expression":
                expression += " + 1"
            scope = "quote" if fault == "wrong_discriminator" else "service_order"
            storage = "VIRTUAL" if fault == "virtual" else "STORED"
            declaration = (
                f"{kind} GENERATED ALWAYS AS (CASE WHEN {discriminator} = '{scope}' "
                f"THEN {expression} ELSE NULL END) {storage}"
            )
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN order_payload_raw_octets {declaration}"))
        if fault == "inherited":
            connection.execute(text(f"CREATE TABLE inherited_count_child () INHERITS ({table})"))
        with pytest.raises(OrderPayloadCountSchemaError):
            require_order_payload_count_schema(connection)


def test_runtime_count_verifier_accepts_fresh_metadata(identity_migration_database):
    from cycling_workshop.db.order_payload_size import require_order_payload_count_schema

    config, engine = identity_migration_database
    command.upgrade(config, "head")
    with engine.connect() as connection:
        require_order_payload_count_schema(connection)


@pytest.mark.parametrize("table,discriminator", PAIRS)
@pytest.mark.parametrize("replacement", ["partitioned", "view", "missing"])
def test_runtime_count_verifier_refuses_nonordinary_relations(
    identity_migration_database, table, discriminator, replacement,
):
    from cycling_workshop.db.order_payload_size import (
        OrderPayloadCountSchemaError,
        require_order_payload_count_schema,
    )

    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("actual PostgreSQL relation negative")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        require_order_payload_count_schema(connection)
        connection.execute(text(f"ALTER TABLE {table} RENAME TO preserved_relation"))
        if replacement == "partitioned":
            connection.execute(text(
                f"CREATE TABLE {table} (LIKE preserved_relation INCLUDING GENERATED) "
                f"PARTITION BY LIST ({discriminator})"
            ))
        elif replacement == "view":
            connection.execute(text(f"CREATE VIEW {table} AS SELECT * FROM preserved_relation"))
        with pytest.raises(OrderPayloadCountSchemaError):
            require_order_payload_count_schema(connection)


@pytest.mark.parametrize("shadow", ["function", "operator"])
def test_runtime_count_verifier_refuses_shadowed_generated_dependencies(
    identity_migration_database, shadow,
):
    from cycling_workshop.db.order_payload_size import (
        OrderPayloadCountSchemaError,
        _pg_expression,
        require_order_payload_count_schema,
    )

    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("actual PostgreSQL dependency negative")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        require_order_payload_count_schema(connection)
        schema = connection.scalar(text("SELECT pg_catalog.current_schema()"))
        quoted = connection.dialect.identifier_preparer.quote(schema)
        if shadow == "function":
            connection.execute(text(
                f"CREATE FUNCTION {quoted}.octet_length(pg_catalog.text) "
                "RETURNS pg_catalog.int4 LANGUAGE SQL IMMUTABLE AS 'SELECT 1'"
            ))
        else:
            connection.execute(text(
                f"CREATE FUNCTION {quoted}.wrong_equal(pg_catalog.text,pg_catalog.text) "
                "RETURNS pg_catalog.bool LANGUAGE SQL IMMUTABLE AS 'SELECT false'"
            ))
            connection.execute(text(
                f"CREATE OPERATOR {quoted}.= (FUNCTION = {quoted}.wrong_equal, "
                "LEFTARG = pg_catalog.text, RIGHTARG = pg_catalog.text)"
            ))
        connection.execute(text(
            "SELECT pg_catalog.set_config('search_path', :path, true)"
        ), {"path": f"{quoted}, pg_catalog"})
        # Corrupt BOTH tables, so the old string-only verifier cannot refuse
        # merely because an untouched builtin now deparses with qualification.
        for table, discriminator in PAIRS:
            connection.execute(text(
                f"ALTER TABLE {table} DROP COLUMN order_payload_raw_octets"
            ))
            connection.execute(text(
                f"ALTER TABLE {table} ADD COLUMN order_payload_raw_octets BIGINT "
                f"GENERATED ALWAYS AS (CASE WHEN {discriminator}::text = 'service_order'::text "
                "THEN octet_length(payload::text)::bigint ELSE NULL END) STORED"
            ))
            expression = connection.scalar(text(
                "SELECT pg_catalog.pg_get_expr(d.adbin,d.adrelid,false) "
                "FROM pg_catalog.pg_attrdef d JOIN pg_catalog.pg_attribute a "
                "ON a.attrelid OPERATOR(pg_catalog.=) d.adrelid "
                "AND a.attnum OPERATOR(pg_catalog.=) d.adnum "
                "WHERE d.adrelid OPERATOR(pg_catalog.=) pg_catalog.to_regclass(:table) "
                "AND a.attname OPERATOR(pg_catalog.=) 'order_payload_raw_octets'"
            ), {"table": table})
            assert " ".join(expression.split()) == _pg_expression(discriminator)
        with pytest.raises(OrderPayloadCountSchemaError):
            require_order_payload_count_schema(connection)


@pytest.mark.parametrize("table,discriminator", PAIRS)
@pytest.mark.parametrize("kind", ["TABLE", "VIEW"])
@pytest.mark.parametrize("uppercase", [False, True])
def test_sqlite_temp_shadow_refused(
    identity_migration_database, table, discriminator, kind, uppercase,
):
    from cycling_workshop.db.order_payload_size import (
        OrderPayloadCountSchemaError,
        require_order_payload_count_schema,
    )

    config, engine = identity_migration_database
    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite TEMP resolution surrogate")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        require_order_payload_count_schema(connection)
        temporary = table.upper() if uppercase else table
        connection.execute(text(f"CREATE TEMP {kind} {temporary} AS SELECT * FROM main.{table}"))
        with pytest.raises(OrderPayloadCountSchemaError):
            require_order_payload_count_schema(connection)


def test_postgres_generated_dependency_rows_are_exact(identity_migration_database):
    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("actual PostgreSQL generated dependency rows")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        for table, discriminator in PAIRS:
            rows = connection.execute(text(
                "SELECT dep.objsubid, dep.refclassid='pg_catalog.pg_class'::regclass, "
                "dep.refobjid=d.adrelid, referenced.attname, dep.deptype "
                "FROM pg_catalog.pg_attrdef d "
                "JOIN pg_catalog.pg_attribute a ON a.attrelid=d.adrelid AND a.attnum=d.adnum "
                "JOIN pg_catalog.pg_depend dep ON dep.classid='pg_catalog.pg_attrdef'::regclass "
                "AND dep.objid=d.oid LEFT JOIN pg_catalog.pg_attribute referenced "
                "ON referenced.attrelid=dep.refobjid AND referenced.attnum=dep.refobjsubid "
                "WHERE d.adrelid=pg_catalog.to_regclass(:table) "
                "AND a.attname='order_payload_raw_octets'"
            ), {"table": table}).all()
            assert set(rows) == {
                (0, True, True, "order_payload_raw_octets", "i"),
                (0, True, True, "payload", "n"),
                (0, True, True, discriminator, "n"),
            }
