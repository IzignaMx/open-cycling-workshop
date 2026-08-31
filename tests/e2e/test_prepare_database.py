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
