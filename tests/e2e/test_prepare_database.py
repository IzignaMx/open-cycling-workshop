from __future__ import annotations

import pytest

from scripts.e2e.prepare_e2e_database import validate_e2e_database_url


def test_e2e_database_guard_accepts_local_dedicated_database() -> None:
    validate_e2e_database_url("postgresql+psycopg://ocwp:test@127.0.0.1:5432/ocwp_e2e")


def test_e2e_database_guard_accepts_plain_postgresql_uri_and_normalizes_driver() -> None:
    validate_e2e_database_url("postgresql://ocwp:test@127.0.0.1:5432/ocwp_e2e")


def test_e2e_database_guard_refuses_non_test_database() -> None:
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        validate_e2e_database_url("postgresql+psycopg://ocwp:test@127.0.0.1:5432/ocwp")


def test_e2e_database_guard_refuses_remote_host() -> None:
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        validate_e2e_database_url("postgresql+psycopg://ocwp:test@db.example.com:5432/ocwp_e2e")


@pytest.mark.parametrize(
    "suffix",
    [
        "?host=remote.example",
        "?host=/tmp/socket",
        "?dbname=operator",
        "?service=production",
        "?sslmode=disable",
        "?host=localhost&host=remote.example",
    ],
)
def test_guard_rejects_every_connection_query_override(suffix: str) -> None:
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        validate_e2e_database_url("postgresql://synthetic@127.0.0.1/fixture_test" + suffix)


@pytest.mark.parametrize("driver", ["postgresql+psycopg2", "mysql", "sqlite"])
def test_guard_rejects_unapproved_drivers(driver: str) -> None:
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        validate_e2e_database_url(driver + "://synthetic@127.0.0.1/fixture_test")


@pytest.mark.parametrize(
    "entrypoint",
    [
        "reset_schema",
        "run_migrations",
        "seed_browser_identity",
        "seed_legacy_upgrade_identity",
        "seed_historical_workshop_records",
        "seed_administration_identities",
    ],
)
def test_each_mutating_entrypoint_guards_before_connection(entrypoint, monkeypatch) -> None:
    from scripts.e2e import prepare_e2e_database as preparation

    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe fixture target reached connection or migration")

    monkeypatch.setattr(preparation, "create_engine", forbidden)
    monkeypatch.setattr(preparation.command, "upgrade", forbidden)
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        getattr(preparation, entrypoint)(
            "postgresql://synthetic@127.0.0.1/fixture_test?dbname=operator"
        )


@pytest.mark.parametrize("fail", [False, True])
def test_migration_uses_validated_argument_and_restores_environment(monkeypatch, fail) -> None:
    import os

    from scripts.e2e import prepare_e2e_database as preparation

    target = "postgresql://synthetic@127.0.0.1/fixture_test"
    normalized = target.replace("postgresql://", "postgresql+psycopg://")
    prior = "postgresql://synthetic@remote.example/operator"
    monkeypatch.setenv("OCWP_DATABASE_URL", prior)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", "/not-read/operator-url")

    def upgrade(config, revision):
        assert config.get_main_option("sqlalchemy.url") == normalized
        assert os.environ["OCWP_DATABASE_URL"] == normalized
        assert revision == "head"
        if fail:
            raise ValueError("synthetic migration failure")

    monkeypatch.setattr(preparation.command, "upgrade", upgrade)
    if fail:
        with pytest.raises(ValueError, match="synthetic migration failure"):
            preparation.run_migrations(target)
    else:
        preparation.run_migrations(target)
    assert os.environ["OCWP_DATABASE_URL"] == prior
    assert os.environ["OCWP_DATABASE_URL_FILE"] == "/not-read/operator-url"


@pytest.mark.parametrize(
    "name",
    ["PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGSYSCONFDIR"],
)
def test_guard_rejects_ambient_destination_settings_without_echo(monkeypatch, name) -> None:
    monkeypatch.setenv(name, "private-target-canary")
    with pytest.raises(RuntimeError, match="dedicated local test database") as error:
        validate_e2e_database_url("postgresql://synthetic@127.0.0.1/fixture_test")
    assert "private-target-canary" not in str(error.value)


def test_guard_does_not_echo_malformed_url_values() -> None:
    with pytest.raises(RuntimeError, match="dedicated local test database") as error:
        validate_e2e_database_url("private-malformed-target-canary")
    assert "private-malformed-target-canary" not in str(error.value)
    assert error.value.__suppress_context__
