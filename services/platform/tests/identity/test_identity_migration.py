"""Identity schema invariants on isolated SQLite and PostgreSQL databases.

PostgreSQL runs only on an explicitly selected loopback *_test or *_e2e database;
each case creates and drops only its own unpredictable schema.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.db.url import normalize_database_url
from sqlalchemy import Engine, MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def safe_access_postgres_url(database_url: str) -> URL:
    error = (
        "Identity migration tests require a loopback PostgreSQL URL with a database "
        "ending in _test or _e2e and no query connection overrides."
    )
    try:
        url = make_url(normalize_database_url(database_url))
    except (ArgumentError, ValueError):
        raise ValueError(error) from None
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_(?:test|e2e)", url.database or "") is None
        or url.query
    ):
        raise ValueError(error)
    for variable in (
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGOPTIONS",
    ):
        if os.getenv(variable):
            raise ValueError("Identity migration tests reject ambient libpq connection overrides.")
    return url


def _clear_connection_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # libpq's PGHOSTADDR/PGSERVICE/PGOPTIONS can redirect even a validated URL.
    # A test may never inherit those settings or an application database URL.
    for variable in tuple(os.environ):
        if variable.startswith("PG") or variable in {
            "OCWP_DATABASE_URL",
            "OCWP_DATABASE_URL_FILE",
            "OCWP_E2E_DATABASE_URL",
            "OCWP_TEST_DATABASE_URL",
        }:
            monkeypatch.delenv(variable, raising=False)


def _config(url: URL | str) -> Config:
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "migrations"))
    config.set_main_option("prepend_sys_path", str(service_root / "src"))
    rendered = url.render_as_string(hide_password=False) if isinstance(url, URL) else url
    config.set_main_option("sqlalchemy.url", rendered.replace("%", "%%"))
    return config


@pytest.fixture(params=["sqlite", "postgres"])
def identity_migration_database(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Config, Engine]]:
    configured_url = os.getenv("OCWP_TEST_DATABASE_URL")
    # Validate routing before clearing environment, so unsafe configurations fail
    # explicitly rather than quietly ignoring the operator's connection inputs.
    postgres_url = None
    if request.param == "postgres" and configured_url:
        postgres_url = safe_access_postgres_url(configured_url)
    _clear_connection_environment(monkeypatch)
    if request.param == "sqlite":
        url = f"sqlite+pysqlite:///{tmp_path / 'identity_migration.sqlite3'}"
        engine = create_engine(url)

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection: Any, _: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

        try:
            yield _config(url), engine
        finally:
            engine.dispose()
        return

    if not configured_url:
        pytest.skip("OCWP_TEST_DATABASE_URL not configured; PostgreSQL migration unverified")
    assert postgres_url is not None
    schema = f"ocwp_identity_migration_{uuid4().hex}"
    admin = create_engine(
        postgres_url,
        connect_args={"options": "-csearch_path=pg_catalog", "connect_timeout": 5},
        hide_parameters=True,
    )
    isolated_url = postgres_url.update_query_dict(
        {"options": f"-csearch_path={schema}", "connect_timeout": "5"}
    )
    engine = create_engine(isolated_url, hide_parameters=True)
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SHOW search_path")) == schema
            assert connection.scalar(text("SELECT current_database()")) == postgres_url.database
            assert int(connection.scalar(text("SHOW server_version_num"))) >= 180000
        yield _config(isolated_url), engine
    finally:
        engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


def _table(engine: Engine, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=engine)


def _insert(engine: Engine, name: str, values: dict[str, Any]) -> None:
    with engine.begin() as connection:
        connection.execute(_table(engine, name).insert(), values)


def _snapshot(engine: Engine, name: str) -> list[dict[str, Any]]:
    table = _table(engine, name)
    with engine.connect() as connection:
        return [
            dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()
        ]


def _revision(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.scalar(text("SELECT version_num FROM alembic_version")))


def _seed_tenant(engine: Engine) -> tuple[str, str]:
    organization_id, location_id = str(uuid4()), str(uuid4())
    _insert(engine, "organizations", {"id": organization_id, "name": "Synthetic workshop"})
    _insert(
        engine,
        "locations",
        {"id": location_id, "organization_id": organization_id, "name": "Synthetic location"},
    )
    return organization_id, location_id


def _user(organization_id: str, **overrides: Any) -> dict[str, Any]:
    values = {
        "id": str(uuid4()),
        "organization_id": organization_id,
        "location_id": None,
        "username": f"synthetic-{uuid4().hex}",
        "display_name": "Synthetic user",
        "password_hash": "legacy-fixture-hash-preserved-exactly",
        "capabilities": ["customers.read", "customers.write"],
        "is_active": True,
        "session_version": 7,
    }
    return values | overrides


def _audit(organization_id: str | None, **overrides: Any) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "organization_id": organization_id,
        "actor_id": None,
        "target_id": None,
        "target_type": "user",
        "action": "user.created",
        "before": None,
        "after": {"display_name": "Synthetic user"},
        "occurred_at": NOW,
        "request_id": "synthetic-request",
    } | overrides


def test_empty_database_upgrades_to_identity_head(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")

    assert _revision(engine) == "0008"
    schema = inspect(engine)
    assert "identity_audit_events" in schema.get_table_names()
    columns = {column["name"]: column for column in schema.get_columns("users")}
    assert not columns["is_owner"]["nullable"]
    assert not columns["version"]["nullable"]
    assert columns["is_owner"]["default"] is not None
    assert columns["version"]["default"] is not None
    assert "uq_user_tenant" in {item["name"] for item in schema.get_unique_constraints("users")}
    index = next(
        item
        for item in schema.get_indexes("identity_audit_events")
        if item["name"] == "ix_identity_audit_org_time"
    )
    assert index["column_names"] == ["organization_id", "occurred_at"]


def test_upgrade_preserves_all_legacy_identity_values_without_promoting_users(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "0007")
    organization_id, location_id = _seed_tenant(engine)
    for values in (
        _user(organization_id, location_id=location_id),
        _user(organization_id, is_active=False, capabilities=[]),
        _user(organization_id, capabilities=["*"], session_version=13),
    ):
        _insert(engine, "users", values)
    before = _snapshot(engine, "users")

    command.upgrade(config, "head")

    after = _snapshot(engine, "users")
    assert len(after) == len(before)
    for old, current in zip(before, after, strict=True):
        assert {key: current[key] for key in old} == old
        assert current["is_owner"] is False
        assert current["version"] == 1
    assert _snapshot(engine, "identity_audit_events") == []
    assert _revision(engine) == "0008"


@pytest.mark.parametrize("session_version", [0, -1])
def test_invalid_legacy_session_version_blocks_upgrade_without_rewriting_users(
    identity_migration_database: tuple[Config, Engine], session_version: int
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "0007")
    organization_id, _ = _seed_tenant(engine)
    _insert(engine, "users", _user(organization_id, session_version=session_version))
    before = _snapshot(engine, "users")

    with pytest.raises(RuntimeError, match="invalid session versions") as failure:
        command.upgrade(config, "head")

    assert organization_id not in str(failure.value)
    assert "backup" in str(failure.value).lower()
    assert _snapshot(engine, "users") == before
    assert _revision(engine) == "0007"


@pytest.mark.parametrize(
    "invalid",
    [
        {"version": 0},
        {"version": -1},
        {"version": None},
        {"session_version": 0},
        {"session_version": -1},
        {"session_version": None},
        {"is_owner": None},
    ],
)
def test_user_version_and_owner_nullability_constraints_reject_invalid_rows(
    identity_migration_database: tuple[Config, Engine], invalid: dict[str, Any]
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    with pytest.raises(IntegrityError):
        _insert(engine, "users", _user(organization_id, **invalid))
    assert _snapshot(engine, "users") == []


def test_user_defaults_and_organization_wide_owner_constraint(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, location_id = _seed_tenant(engine)
    ordinary = _user(organization_id, location_id=location_id)
    _insert(engine, "users", ordinary)
    stored = _snapshot(engine, "users")[0]
    assert stored["is_owner"] is False
    assert stored["version"] == 1
    with pytest.raises(IntegrityError):
        _insert(engine, "users", _user(organization_id, location_id=location_id, is_owner=True))
    _insert(engine, "users", _user(organization_id, is_owner=True))
    assert len(_snapshot(engine, "users")) == 2


def test_existing_tenant_location_and_username_constraints_remain_enforced(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    foreign_organization_id, foreign_location_id = _seed_tenant(engine)
    _insert(engine, "users", _user(organization_id, username="normalized"))
    with pytest.raises(IntegrityError):
        _insert(engine, "users", _user(organization_id, username="normalized"))
    with pytest.raises(IntegrityError):
        _insert(engine, "users", _user(organization_id, location_id=foreign_location_id))
    _insert(engine, "users", _user(foreign_organization_id, username="normalized"))


@pytest.mark.parametrize("reference", ["actor_id", "target_id"])
def test_audit_user_references_cannot_cross_tenants_or_reference_missing_users(
    identity_migration_database: tuple[Config, Engine], reference: str
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    foreign_organization_id, _ = _seed_tenant(engine)
    user = _user(organization_id)
    foreign_user = _user(foreign_organization_id)
    _insert(engine, "users", user)
    _insert(engine, "users", foreign_user)
    for invalid_id in (foreign_user["id"], str(uuid4())):
        with pytest.raises(IntegrityError):
            _insert(
                engine, "identity_audit_events", _audit(organization_id, **{reference: invalid_id})
            )
    _insert(engine, "identity_audit_events", _audit(organization_id, **{reference: user["id"]}))
    assert len(_snapshot(engine, "identity_audit_events")) == 1


@pytest.mark.parametrize("reference", ["actor_id", "target_id"])
def test_audited_users_cannot_be_deleted_or_moved_between_tenants(
    identity_migration_database: tuple[Config, Engine], reference: str
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    foreign_organization_id, _ = _seed_tenant(engine)
    user = _user(organization_id)
    _insert(engine, "users", user)
    _insert(engine, "identity_audit_events", _audit(organization_id, **{reference: user["id"]}))
    users = _table(engine, "users")
    statements = [
        users.delete().where(users.c.id == user["id"]),
        users.update()
        .where(users.c.id == user["id"])
        .values(organization_id=foreign_organization_id),
    ]
    for statement in statements:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(statement)
    assert len(_snapshot(engine, "identity_audit_events")) == 1


def test_audit_organization_reference_is_required_and_restricts_deletion(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    for invalid_organization_id in (None, str(uuid4())):
        with pytest.raises(IntegrityError):
            _insert(engine, "identity_audit_events", _audit(invalid_organization_id))
    _insert(engine, "identity_audit_events", _audit(organization_id))
    organizations = _table(engine, "organizations")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(organizations.delete().where(organizations.c.id == organization_id))
    assert len(_snapshot(engine, "identity_audit_events")) == 1


@pytest.mark.parametrize(
    "invalid",
    [
        {"target_type": "organization"},
        {"target_type": None},
        {"action": None},
        {"occurred_at": None},
    ],
)
def test_audit_rejects_invalid_required_fields(
    identity_migration_database: tuple[Config, Engine], invalid: dict[str, Any]
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    with pytest.raises(IntegrityError):
        _insert(engine, "identity_audit_events", _audit(organization_id, **invalid))


def test_location_audit_keeps_location_identifier_in_safe_snapshot_only(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, location_id = _seed_tenant(engine)
    user = _user(organization_id)
    _insert(engine, "users", user)
    with pytest.raises(IntegrityError):
        _insert(
            engine,
            "identity_audit_events",
            _audit(organization_id, target_type="location", target_id=user["id"]),
        )
    safe_snapshot = {"id": location_id, "name": "Synthetic location"}
    _insert(
        engine,
        "identity_audit_events",
        _audit(organization_id, target_type="location", after=safe_snapshot),
    )
    stored = _snapshot(engine, "identity_audit_events")[0]
    assert stored["target_id"] is None
    assert stored["after"] == safe_snapshot


@pytest.mark.parametrize("mutation", ["UPDATE", "DELETE"])
def test_audit_history_is_database_append_only(
    identity_migration_database: tuple[Config, Engine], mutation: str
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    _insert(engine, "identity_audit_events", _audit(organization_id))
    before = _snapshot(engine, "identity_audit_events")
    statement = (
        "UPDATE identity_audit_events SET action = 'rewritten'"
        if mutation == "UPDATE"
        else "DELETE FROM identity_audit_events"
    )
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(text(statement))
    assert _snapshot(engine, "identity_audit_events") == before


def test_postgres_audit_history_rejects_truncate(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("TRUNCATE is PostgreSQL-specific")
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    _insert(engine, "identity_audit_events", _audit(organization_id))
    before = _snapshot(engine, "identity_audit_events")
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(text("TRUNCATE identity_audit_events"))
    assert _snapshot(engine, "identity_audit_events") == before


def test_downgrade_and_reupgrade_preserve_legacy_user_fields(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    command.upgrade(config, "0007")
    organization_id, location_id = _seed_tenant(engine)
    _insert(engine, "users", _user(organization_id, location_id=location_id))
    before = _snapshot(engine, "users")
    command.upgrade(config, "head")
    _insert(engine, "identity_audit_events", _audit(organization_id))

    command.downgrade(config, "0007")

    assert _revision(engine) == "0007"
    assert _snapshot(engine, "users") == before
    assert "identity_audit_events" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    assert _revision(engine) == "0008"
    assert len(_snapshot(engine, "users")) == 1


def test_postgres_offline_upgrade_emits_constraints_and_append_only_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_connection_environment(monkeypatch)
    config = _config("postgresql+psycopg://")
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "0007:head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE identity_audit_events" in sql
    assert "uq_user_tenant" in sql
    assert "CHECK (version > 0)" in sql
    assert "ON DELETE RESTRICT" in sql
    assert "BEFORE UPDATE OR DELETE OR TRUNCATE" in sql
    assert "append-only" in sql


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/workshop",
        "postgresql://database.example/workshop_test",
        "postgresql://localhost/workshop_test?host=database.example",
        "postgresql://localhost/workshop_test?hostaddr=198.51.100.1",
        "postgresql://localhost/workshop_test?service=production",
        "postgresql://localhost/workshop_test?options=-csearch_path%3Dpublic",
        "postgresql://localhost/workshop_test?dbname=workshop",
        "sqlite:///workshop_test",
        "not-a-database-url",
    ],
)
def test_postgres_fixture_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError, match=r"loopback PostgreSQL.*_test or _e2e"):
        safe_access_postgres_url(url)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
@pytest.mark.parametrize("database", ["workshop_test", "workshop_e2e"])
def test_postgres_fixture_accepts_explicit_test_targets(host: str, database: str) -> None:
    parsed = safe_access_postgres_url(f"postgresql://{host}/{database}")
    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.database == database


def test_postgres_fixture_removes_environment_connection_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variables = (
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGOPTIONS",
        "PGPASSFILE",
        "PGPASSWORD",
        "OCWP_DATABASE_URL",
        "OCWP_E2E_DATABASE_URL",
        "OCWP_TEST_DATABASE_URL",
    )
    for variable in variables:
        monkeypatch.setenv(variable, "unsafe-synthetic-fixture")
    _clear_connection_environment(monkeypatch)
    assert all(variable not in os.environ for variable in variables)


def test_migration_config_round_trips_percent_encoded_credentials() -> None:
    url = "postgresql+psycopg://synthetic:p%25ssword@localhost/workshop_test"
    assert _config(url).get_main_option("sqlalchemy.url") == url


@pytest.mark.parametrize(
    "variable",
    [
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGSYSCONFDIR",
        "PGOPTIONS",
    ],
)
def test_postgres_fixture_rejects_ambient_connection_redirects(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "unsafe-synthetic-fixture")
    with pytest.raises(ValueError, match="ambient libpq connection overrides"):
        safe_access_postgres_url("postgresql://localhost/workshop_test")


def test_sqlite_replace_cannot_overwrite_an_existing_audit_event(
    identity_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = identity_migration_database
    if engine.dialect.name != "sqlite":
        pytest.skip("INSERT OR REPLACE is SQLite-specific")
    command.upgrade(config, "head")
    organization_id, _ = _seed_tenant(engine)
    audit = _audit(organization_id)
    _insert(engine, "identity_audit_events", audit)
    before = _snapshot(engine, "identity_audit_events")
    table = _table(engine, "identity_audit_events")
    with pytest.raises(IntegrityError, match="append-only"), engine.begin() as connection:
        connection.execute(
            table.insert().prefix_with("OR REPLACE"), audit | {"action": "rewritten"}
        )
    assert _snapshot(engine, "identity_audit_events") == before


def test_identity_migration_fixture_clears_file_backed_application_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", "/synthetic/production-database-url")
    _clear_connection_environment(monkeypatch)
    assert "OCWP_DATABASE_URL_FILE" not in os.environ
