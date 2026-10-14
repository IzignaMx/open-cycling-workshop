"""Additive metadata migration, byte bounds and business preservation."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_baseline_migration_preserves_previous_rows_and_enforces_utf8_cache_bound(
    tmp_path, monkeypatch
):
    for name in (
        "OCWP_DATABASE_URL",
        "OCWP_DATABASE_URL_FILE",
        "OCWP_E2E_DATABASE_URL",
        "OCWP_TEST_DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    service = Path(__file__).resolve().parents[2]
    config = Config(str(service / "alembic.ini"))
    config.set_main_option("script_location", str(service / "migrations"))
    config.set_main_option("prepend_sys_path", str(service / "src"))
    url = f"sqlite+pysqlite:///{tmp_path / 'baseline.sqlite3'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "0008")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO organizations (id,name) VALUES ('org','Preserve')"))
    command.upgrade(config, "0009")
    with engine.begin() as connection:
        assert (
            connection.scalar(text("SELECT name FROM organizations WHERE id='org'")) == "Preserve"
        )
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0009"
        values = dict(
            reference_hash="a" * 64,
            baseline_id="baseline",
            organization_id="org",
            user_id="user",
            location_id="loc",
            request_id="request",
            epoch="epoch",
            phase="scan",
            sequence=0,
            created_at="2026-01-01",
            baseline_expires_at="2026-01-02",
            family_expires_at="2026-01-02",
            retention_until="2026-01-02",
            start_json="{}",
            state_json="{}",
            response_json="é" * 524289,
        )
        columns = ",".join(values)
        parameters = ",".join(":" + name for name in values)
        with pytest.raises(IntegrityError, match="ck_baseline_response_bytes"):
            connection.execute(
                text(f"INSERT INTO sync_baseline_families ({columns}) VALUES ({parameters})"),
                values,
            )
    indexes = {index["name"] for index in inspect(engine).get_indexes("sync_changes")}
    assert "ix_sync_changes_org_location_type_cursor" in indexes
    for table in ("customers", "bicycles", "service_orders"):
        assert f"ix_{table}_baseline_scan" in {
            i["name"] for i in inspect(engine).get_indexes(table)
        }
