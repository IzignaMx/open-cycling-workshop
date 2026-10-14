"""Real PostgreSQL metadata and sparse-feed plans, in an owned test schema only."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from cycling_workshop.sync.baseline_queries import BaselineQueries
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.sql.elements import TextClause
from test_administration_postgres import _configured_postgres_url, _migration_config


@pytest.fixture
def baseline_query_postgres(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    url = _configured_postgres_url(monkeypatch)
    schema = f"ocwp_baseline_queries_{uuid4().hex}"
    admin = create_engine(
        url,
        hide_parameters=True,
        connect_args={"options": "-csearch_path=pg_catalog", "connect_timeout": 5},
    )
    isolated = url.update_query_dict({"options": f"-csearch_path={schema}", "connect_timeout": "5"})
    engine = create_engine(isolated, hide_parameters=True)
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SELECT current_database()")) == url.database
        command.upgrade(_migration_config(isolated), "head")
        yield engine
    finally:
        engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _nodes(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from _nodes(child)


def _sparse_feed_seed_statements() -> tuple[TextClause, TextClause]:
    return (
        text("""
            INSERT INTO sync_changes (organization_id, location_id, entity_type, entity_id,
                operation, entity_version, occurred_at, payload)
            SELECT 'org', 'loc', 'hidden', 'a', 'update', 1, now(),
                   json_build_object('hidden', true)
            FROM generate_series(1, 200000)
        """),
        text("""
            INSERT INTO sync_changes (organization_id, location_id, entity_type, entity_id,
                operation, entity_version, occurred_at, payload)
            VALUES ('org','loc','customer','a','update',2,now(),
                    json_build_object('historical', true)),
                   ('org','else','customer','a','update',3,now(),
                    json_build_object('foreign', true)),
                   ('org','loc','bicycle','b','update',1,now(),
                    json_build_object('historical', true))
        """),
    )


def test_sparse_feed_seed_has_no_accidental_bind_parameters() -> None:
    for statement in _sparse_feed_seed_statements():
        assert statement.compile().construct_params() == {}


def test_sparse_authorized_feed_has_bounded_index_plan(baseline_query_postgres: Engine) -> None:
    engine = baseline_query_postgres
    with engine.begin() as connection:
        for statement in _sparse_feed_seed_statements():
            connection.execute(statement)
        connection.execute(text("ANALYZE sync_changes"))
    captured: list[tuple[str, Any]] = []

    def capture(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        captured.append((statement, parameters))

    with Session(engine) as session:
        event.listen(engine, "before_cursor_execute", capture)
        try:
            queries = BaselineQueries(session, "org", "loc", ["customer", "bicycle"])
            candidates = queries.delta_candidates(0, 999999)
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert len(captured) == 2
        assert [candidate.entity_type for candidate in candidates] == ["customer", "bicycle"]
        for statement, parameters in captured:
            assert "octet_length(CAST(sync_changes.payload AS TEXT))" in statement
            assert "pg_column_size" not in statement
            plan = (
                session.connection()
                .exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters)
                .scalar_one()[0]["Plan"]
            )
            scans = [node for node in _nodes(plan) if node.get("Relation Name") == "sync_changes"]
            assert len(scans) == 1
            scan = scans[0]
            assert scan["Node Type"] in {"Index Scan", "Index Only Scan"}
            assert all(
                key in scan["Index Cond"]
                for key in ("organization_id", "location_id", "entity_type", "cursor")
            )
            assert scan["Actual Rows"] <= 101
            assert scan.get("Rows Removed by Filter", 0) == 0
            assert plan.get("Shared Hit Blocks", 0) + plan.get("Shared Read Blocks", 0) < 100


def test_decompressed_large_text_and_json_preflight(baseline_query_postgres: Engine) -> None:
    engine = baseline_query_postgres
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations(id,name) VALUES ('org','Synthetic')"))
        connection.execute(
            text("""INSERT INTO locations(id,organization_id,name)
                                   VALUES ('loc','org','Synthetic')""")
        )
        connection.execute(
            text("""INSERT INTO customers
            (id,organization_id,location_id,display_name,created_at,updated_at,version)
            VALUES ('a','org','loc','Synthetic',now(),now(),1)""")
        )
        connection.execute(
            text("""INSERT INTO service_orders
            (id,organization_id,location_id,customer_id,state,reported_problem,priority,
             created_at,updated_at,version)
            VALUES ('order','org','loc','a','INTAKE',repeat('x',4000000),'normal',now(),now(),1)
        """)
        )
        connection.execute(
            text("""INSERT INTO sync_changes
            (organization_id,location_id,entity_type,entity_id,operation,entity_version,
             occurred_at,payload)
            VALUES ('org','loc','service_order','order','update',1,now(),
                    json_build_object('reported_problem',repeat('x',4000000)))""")
        )
    with Session(engine) as session:
        queries = BaselineQueries(session, "org", "loc", ["service_order"])
        current = queries.scan_candidates("service_order", None, "z")
        historical = queries.delta_candidates(0, 999999)
        assert current[0].estimated_bytes >= 4000000
        assert historical[0].estimated_bytes >= 4000000
        assert not session.identity_map
