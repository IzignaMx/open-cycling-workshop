from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_uses_database_secret_with_percent_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database = tmp_path / "database%name.sqlite3"
    secret = tmp_path / "database_url"
    secret.write_text(f"sqlite+pysqlite:///{database}")
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(secret))
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", "sqlite+pysqlite:///:memory:")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite+pysqlite:///{database}")
    try:
        assert "users" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_production_migrations_do_not_require_auth_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("OCWP_ENVIRONMENT", "production")
    monkeypatch.delenv("OCWP_AUTH_SECRET", raising=False)
    monkeypatch.delenv("OCWP_AUTH_SECRET_FILE", raising=False)
    test_alembic_uses_database_secret_with_percent_path(monkeypatch, tmp_path)
