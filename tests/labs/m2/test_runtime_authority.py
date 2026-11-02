"""Preparation-only pure contracts; no PostgreSQL connections or credentials."""

import json

import pytest

from tests.labs.m2.authority import LabDenied
from tests.labs.m2.runtime_authority import parse_run_manifest, validate_server_identity

MANIFEST = {"schema": 1, "nonce": "a" * 32, "source_commit": "b" * 40, "source_tree": "c" * 40}


def test_closed_manifest_derives_owned_database_without_accepting_dsn():
    run = parse_run_manifest(json.dumps(MANIFEST).encode())
    assert run.database == "m2_" + "a" * 32
    assert run.source_commit == "b" * 40
    assert run.source_tree == "c" * 40
    validate_server_identity(180004, run.database, run)


@pytest.mark.parametrize(
    "change",
    [
        {"dsn": "not-permitted"},
        {"schema": True},
        {"schema": 2},
        {"nonce": "../existing"},
        {"nonce": "A" * 32},
        {"source_tree": "z" * 40},
        {"source_commit": ""},
        {"database": "postgres"},
    ],
)
def test_manifest_refuses_unknown_or_unbound_configuration(change):
    with pytest.raises(LabDenied):
        parse_run_manifest(json.dumps({**MANIFEST, **change}).encode())


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"null",
        b"{",
        b" " * 4097,
        b'{"schema":1,"schema":1,"nonce":"'
        + b"a" * 32
        + b'","source_commit":"'
        + b"b" * 40
        + b'","source_tree":"'
        + b"c" * 40
        + b'"}',
    ],
)
def test_manifest_is_bounded_strict_object_without_duplicates(raw):
    with pytest.raises(LabDenied):
        parse_run_manifest(raw)


@pytest.mark.parametrize(
    "version,cluster",
    [(180003, "m2_" + "a" * 32), (180005, "m2_" + "a" * 32), (180004, "different")],
)
def test_server_requires_exact_18_4_and_same_owned_cluster_before_create(version, cluster):
    run = parse_run_manifest(json.dumps(MANIFEST).encode())
    with pytest.raises(LabDenied):
        validate_server_identity(version, cluster, run)


def test_engine_options_explicitly_pin_hostaddr_despite_environment(monkeypatch):
    # Pure factory contract only: no engine/PG connection or password is created.
    from sqlalchemy.engine import URL

    from tests.labs.m2 import runtime_authority as module

    captured = {}
    sentinel = object()

    def capture(url, **options):
        captured.update(options)
        assert url.host == "127.0.0.1"
        return sentinel

    monkeypatch.setenv("PGHOSTADDR", "203.0.113.99")
    monkeypatch.setattr(module, "create_engine", capture)
    result = module._engine(
        URL.create("postgresql+psycopg", host="127.0.0.1"), administration=False
    )
    assert result is sentinel
    assert captured["connect_args"].get("hostaddr") == "127.0.0.1"
    assert captured["pool_size"] == 2
    assert captured["max_overflow"] == 0
    assert captured["hide_parameters"] is True
