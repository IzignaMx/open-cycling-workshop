"""Mock-only DB adapter tests; never connect, spawn or consume H/S."""

from types import SimpleNamespace

import pytest

from scripts.ci import quote_ownership_database as db


class Cursor:
    def __init__(self, raw):
        self.raw = raw
        self.rows = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, sql, parameters=None):
        self.raw.queries.append((sql, parameters))
        if self.raw.fail:
            raise OSError("private database canary")
        self.raw.info.transaction_status = 0 if self.raw.autocommit else 2
        if sql == db.ROLE_SQL:
            self.rows = self.raw.role
        elif sql == db.IDENTITY_SQL:
            self.rows = self.raw.backend
        elif sql == db.SETTINGS_SQL:
            self.rows = list(db.FULL_POSTGRES_SETTINGS.items())
        elif sql == db.BOOTSTRAP_SQL:
            self.rows = (
                any(
                    database is not None and user != "ocwp"
                    for database, user, _ in self.raw.visible_sessions
                ),
            )
        elif sql == db.ABSENCE_SQL:
            self.rows = (self.raw.present, self.raw.readonly, "ocwp", "ocwp", "ocwp")
        else:
            assert sql == db.TIMEOUT_SQL
            self.rows = (str(parameters[0]),)
        self.raw.after_query()
        return self

    def fetchone(self):
        return self.rows

    def fetchall(self):
        return self.rows


class Raw:
    def __init__(self):
        self.info = SimpleNamespace(
            host="127.0.0.1", port=5432, dbname="ocwp", user="ocwp", transaction_status=0
        )
        self.autocommit = True
        self.closed = False
        self.queries = []
        self.fail = False
        self.present = False
        self.readonly = "on"
        self.visible_sessions = []
        self.after_query = lambda: None
        self.role = (
            "ocwp",
            "ocwp",
            "ocwp",
            "180004",
            "UTF8",
            "UTF8",
            "on",
            "on",
            "127.0.0.1",
            5432,
            False,
            False,
            False,
            False,
            False,
            False,
        )
        self.backend = (123, 123456789, "ocwp", "ocwp")
        self.commits = 0

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1
        self.info.transaction_status = 0

    def close(self):
        self.closed = True


@pytest.fixture
def fixture(monkeypatch):
    raw = Raw()
    calls = []
    clock = [0]

    def connect(**kwargs):
        calls.append(kwargs)
        raw.autocommit = kwargs["autocommit"]
        return raw

    monkeypatch.setattr(db, "_local_versions", lambda: ("3.13.14", "3.3.4", "9.1.1"))
    return raw, calls, clock, connect


def version_runner(argv, *, timeout):
    assert 0 < timeout <= 5
    values = {
        "node": "v22.16.0",
        "pnpm": "11.17.0",
        "git": "git version 2.48.1",
        "pg_dump": "pg_dump (PostgreSQL) 18.4",
        "pg_restore": "pg_restore (PostgreSQL) 18.4",
        "psql": "psql (PostgreSQL) 18.4",
    }
    return "Version 1.62.0" if len(argv) > 2 else values[argv[0]]


def test_preflight_uses_fixed_ordinary_readonly_identity_and_closes(fixture):
    raw, calls, clock, connect = fixture
    db.preflight(lambda: clock[0], 65_000_000_000, connect=connect, version_runner=version_runner)
    assert raw.closed and len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1" and calls[0]["dbname"] == calls[0]["user"] == "ocwp"
    assert calls[0]["password"] == db.PUBLIC_SYNTHETIC_FIXTURE_VALUE
    assert len(calls[0]["password"]) >= 32
    assert (
        calls[0]["autocommit"] is True and "default_transaction_read_only=on" in calls[0]["options"]
    )
    assert calls[0]["connect_timeout"] <= 5
    assert {sql for sql, _ in raw.queries} <= {
        db.ROLE_SQL,
        db.SETTINGS_SQL,
        db.TIMEOUT_SQL,
        db.BOOTSTRAP_SQL,
    }


@pytest.mark.parametrize(
    "index,value",
    [
        (0, "wrong"),
        (1, "postgres"),
        (2, "postgres"),
        (3, "180003"),
        (4, "LATIN1"),
        (6, "off"),
        (7, "off"),
        (8, "10.0.0.1"),
        (9, 5433),
        *[(i, True) for i in range(10, 16)],
    ],
)
def test_preflight_refuses_role_membership_or_identity_mismatch(fixture, index, value):
    raw, _, clock, connect = fixture
    row = list(raw.role)
    row[index] = value
    raw.role = tuple(row)
    with pytest.raises(db.DatabaseRefusal) as caught:
        db.preflight(
            lambda: clock[0], 65_000_000_000, connect=connect, version_runner=version_runner
        )
    assert str(caught.value) == "ownership_database_unavailable" and raw.closed


def test_connect_cannot_round_remaining_up_or_renew_clock(fixture):
    _, calls, clock, connect = fixture
    with pytest.raises(db.DatabaseRefusal):
        db.open_observer(lambda: clock[0], 1_999_999_999, connect=connect)
    assert not calls


def test_observer_reads_fresh_exact_backend_and_uses_original_deadline(fixture):
    raw, _, clock, connect = fixture
    observer = db.open_observer(lambda: clock[0], 8_000_000_000, connect=connect)
    backend = {"pid": 123, "start_us": 123456789, "database": "ocwp", "role": "ocwp"}
    assert db.observe_absence(observer, backend, lambda: clock[0], 8_000_000_000) is True
    query = [params for sql, params in raw.queries if sql == db.ABSENCE_SQL][-1]
    assert query == (123, 123456789, "ocwp", "ocwp")
    assert raw.autocommit and raw.info.transaction_status == 0
    raw.present = True
    assert db.observe_absence(observer, backend, lambda: clock[0], 8_000_000_000) is False
    raw.after_query = lambda: clock.__setitem__(0, 8_000_000_001)
    with pytest.raises(db.DatabaseRefusal):
        db.observe_absence(observer, backend, lambda: clock[0], 8_000_000_000)


@pytest.mark.parametrize("fault", ["query", "transaction", "autocommit", "wrong_role", "bool_pid"])
def test_observer_unknown_is_not_absence(fixture, fault):
    raw, _, clock, connect = fixture
    observer = db.open_observer(lambda: clock[0], 8_000_000_000, connect=connect)
    backend = {"pid": 123, "start_us": 123456789, "database": "ocwp", "role": "ocwp"}
    if fault == "query":
        raw.fail = True
    elif fault == "transaction":
        raw.info.transaction_status = 2
    elif fault == "autocommit":
        raw.autocommit = False
    elif fault == "wrong_role":
        backend["role"] = "postgres"
    else:
        backend["pid"] = True
    with pytest.raises(db.DatabaseRefusal) as caught:
        db.observe_absence(observer, backend, lambda: clock[0], 8_000_000_000)
    assert str(caught.value) == "ownership_database_unavailable"


def make_factories(raw, *, replaced=False, dirty=False):
    observed = {}

    class Connection:
        def __init__(self):
            self.connection = SimpleNamespace(driver_connection=Raw() if replaced else raw)
            self.dirty = dirty
            self.closed = False

        def exec_driver_sql(self, sql):
            return Cursor(raw).execute(sql)

        def commit(self):
            raw.commit()

        def in_transaction(self):
            return self.dirty

        def close(self):
            self.closed = True

    connection = Connection()

    class Engine:
        def connect(self):
            return connection

        def dispose(self):
            observed["disposed"] = True

    def engine_factory(url, **kwargs):
        observed.update(url=url, **kwargs)
        assert kwargs["poolclass"].__name__ == "NullPool"
        assert kwargs["creator"]() is raw
        return Engine()

    class Session:
        def __init__(self, *, bind, autobegin):
            assert bind is connection and autobegin is False
            self.closed = False

        def get_bind(self):
            return connection

        def in_transaction(self):
            return False

        def close(self):
            self.closed = True

    return observed, engine_factory, Session


def test_clean_session_retains_single_backend_without_autobegin(fixture):
    raw, calls, clock, connect = fixture
    observed, engine_factory, session_factory = make_factories(raw)
    clean = db.open_clean_session(
        lambda: clock[0],
        8_000_000_000,
        connect=connect,
        engine_factory=engine_factory,
        session_factory=session_factory,
    )
    assert len(calls) == 1 and clean.raw is raw
    assert clean.backend == {"pid": 123, "start_us": 123456789, "database": "ocwp", "role": "ocwp"}
    assert not clean.session.in_transaction() and not clean.connection.in_transaction()
    assert raw.info.transaction_status == 0 and raw.commits >= 2
    with pytest.raises(db.DatabaseRefusal):
        observed["creator"]()
    clean.close(lambda: clock[0], 8_000_000_000)
    assert clean.session.closed and clean.connection.closed and raw.closed and observed["disposed"]


@pytest.mark.parametrize("fault", ["replaced", "dirty"])
def test_clean_session_refuses_connection_replacement_or_transaction(fixture, fault):
    raw, _, clock, connect = fixture
    _, engine_factory, session_factory = make_factories(raw, **{fault: True})
    with pytest.raises(db.DatabaseRefusal):
        db.open_clean_session(
            lambda: clock[0],
            8_000_000_000,
            connect=connect,
            engine_factory=engine_factory,
            session_factory=session_factory,
        )
    assert raw.closed


def test_observer_rechecks_live_readonly_on_each_observation(fixture):
    raw, _, clock, connect = fixture
    observer = db.open_observer(lambda: clock[0], 8_000_000_000, connect=connect)
    raw.readonly = "off"
    with pytest.raises(db.DatabaseRefusal):
        db.observe_absence(
            observer,
            {"pid": 123, "start_us": 123456789, "database": "ocwp", "role": "ocwp"},
            lambda: clock[0],
            8_000_000_000,
        )


def test_clean_session_rechecks_readonly_after_engine_initialization(fixture):
    raw, _, clock, connect = fixture
    _, factory, session_factory = make_factories(raw)

    def changed_engine(*args, **kwargs):
        engine = factory(*args, **kwargs)
        values = list(raw.role)
        values[6] = "off"
        raw.role = tuple(values)
        return engine

    with pytest.raises(db.DatabaseRefusal):
        db.open_clean_session(
            lambda: clock[0],
            8_000_000_000,
            connect=connect,
            engine_factory=changed_engine,
            session_factory=session_factory,
        )
    assert raw.closed


def test_observer_close_reports_late_close_without_new_deadline(fixture):
    raw, _, clock, _ = fixture

    def late_close():
        raw.closed = True
        clock[0] = 8_000_000_001

    raw.close = late_close
    with pytest.raises(db.DatabaseRefusal):
        db.close_observer(raw, lambda: clock[0], 8_000_000_000)
    assert raw.closed


def test_observer_close_no_call_after_expiry(fixture):
    raw, _, clock, _ = fixture
    clock[0] = 8_000_000_000
    with pytest.raises(db.DatabaseRefusal):
        db.close_observer(raw, lambda: clock[0], 8_000_000_000)
    assert not raw.closed


@pytest.mark.parametrize("bad_endpoint", [False, True])
def test_failed_open_sanitizes_secondary_close_error(fixture, bad_endpoint):
    raw, _, clock, connect = fixture
    if bad_endpoint:
        raw.info.host = "wrong"
    else:
        raw.fail = True

    def fail_close():
        raise OSError("private close canary")

    raw.close = fail_close
    with pytest.raises(db.DatabaseRefusal) as caught:
        db.open_observer(lambda: clock[0], 8_000_000_000, connect=connect)
    assert str(caught.value) == "ownership_database_unavailable"


def sqlalchemy_row(values):
    from sqlalchemy.engine import Row
    from sqlalchemy.engine.result import SimpleResultMetaData

    metadata = SimpleResultMetaData([f"column_{index}" for index in range(len(values))])
    return Row(metadata, None, metadata._key_to_index, values)


def test_clean_session_accepts_actual_sqlalchemy_rows_only_at_sa_boundary(fixture):
    raw, _, clock, connect = fixture
    _, factory, session_factory = make_factories(raw)

    def row_engine(*args, **kwargs):
        engine = factory(*args, **kwargs)
        connection = engine.connect()
        execute = connection.exec_driver_sql

        def row_execute(sql):
            result = execute(sql).fetchone()
            return SimpleNamespace(fetchone=lambda: sqlalchemy_row(result))

        connection.exec_driver_sql = row_execute
        return engine

    clean = db.open_clean_session(
        lambda: clock[0],
        8_000_000_000,
        connect=connect,
        engine_factory=row_engine,
        session_factory=session_factory,
    )
    assert clean.raw is raw and clean.backend["pid"] == 123
    clean.close(lambda: clock[0], 8_000_000_000)


def test_raw_psycopg_boundary_still_refuses_sqlalchemy_row(fixture):
    raw, _, clock, connect = fixture
    raw.role = sqlalchemy_row(raw.role)
    with pytest.raises(db.DatabaseRefusal):
        db.open_observer(lambda: clock[0], 8_000_000_000, connect=connect)
    assert raw.closed


@pytest.mark.parametrize(
    "row,refused",
    [
        (("postgres", "postgres", None), True),
        ((None, "postgres", "logical replication launcher"), False),
        (("postgres", None, None), True),
        (("ocwp", "ocwp", "client backend"), False),
    ],
)
def test_preflight_conservatively_checks_only_universally_visible_session_identity(
    fixture, row, refused
):
    raw, _, clock, connect = fixture
    raw.visible_sessions = [row]
    assert "datname IS NOT NULL" in db.BOOTSTRAP_SQL
    assert "usename IS DISTINCT FROM current_user" in db.BOOTSTRAP_SQL
    assert "backend_type" not in db.BOOTSTRAP_SQL
    if refused:
        with pytest.raises(db.DatabaseRefusal):
            db.preflight(
                lambda: clock[0], 65_000_000_000, connect=connect, version_runner=version_runner
            )
    else:
        db.preflight(
            lambda: clock[0], 65_000_000_000, connect=connect, version_runner=version_runner
        )
    assert raw.closed
