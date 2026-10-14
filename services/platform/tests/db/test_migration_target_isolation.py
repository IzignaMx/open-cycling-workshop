"""Exercise real migration setup while stopping before any database connection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy
from alembic import command
from sqlalchemy.engine import make_url

from services.platform.tests.db import test_migrations, test_postgres_integration
from services.platform.tests.inventory import test_inventory_migration, test_inventory_postgres

TEST_URL = "postgresql+psycopg://fixture:p%40ss%25word@127.0.0.1/fixture_test"
AMBIENT_URL = "postgresql+psycopg://fixture:synthetic-secret@production.invalid/workshop"


class StoppedBeforeConnection(Exception):
    """The Alembic configuration was captured; no engine was created."""


def _ambient_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    secret = tmp_path / "synthetic-database-url"
    secret.write_text(AMBIENT_URL, encoding="utf-8")
    monkeypatch.setenv("OCWP_DATABASE_URL", AMBIENT_URL)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(secret))
    return secret


def _capture_alembic(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []

    def capture(configuration: dict[str, Any], **_kwargs: Any) -> None:
        captured.append(configuration["sqlalchemy.url"])
        raise StoppedBeforeConnection

    monkeypatch.setattr(sqlalchemy, "engine_from_config", capture)
    return captured


@pytest.mark.parametrize("fixture_name", ["infrastructure", "inventory"])
def test_sqlite_migration_setup_ignores_ambient_database_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fixture_name: str
) -> None:
    _ambient_database(monkeypatch, tmp_path)
    captured = _capture_alembic(monkeypatch)
    if fixture_name == "infrastructure":
        expected = f"sqlite+pysqlite:///{tmp_path / 'migration.sqlite3'}"
        with pytest.raises(StoppedBeforeConnection):
            test_migrations.test_alembic_head_contains_v01_infrastructure_tables(
                tmp_path, monkeypatch
            )
    else:
        setup = test_inventory_migration.migration_database.__wrapped__(tmp_path, monkeypatch)
        try:
            config, _ = next(setup)
            expected = config.get_main_option("sqlalchemy.url")
            with pytest.raises(StoppedBeforeConnection):
                command.upgrade(config, "head")
        finally:
            setup.close()
    assert captured == [expected]


class _SyntheticEngine:
    """Fixture setup/cleanup recorder; never constructs a database driver."""

    def __init__(self, url: Any) -> None:
        self.url = make_url(url)
        self.schema = self.url.query["options"].removeprefix("-csearch_path=")
        self.statements: list[str] = []
        self.disposed = False

    def begin(self) -> _SyntheticEngine:
        return self

    def connect(self) -> _SyntheticEngine:
        return self

    def __enter__(self) -> _SyntheticEngine:
        return self

    def __exit__(self, *_args: Any) -> None:
        pass

    def execute(self, statement: Any) -> None:
        self.statements.append(str(statement))

    def scalar(self, statement: Any) -> str:
        if str(statement) in {"SELECT current_schema()", "SHOW search_path"}:
            return str(self.schema)
        assert str(statement) == "SELECT current_database()"
        return str(self.url.database)

    def dispose(self) -> None:
        self.disposed = True


def test_isolated_postgres_fixture_keeps_its_schema_when_ambient_file_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ambient_database(monkeypatch, tmp_path)
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", TEST_URL)
    captured = _capture_alembic(monkeypatch)
    engines: list[_SyntheticEngine] = []

    def synthetic_engine(url: Any, **_kwargs: Any) -> _SyntheticEngine:
        engine = _SyntheticEngine(url)
        engines.append(engine)
        return engine

    monkeypatch.setattr(test_inventory_migration, "create_engine", synthetic_engine)
    setup = test_inventory_migration.postgres_migration_database.__wrapped__(monkeypatch)
    try:
        config, _ = next(setup)
        expected = config.get_main_option("sqlalchemy.url")
        with pytest.raises(StoppedBeforeConnection):
            command.upgrade(config, "head")
    finally:
        setup.close()
    assert captured == [expected]
    assert make_url(captured[0]).password == "p@ss%word"
    assert (
        make_url(captured[0]).query["options"].startswith("-csearch_path=ocwp_inventory_migration_")
    )
    assert len(engines) == 2
    assert all(engine.disposed for engine in engines)
    assert engines[0].statements[0].startswith("CREATE SCHEMA ocwp_inventory_migration_")
    assert engines[0].statements[1].startswith("DROP SCHEMA ocwp_inventory_migration_")


@pytest.mark.parametrize("ambient_raw", [True, False])
def test_postgres_infrastructure_migration_pins_validated_target_and_restores_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ambient_raw: bool
) -> None:
    secret = _ambient_database(monkeypatch, tmp_path)
    if not ambient_raw:
        monkeypatch.delenv("OCWP_DATABASE_URL")
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", TEST_URL)
    captured = _capture_alembic(monkeypatch)
    with pytest.raises(StoppedBeforeConnection):
        test_postgres_integration.test_postgres_18_migrates_to_head_with_expected_v01_tables()
    assert captured == [TEST_URL]
    assert make_url(captured[0]).password == "p@ss%word"
    assert os.getenv("OCWP_DATABASE_URL") == (AMBIENT_URL if ambient_raw else None)
    assert os.getenv("OCWP_DATABASE_URL_FILE") == str(secret)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://fixture:synthetic-secret@production.invalid/fixture_test",
        "postgresql://fixture:synthetic-secret@127.0.0.1/workshop",
        "postgresql://fixture:synthetic-secret@localhost/fixture_test?host=production.invalid",
        "postgresql://fixture:synthetic-secret@localhost/fixture_test?options=-csearch_path%3Dpublic",
        "postgresql://fixture:synthetic-secret@localhost/fixture_test?service=production",
        "sqlite:///fixture_test",
        "synthetic-secret-invalid-url",
    ],
    ids=[
        "remote-host",
        "non-test-database",
        "query-host",
        "query-options",
        "query-service",
        "sqlite",
        "malformed",
    ],
)
def test_postgres_infrastructure_rejects_unsafe_targets_before_migration(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", url)

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Unsafe target reached migration or engine construction")

    monkeypatch.setattr(command, "upgrade", forbidden)
    monkeypatch.setattr(test_postgres_integration, "create_engine", forbidden)
    with pytest.raises(ValueError, match=r"loopback PostgreSQL.*_test or _e2e") as failure:
        test_postgres_integration.test_postgres_18_migrates_to_head_with_expected_v01_tables()
    assert "synthetic-secret" not in str(failure.value)
    assert "production.invalid" not in str(failure.value)
    assert url not in str(failure.value)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
@pytest.mark.parametrize("database", ["fixture_test", "fixture_e2e"])
def test_postgres_infrastructure_accepts_only_dedicated_loopback_targets(
    monkeypatch: pytest.MonkeyPatch, host: str, database: str
) -> None:
    raw = f"postgresql://fixture:p%40ss%25word@{host}/{database}"
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", raw)
    result = make_url(test_postgres_integration.postgres_url())
    assert result.drivername == "postgresql+psycopg"
    assert result.database == database
    assert result.password == "p@ss%word"


def test_existing_inventory_fixture_raw_target_takes_precedence_over_ambient_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ambient_database(monkeypatch, tmp_path)
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", TEST_URL)
    captured = _capture_alembic(monkeypatch)
    with pytest.raises(StoppedBeforeConnection):
        test_inventory_postgres.inventory_postgres_url.__wrapped__()
    assert captured == [TEST_URL]
