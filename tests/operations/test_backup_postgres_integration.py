"""Real restore drill, only against explicitly configured disposable PostgreSQL."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

from scripts.database.backup_postgres import (
    BackupError,
    _libpq_env,
    create_backup_bundle,
    restore_backup_bundle,
    verify_backup_bundle,
)

ROOT = Path(__file__).resolve().parents[2]


def _safe_test_database_url(configured: str) -> URL:
    url = make_url(configured)
    if url.drivername not in {"postgresql", "postgresql+psycopg", "postgres"}:
        raise ValueError("restore drill requires a PostgreSQL URL")
    if not url.database or not url.database.endswith(("_test", "_e2e")):
        raise ValueError("restore drill requires an explicitly named _test or _e2e database")
    if url.query:
        raise ValueError("restore drill disallows URL query overrides")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("restore drill requires an explicit loopback test host")
    _libpq_env(configured)  # Prevent ambient libpq host/service overrides in the fixture too.
    return url.set(drivername="postgresql+psycopg")


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user@127.0.0.1/production",
        "postgresql://user@127.0.0.1/db_test?dbname=production",
        "postgresql://user@127.0.0.1/db_test?host=elsewhere",
        "postgresql://user@127.0.0.1/db_test?service=remote",
        "postgresql://user@elsewhere/db_test",
        "postgresql://user/db_test",
    ],
)
def test_restore_fixture_rejects_unsafe_connection_targets(url: str) -> None:
    with pytest.raises(ValueError):
        _safe_test_database_url(url)


@pytest.fixture
def disposable_databases(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, str]]:
    configured = os.getenv("OCWP_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("PostgreSQL restore drill needs OCWP_TEST_DATABASE_URL")
    url = _safe_test_database_url(configured)
    for executable in ("pg_dump", "pg_restore"):
        if not shutil.which(executable):
            pytest.skip(f"PostgreSQL restore drill needs {executable} 18 on PATH")
        version = subprocess.run(
            [executable, "--version"], check=True, capture_output=True, text=True
        ).stdout
        if "(PostgreSQL) 18." not in version:
            pytest.skip("PostgreSQL restore drill needs matching major-18 clients on PATH")
    # Alembic env honors these; pin the generated source explicitly below instead.
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    monkeypatch.delenv("OCWP_E2E_DATABASE_URL", raising=False)
    suffix = uuid.uuid4().hex
    names = (f"ocwp_backup_source_{suffix}_test", f"ocwp_backup_target_{suffix}_test")
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    created: list[str] = []
    try:
        with admin.connect() as connection:
            for name in names:
                # Names are internal hex UUIDs, never accepted from input or a manifest.
                connection.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE template0')
                created.append(name)
        yield tuple(url.set(database=name).render_as_string(hide_password=False) for name in names)
    finally:
        with admin.connect() as connection:
            for name in created:
                connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def test_real_database_only_restore_drill(
    disposable_databases: tuple[str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_url, target_url = disposable_databases
    config = Config(str(ROOT / "services/platform/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/platform/migrations"))
    config.set_main_option("prepend_sys_path", str(ROOT / "services/platform/src"))
    config.set_main_option("sqlalchemy.url", source_url.replace("%", "%%"))
    monkeypatch.setenv("OCWP_DATABASE_URL", source_url)
    command.upgrade(config, "head")
    source = create_engine(source_url)
    target = create_engine(target_url)
    try:
        with source.begin() as connection:
            connection.execute(
                text("INSERT INTO organizations (id,name) VALUES (:id,:name)"),
                {"id": "synthetic-org", "name": "Restore drill workshop"},
            )
            # Identifier quoting is deliberate: count checks must not treat : as a bind.
            connection.exec_driver_sql('CREATE TABLE public.":odd""table" (value text)')
            connection.exec_driver_sql('INSERT INTO public.":odd""table" VALUES (\'synthetic\')')
        bundle = create_backup_bundle(source_url, tmp_path / "generation")
        assert verify_backup_bundle(bundle)["status"] == "integrity_checked_not_restored"
        result = restore_backup_bundle(bundle, target_url, confirm_empty_target=True)
        assert result["status"] == "database_restore_checked"
        assert result["application_smoke_tested"] is False
        manifest = json.loads((bundle / "manifest.json").read_text())
        assert result["tables_checked"] == len(manifest["database"]["tables"])
        with target.connect() as connection:
            assert connection.execute(text("SELECT name FROM organizations")).scalar_one() == (
                "Restore drill workshop"
            )
        target.dispose()
        with pytest.raises(BackupError, match="not empty"):
            restore_backup_bundle(bundle, target_url, confirm_empty_target=True)
        # Neither retry refusal nor verification mutates the successful restored data.
        with target.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM organizations")).scalar_one() == 1
    finally:
        source.dispose()
        target.dispose()
