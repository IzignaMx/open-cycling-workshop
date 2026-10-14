from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.db.url import normalize_database_url
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def postgres_url() -> str:
    url = os.getenv("OCWP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("OCWP_TEST_DATABASE_URL not configured")
    error = (
        "Infrastructure migration tests require a loopback PostgreSQL URL with a database "
        "ending in _test or _e2e and no query connection overrides."
    )
    normalized = normalize_database_url(url)
    try:
        parsed = make_url(normalized)
    except (ArgumentError, ValueError):
        raise ValueError(error) from None
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host not in {"localhost", "127.0.0.1", "::1"}
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_(?:test|e2e)", parsed.database or "") is None
        or parsed.query
    ):
        # Do not disclose connection URLs, passwords, or secret-file contents.
        raise ValueError(error)
    return normalized


def test_postgres_18_migrates_to_head_with_expected_v01_tables() -> None:
    url = postgres_url()
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "migrations"))
    config.set_main_option("prepend_sys_path", str(service_root / "src"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

    # env.py intentionally honors application URL/secret-file overrides. Pin
    # this validated test target only for the migration, then restore ambient state.
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("OCWP_DATABASE_URL", url)
        environment.delenv("OCWP_DATABASE_URL_FILE", raising=False)
        command.upgrade(config, "head")

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            version = int(connection.scalar(text("select current_setting('server_version_num')")))
        assert version >= 180000
        tables = set(inspect(engine).get_table_names())
        assert {
            "organizations",
            "locations",
            "customers",
            "sync_mutation_receipts",
            "sync_changes",
            "outbox_events",
            "background_jobs",
            "users",
        } <= tables
    finally:
        engine.dispose()
