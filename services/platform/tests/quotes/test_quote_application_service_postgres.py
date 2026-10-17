"""Four unchanged service bodies on genuine, isolated PostgreSQL schema 0012.

This finite bridge does not qualify concurrency, restore or maximum capacity.
"""

import re

import psycopg
import pytest
from sqlalchemy import text
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import actors as actors
from test_quote_application_service import (
    test_create_decide_replay_commits_one_complete_tuple,
    test_expired_deadline_refuses_before_writer_or_effects,
    test_historical_quote_only_decision_replay_does_not_invent_transition,
    test_response_failure_rolls_back_all_decision_effects,
)
from test_quote_repository import database as database

__all__ = [
    "test_create_decide_replay_commits_one_complete_tuple",
    "test_expired_deadline_refuses_before_writer_or_effects",
    "test_historical_quote_only_decision_replay_does_not_invent_transition",
    "test_response_failure_rolls_back_all_decision_effects",
]

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


@pytest.fixture(autouse=True)
def postgres_identity(database, request):
    """Inspect the migrated connection, then release it before any service session."""
    assert database.dialect.name == "postgresql"
    assert database.dialect.driver == "psycopg"
    assert psycopg.__version__ == "3.3.4"
    with database.connect() as connection:
        assert isinstance(connection.connection.driver_connection, psycopg.Connection)
        observed = connection.execute(
            text(
                "SELECT current_database(), current_schema(), current_setting('search_path'), "
                "current_setting('server_version_num')::integer, "
                "current_setting('server_encoding'), current_setting('client_encoding'), "
                "(SELECT version_num FROM alembic_version)"
            )
        ).one()
        name, schema, search_path, version, server_encoding, client_encoding, revision = observed
        assert name == "ocwp_quote_micro_test"
        assert re.fullmatch(r"ocwp_identity_migration_[0-9a-f]{32}", schema)
        assert search_path == schema
        assert type(version) is int and version == 180004
        assert server_encoding == client_encoding == "UTF8"
        assert revision == "0012"
    assert connection.closed
    request.node.user_properties.append(
        (
            "ocwp_postgres_identity",
            {
                "node": request.node.nodeid,
                "dialect": database.dialect.name,
                "driver": database.dialect.driver,
                "driver_version": psycopg.__version__,
                "database": name,
                "schema": schema,
                "search_path": search_path,
                "server_version_num": version,
                "server_encoding": server_encoding,
                "client_encoding": client_encoding,
                "schema_revision": revision,
                "probe_connection_closed": connection.closed,
            },
        )
    )
