from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from cycling_workshop.db.url import normalize_database_url


def postgres_url() -> str:
    url = os.getenv('OCWP_TEST_DATABASE_URL')
    if not url:
        pytest.skip('OCWP_TEST_DATABASE_URL not configured')
    return url


def test_postgres_18_migrates_to_head_with_expected_v01_tables() -> None:
    url = normalize_database_url(postgres_url())
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / 'alembic.ini'))
    config.set_main_option('script_location', str(service_root / 'migrations'))
    config.set_main_option('prepend_sys_path', str(service_root / 'src'))
    config.set_main_option('sqlalchemy.url', url.replace('%', '%%'))

    command.upgrade(config, 'head')

    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            version = int(connection.scalar(text("select current_setting('server_version_num')")))
        assert version >= 180000
        tables = set(inspect(engine).get_table_names())
        assert {
            'organizations',
            'locations',
            'customers',
            'sync_mutation_receipts',
            'sync_changes',
            'outbox_events',
            'background_jobs',
            'users',
        } <= tables
    finally:
        engine.dispose()
