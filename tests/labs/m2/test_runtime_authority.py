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


@pytest.fixture
def fake_bootstrap(monkeypatch):
    """Exercise real bootstrap control flow, never a DB/secret-file implementation.

    Fixed public bytes are format fixtures, not generated or usable credentials.
    Unknown SQL is recorded and rejected; no fallback reaches a real engine.
    """
    from types import SimpleNamespace
    from uuid import UUID

    from tests.labs.m2 import authority, runtime_authority

    state = SimpleNamespace(
        version=180004,
        cluster="m2_" + MANIFEST["nonce"],
        user="m2_lab",
        exists=False,
        oid=123,
        failure=None,
        events=[],
    )
    database = state.cluster
    statements = {
        "SHOW server_version_num": "version",
        "SHOW cluster_name": "cluster",
        "SELECT current_user": "user",
        "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname=:name)": "exists",
        "SELECT oid FROM pg_database WHERE datname=:name": "oid",
        f'CREATE DATABASE "{database}" TEMPLATE template0': "create",
        f"COMMENT ON DATABASE \"{database}\" IS 'm2-owned:{MANIFEST['nonce']}'": "comment",
    }

    class Connection:
        def __enter__(self):
            state.events.append("connect")
            return self

        def __exit__(self, *args):
            state.events.append("disconnect")

        def scalar(self, statement, parameters=None):
            operation = statements.get(str(statement), "unexpected_sql")
            state.events.append(operation)
            assert operation in ("version", "cluster", "user", "exists", "oid")
            if operation in ("exists", "oid"):
                assert parameters == {"name": database}
            if state.failure == operation:
                raise RuntimeError("Public synthetic database failure")
            return getattr(state, operation)

        def execute(self, statement):
            operation = statements.get(str(statement), "unexpected_sql")
            state.events.append(operation)
            assert operation in ("create", "comment")
            if state.failure == operation:
                raise RuntimeError("Public synthetic database failure")
            state.events.append(operation + "_acknowledged")

    class AdminEngine:
        def connect(self):
            return Connection()

        def dispose(self):
            state.events.append("dispose_admin")

    data_engine = object()

    def engine(url, *, administration):
        state.events.append("admin_engine" if administration else "data_engine")
        assert url.host == "127.0.0.1" and url.port == 5432 and url.username == "m2_lab"
        assert url.database == ("postgres" if administration else database)
        return AdminEngine() if administration else data_engine

    def private_input(path, maximum):
        if path == runtime_authority.MANIFEST_FILE:
            assert maximum == 4096
            return json.dumps(MANIFEST).encode()
        assert path == runtime_authority.PASSWORD_FILE and maximum == 64
        return b"0" * 64

    def forbidden(*args, **kwargs):
        state.events.append("forbidden_resource_boundary")
        raise AssertionError("No real engine or fixture initialization allowed")

    monkeypatch.setattr(runtime_authority, "_engine", engine)
    monkeypatch.setattr(runtime_authority, "create_engine", forbidden)
    monkeypatch.setattr(runtime_authority, "read_private_file", private_input)
    monkeypatch.setattr(runtime_authority.PostgresLabAuthority, "_initialize", forbidden)
    monkeypatch.setattr(authority, "uuid4", lambda: UUID("00000000-0000-4000-8000-000000000001"))
    monkeypatch.setattr(authority, "_clock", lambda: (1000.0, 1000.0))
    subject = runtime_authority.PostgresLabAuthority.__new__(runtime_authority.PostgresLabAuthority)

    def refused():
        with pytest.raises(LabDenied) as failure:
            runtime_authority.PostgresLabAuthority.__init__(subject)
        assert failure.value.status == 503
        assert subject._created_oid is None
        assert subject.database_removed is False
        assert state.events[-2:] == ["disconnect", "dispose_admin"]
        # Any attempted DROP would require another admin engine/SQL operation.
        assert state.events.count("admin_engine") == 1
        assert "data_engine" not in state.events
        assert "unexpected_sql" not in state.events
        assert "forbidden_resource_boundary" not in state.events

    return state, subject, refused, data_engine


def test_existing_database_refused_without_create_comment_or_drop(fake_bootstrap):
    state, _subject, refused, _engine = fake_bootstrap
    state.exists = True
    refused()
    assert state.events == [
        "admin_engine",
        "connect",
        "version",
        "cluster",
        "user",
        "exists",
        "disconnect",
        "dispose_admin",
    ]


@pytest.mark.parametrize(
    "field,value,queried",
    [
        ("version", 180003, ["version", "cluster"]),
        ("version", 180005, ["version", "cluster"]),
        ("cluster", "different-public-fixture", ["version", "cluster"]),
        ("user", "different_public_role", ["version", "cluster", "user"]),
    ],
)
def test_bootstrap_identity_mismatch_refuses_before_existing_lookup_or_create(
    fake_bootstrap, field, value, queried
):
    state, _subject, refused, _engine = fake_bootstrap
    setattr(state, field, value)
    refused()
    assert state.events == ["admin_engine", "connect", *queried, "disconnect", "dispose_admin"]


@pytest.mark.parametrize(
    "failure,oid", [("comment", 123), ("oid", 123), (None, None), (None, 0), (None, True)]
)
def test_acknowledged_create_without_oid_witness_never_drops_uncertain_database(
    fake_bootstrap, failure, oid
):
    state, _subject, refused, _engine = fake_bootstrap
    state.failure, state.oid = failure, oid
    refused()
    assert "create_acknowledged" in state.events
    expected = [
        "admin_engine",
        "connect",
        "version",
        "cluster",
        "user",
        "exists",
        "create",
        "create_acknowledged",
        "comment",
    ]
    if failure != "comment":
        expected += ["comment_acknowledged", "oid"]
    assert state.events == [*expected, "disconnect", "dispose_admin"]


def test_fake_bootstrap_positive_control_installs_only_acknowledged_oid(fake_bootstrap):
    """Control proving the fixture permits actual successful _build_engine flow."""
    state, subject, _refused, data_engine = fake_bootstrap
    subject.owned_run = subject._admin_url = subject._created_oid = None
    subject.database_removed = False
    assert subject._build_engine() is data_engine
    assert subject._created_oid == 123
    assert subject.database_removed is False
    assert state.events == [
        "admin_engine",
        "connect",
        "version",
        "cluster",
        "user",
        "exists",
        "create",
        "create_acknowledged",
        "comment",
        "comment_acknowledged",
        "oid",
        "disconnect",
        "dispose_admin",
        "data_engine",
    ]
