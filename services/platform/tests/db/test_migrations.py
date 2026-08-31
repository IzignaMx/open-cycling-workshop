from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_head_contains_v01_infrastructure_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # migrations/env.py intentionally lets OCWP_DATABASE_URL override the
    # config URL (12-factor deployments). CI exports that variable for the
    # PostgreSQL service, so this disposable sqlite migration must strip it
    # or alembic would migrate the shared service database instead.
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_E2E_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_TEST_DATABASE_URL", raising=False)
    service_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "migration.sqlite3"
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "migrations"))
    config.set_main_option("prepend_sys_path", str(service_root / "src"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite+pysqlite:///{database_path}")).get_table_names())
    assert {
        "organizations",
        "locations",
        "customers",
        "sync_mutation_receipts",
        "sync_changes",
    } <= tables
    assert "outbox_events" in tables
    assert "background_jobs" in tables
    assert "users" in tables
