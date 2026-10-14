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
from sqlalchemy import Engine, MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

INDEX_NAME = "uq_inventory_reservation_finalization"
NOW = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture
def migration_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Config, Engine]]:
    # Alembic env.py gives the environment URL precedence. Never migrate a
    # developer, production, or shared CI database from these isolated tests.
    for variable in (
        "OCWP_DATABASE_URL",
        "OCWP_DATABASE_URL_FILE",
        "OCWP_E2E_DATABASE_URL",
        "OCWP_TEST_DATABASE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)
    service_root = Path(__file__).resolve().parents[2]
    url = f"sqlite+pysqlite:///{tmp_path / 'inventory_migration.sqlite3'}"
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "migrations"))
    config.set_main_option("prepend_sys_path", str(service_root / "src"))
    config.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        yield config, engine
    finally:
        engine.dispose()


def _validated_postgres_test_url(database_url: str) -> URL:
    error = (
        "Inventory migration tests require a loopback PostgreSQL URL with a database "
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
        # Never echo a connection URL or credentials in safety failures.
        raise ValueError(error)
    return url


@pytest.fixture
def postgres_migration_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Config, Engine]]:
    configured_url = os.getenv("OCWP_TEST_DATABASE_URL")
    if not configured_url:
        pytest.skip("OCWP_TEST_DATABASE_URL not configured for live PostgreSQL migration tests")
    url = _validated_postgres_test_url(configured_url)
    for variable in (
        "OCWP_DATABASE_URL",
        "OCWP_DATABASE_URL_FILE",
        "OCWP_E2E_DATABASE_URL",
        "OCWP_TEST_DATABASE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)

    # An unpredictable, explicitly created schema is the entire reset boundary.
    # Neither public nor any pre-existing schema is on this connection's path.
    schema = f"ocwp_inventory_migration_{uuid4().hex}"
    admin = create_engine(
        url.update_query_dict({"options": "-csearch_path=pg_catalog", "connect_timeout": "5"}),
        hide_parameters=True,
    )
    isolated_url = url.update_query_dict(
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
            assert connection.scalar(text("SELECT current_database()")) == url.database

        service_root = Path(__file__).resolve().parents[2]
        config = Config(str(service_root / "alembic.ini"))
        config.set_main_option("script_location", str(service_root / "migrations"))
        config.set_main_option("prepend_sys_path", str(service_root / "src"))
        config.set_main_option(
            "sqlalchemy.url", isolated_url.render_as_string(hide_password=False).replace("%", "%%")
        )
        yield config, engine
    finally:
        engine.dispose()
        try:
            if created:
                with admin.begin() as connection:
                    connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


def _seed_tenant(engine: Engine, suffix: str = "1") -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            metadata.tables["organizations"].insert(),
            {"id": f"org-{suffix}", "name": "Synthetic workshop"},
        )
        connection.execute(
            metadata.tables["locations"].insert(),
            {
                "id": f"loc-{suffix}",
                "organization_id": f"org-{suffix}",
                "name": "Synthetic location",
            },
        )
        connection.execute(
            metadata.tables["products"].insert(),
            {
                "id": f"product-{suffix}",
                "organization_id": f"org-{suffix}",
                "location_id": f"loc-{suffix}",
                "sku": "TEST-SKU",
                "name": "Synthetic part",
                "unit": "piece",
                "created_at": NOW,
                "updated_at": NOW,
                "version": 1,
            },
        )


def _movement(
    movement_id: str,
    kind: str,
    quantity: int,
    reference: str | None = None,
    *,
    suffix: str = "1",
) -> dict[str, Any]:
    return {
        "movement_id": movement_id,
        "organization_id": f"org-{suffix}",
        "location_id": f"loc-{suffix}",
        "product_id": f"product-{suffix}",
        "kind": kind,
        "quantity": quantity,
        "order_id": "order-private-fixture",
        "reference_movement_id": reference,
        "actor_id": "actor-private-fixture",
        "note": "private-fixture-note",
        "occurred_at": NOW,
    }


def _insert(engine: Engine, *movements: dict[str, Any]) -> None:
    table = Table("inventory_movements", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(table.insert(), list(movements))


def _snapshot(engine: Engine) -> list[dict[str, Any]]:
    table = Table("inventory_movements", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(select(table).order_by(table.c.movement_id)).mappings()
        ]


def _revision(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.scalar(text("SELECT version_num FROM alembic_version")))


def test_upgrade_preserves_legacy_consumption_rows_and_balance(
    migration_database: tuple[Config, Engine],
) -> None:
    config, engine = migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _insert(
        engine,
        _movement("opening", "ADJUST", 10),
        _movement("reservation", "RESERVE", -4),
        _movement("legacy-consume", "CONSUME", 4, "reservation"),
        _movement("legacy-deduction", "ADJUST", -4, "legacy-consume"),
    )
    before = _snapshot(engine)

    command.upgrade(config, "head")

    assert _revision(engine) == "0007"
    assert _snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT SUM(quantity) FROM inventory_movements")) == 6
    index = next(
        index
        for index in inspect(engine).get_indexes("inventory_movements")
        if index["name"] == INDEX_NAME
    )
    assert index["unique"]
    assert index["column_names"] == ["organization_id", "reference_movement_id"]
    assert str(index["dialect_options"]["sqlite_where"]) == "kind IN ('RELEASE', 'CONSUME')"


@pytest.mark.parametrize("first_kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize("second_kind", ["RELEASE", "CONSUME"])
def test_upgrade_blocks_a_second_terminal_finalization(
    migration_database: tuple[Config, Engine], first_kind: str, second_kind: str
) -> None:
    config, engine = migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _insert(
        engine,
        _movement("reservation", "RESERVE", -4),
        _movement("first-finalization", first_kind, 4, "reservation"),
    )
    command.upgrade(config, "head")
    before = _snapshot(engine)

    with pytest.raises(IntegrityError):
        _insert(engine, _movement("second-finalization", second_kind, 4, "reservation"))

    assert _snapshot(engine) == before


@pytest.mark.parametrize("first_kind", ["RELEASE", "CONSUME"])
@pytest.mark.parametrize("second_kind", ["RELEASE", "CONSUME"])
def test_duplicate_legacy_finalizations_block_upgrade_without_changing_history(
    migration_database: tuple[Config, Engine], first_kind: str, second_kind: str
) -> None:
    config, engine = migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _insert(
        engine,
        _movement("reservation-private-fixture", "RESERVE", -4),
        _movement("first-finalization", first_kind, 4, "reservation-private-fixture"),
        _movement("second-finalization", second_kind, 4, "reservation-private-fixture"),
    )
    before = _snapshot(engine)

    with pytest.raises(RuntimeError, match="duplicate reservation finalizations") as failure:
        command.upgrade(config, "head")

    message = str(failure.value)
    assert "backup" in message.lower()
    assert "reconcil" in message.lower()
    assert "organization_id" in message
    assert "reference_movement_id" in message
    for private_value in ("org-1", "private-fixture", "first-finalization", "second-finalization"):
        assert private_value not in message
    assert _snapshot(engine) == before
    assert _revision(engine) == "0006"
    assert INDEX_NAME not in {
        index["name"] for index in inspect(engine).get_indexes("inventory_movements")
    }


def test_preflight_and_index_allow_distinct_tenants_nonterminal_rows_and_null_references(
    migration_database: tuple[Config, Engine],
) -> None:
    config, engine = migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _seed_tenant(engine, "2")
    _insert(
        engine,
        _movement("finalization-org-1", "CONSUME", 4, "shared-reference"),
        _movement("finalization-org-2", "RELEASE", 4, "shared-reference", suffix="2"),
        _movement("adjust-1", "ADJUST", -4, "shared-reference"),
        _movement("adjust-2", "ADJUST", 4, "shared-reference"),
        _movement("unreferenced-1", "CONSUME", 4),
        _movement("unreferenced-2", "CONSUME", 4),
    )
    before = _snapshot(engine)

    command.upgrade(config, "head")

    assert _snapshot(engine) == before
    _insert(
        engine,
        _movement("adjust-3", "ADJUST", -4, "shared-reference"),
        _movement("unreferenced-3", "RELEASE", 4),
        _movement("another-reservation", "CONSUME", 4, "different-reference"),
    )
    assert len(_snapshot(engine)) == len(before) + 3


def test_downgrade_removes_only_the_finalization_index(
    migration_database: tuple[Config, Engine],
) -> None:
    config, engine = migration_database
    command.upgrade(config, "head")
    _seed_tenant(engine)
    _insert(engine, _movement("reservation", "RESERVE", -4))
    before = _snapshot(engine)
    indexes = {index["name"] for index in inspect(engine).get_indexes("inventory_movements")}
    assert INDEX_NAME in indexes

    command.downgrade(config, "0006")

    assert _snapshot(engine) == before
    assert _revision(engine) == "0006"
    assert {index["name"] for index in inspect(engine).get_indexes("inventory_movements")} == (
        indexes - {INDEX_NAME}
    )
    command.upgrade(config, "head")
    assert _revision(engine) == "0007"
    assert _snapshot(engine) == before


@pytest.mark.parametrize("dialect", ["sqlite+pysqlite", "postgresql+psycopg"])
def test_offline_upgrade_emits_partial_unique_index_without_online_preflight(
    migration_database: tuple[Config, Engine], dialect: str
) -> None:
    config, _ = migration_database
    output = StringIO()
    config.output_buffer = output
    # Offline compilation must not attempt to connect to either database.
    config.set_main_option("sqlalchemy.url", f"{dialect}://")

    command.upgrade(config, "0006:head", sql=True)

    sql = output.getvalue()
    assert (
        f"CREATE UNIQUE INDEX {INDEX_NAME} ON inventory_movements "
        "(organization_id, reference_movement_id) WHERE kind IN ('RELEASE', 'CONSUME');"
    ) in sql
    assert "SELECT" not in sql.upper()


def test_empty_database_upgrades_to_inventory_finalization_head(
    migration_database: tuple[Config, Engine],
) -> None:
    config, engine = migration_database

    command.upgrade(config, "head")

    assert _revision(engine) == "0007"
    assert INDEX_NAME in {
        index["name"] for index in inspect(engine).get_indexes("inventory_movements")
    }


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/workshop",
        "postgresql://database.example/workshop_test",
        "postgresql://localhost/workshop_test?host=database.example",
        "postgresql://localhost/workshop_test?options=-csearch_path%3Dpublic",
        "postgresql://localhost/workshop_test?dbname=workshop",
        "sqlite:///workshop_test",
        "not-a-database-url",
    ],
)
def test_postgres_migration_fixture_rejects_unsafe_database_urls(url: str) -> None:
    with pytest.raises(ValueError, match=r"loopback PostgreSQL.*_test or _e2e"):
        _validated_postgres_test_url(url)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
@pytest.mark.parametrize("database", ["workshop_test", "workshop_e2e"])
def test_postgres_migration_fixture_accepts_only_explicit_test_targets(
    host: str, database: str
) -> None:
    url = _validated_postgres_test_url(f"postgresql://{host}/{database}")

    assert url.drivername == "postgresql+psycopg"
    assert url.database == database


def test_postgres_seeded_upgrade_preserves_legacy_ledger_and_enforces_finalization(
    postgres_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = postgres_migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _insert(
        engine,
        _movement("opening", "ADJUST", 10),
        _movement("reservation", "RESERVE", -4),
        _movement("legacy-consume", "CONSUME", 4, "reservation"),
        _movement("legacy-deduction", "ADJUST", -4, "legacy-consume"),
    )
    before = _snapshot(engine)

    command.upgrade(config, "head")

    assert _revision(engine) == "0007"
    assert _snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT SUM(quantity) FROM inventory_movements")) == 6
    index = next(
        index
        for index in inspect(engine).get_indexes("inventory_movements")
        if index["name"] == INDEX_NAME
    )
    assert index["unique"]
    assert index["column_names"] == ["organization_id", "reference_movement_id"]
    with pytest.raises(IntegrityError):
        _insert(engine, _movement("second-finalization", "RELEASE", 4, "reservation"))
    assert _snapshot(engine) == before


def test_postgres_duplicate_preflight_preserves_seeded_ledger_and_revision(
    postgres_migration_database: tuple[Config, Engine],
) -> None:
    config, engine = postgres_migration_database
    command.upgrade(config, "0006")
    _seed_tenant(engine)
    _insert(
        engine,
        _movement("reservation-private-fixture", "RESERVE", -4),
        _movement("first-finalization", "CONSUME", 4, "reservation-private-fixture"),
        _movement("second-finalization", "RELEASE", 4, "reservation-private-fixture"),
    )
    before = _snapshot(engine)

    with pytest.raises(RuntimeError, match="duplicate reservation finalizations") as failure:
        command.upgrade(config, "head")

    assert "private-fixture" not in str(failure.value)
    assert "org-1" not in str(failure.value)
    assert "backup" in str(failure.value).lower()
    assert _snapshot(engine) == before
    assert _revision(engine) == "0006"
    assert INDEX_NAME not in {
        index["name"] for index in inspect(engine).get_indexes("inventory_movements")
    }
