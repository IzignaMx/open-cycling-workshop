"""Fixed DB seams for the reviewed disposable ownership consumer, never a CLI.

Imports perform no IO. All tests inject connectors/tool runners. Synchronous calls
remain cooperative; their owner must enforce the original external process deadline.
"""

from __future__ import annotations

import importlib.metadata
import platform
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from scripts.ci.verify_v01 import FULL_POSTGRES_SETTINGS, FULL_PREFLIGHT

PUBLIC_SYNTHETIC_FIXTURE_VALUE = "ocwp-ownership-fixture-only-not-a-secret-20261029"
Clock = Callable[[], int]
ROLE_SQL = (
    "SELECT current_database(), current_user, session_user, "
    "current_setting('server_version_num'), current_setting('server_encoding'), "
    "current_setting('client_encoding'), current_setting('transaction_read_only'), "
    "current_setting('default_transaction_read_only'), inet_server_addr()::text, "
    "inet_server_port(), r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolreplication, "
    "r.rolbypassrls, EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid) "
    "FROM pg_roles r WHERE r.rolname=current_user"
)
IDENTITY_SQL = (
    "SELECT pid, (extract(epoch FROM backend_start)*1000000)::bigint, datname, usename "
    "FROM pg_stat_activity WHERE pid=pg_backend_pid()"
)
SETTINGS_SQL = "SELECT name, current_setting(name) FROM pg_settings WHERE name = ANY(%s)"
TIMEOUT_SQL = "SELECT set_config('statement_timeout', %s, false)"
ABSENCE_SQL = (
    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE pid=%s "
    "AND (extract(epoch FROM backend_start)*1000000)::bigint=%s AND datname=%s AND usename=%s), "
    "current_setting('transaction_read_only'), current_user, session_user, current_database()"
)
# Ordinary-role views redact backend_type for other users. Only database/user
# identity is universally visible: refuse foreign/unknown database-connected
# users, but do not mistake a database-less launcher for an initializer client.
BOOTSTRAP_SQL = (
    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
    "WHERE datname IS NOT NULL AND usename IS DISTINCT FROM current_user)"
)


class DatabaseRefusal(ValueError):
    def __init__(self) -> None:
        super().__init__("ownership_database_unavailable")


def _require(value: bool) -> None:
    if not value:
        raise DatabaseRefusal() from None


def _remaining(clock_ns: Clock, deadline_ns: int) -> int:
    now = clock_ns()
    _require(type(now) is int and type(deadline_ns) is int and 0 <= now < deadline_ns)
    milliseconds = (deadline_ns - now) // 1_000_000
    _require(milliseconds > 0)
    return min(milliseconds, 5000)


def _local_versions() -> tuple[str, str, str]:
    import psycopg

    return platform.python_version(), psycopg.__version__, importlib.metadata.version("pytest")


def _default_connect(**kwargs: Any) -> Any:
    import psycopg

    return psycopg.connect(**kwargs)


def _default_version_runner(argv: list[str], *, timeout: float) -> str:
    from scripts.ci.quote_capacity_micro import full_client

    return full_client(argv, timeout=timeout)


def _endpoint(raw: Any) -> None:
    _require(
        raw.info.host == "127.0.0.1"
        and raw.info.port == 5432
        and raw.info.dbname == "ocwp"
        and raw.info.user == "ocwp"
        and not raw.closed
    )


def _idle(raw: Any) -> None:
    _endpoint(raw)
    _require(raw.info.transaction_status == 0)


def _connect(
    clock_ns: Clock, deadline_ns: int, connect: Callable[..., Any], *, autocommit: bool
) -> Any:
    milliseconds = _remaining(clock_ns, deadline_ns)
    # libpq treats connection timeouts below two seconds as two; never round up.
    seconds = milliseconds // 1000
    _require(seconds >= 2)
    raw = connect(
        host="127.0.0.1",
        port=5432,
        dbname="ocwp",
        user="ocwp",
        password=PUBLIC_SYNTHETIC_FIXTURE_VALUE,
        connect_timeout=seconds,
        autocommit=autocommit,
        options=f"-c default_transaction_read_only=on -c statement_timeout={milliseconds}",
    )
    try:
        _remaining(clock_ns, deadline_ns)
        _idle(raw)
        return raw
    except Exception:
        with suppress(Exception):
            raw.close()
        raise DatabaseRefusal() from None


def _query(
    raw: Any,
    sql: str,
    clock_ns: Clock,
    deadline_ns: int,
    parameters: Any = None,
    *,
    many: bool = False,
) -> Any:
    milliseconds = _remaining(clock_ns, deadline_ns)
    with raw.cursor() as cursor:
        cursor.execute(TIMEOUT_SQL, (str(milliseconds),))
        _remaining(clock_ns, deadline_ns)
        cursor.execute(sql, parameters)
        result = cursor.fetchall() if many else cursor.fetchone()
    _remaining(clock_ns, deadline_ns)
    return result


def _validate_role_row(row: Any) -> None:
    _require(type(row) is tuple and len(row) == 16)
    _require(
        row[:10]
        == ("ocwp", "ocwp", "ocwp", "180004", "UTF8", "UTF8", "on", "on", "127.0.0.1", 5432)
    )
    _require(all(flag is False for flag in row[10:]))


def _role(raw: Any, clock_ns: Clock, deadline_ns: int) -> None:
    _validate_role_row(_query(raw, ROLE_SQL, clock_ns, deadline_ns))


def _backend(row: Any) -> dict[str, object]:
    _require(type(row) is tuple and len(row) == 4)
    _require(type(row[0]) is int and 1 <= row[0] <= 2**31 - 1)
    _require(type(row[1]) is int and 1 <= row[1] < 2**63)
    _require(row[2:] == ("ocwp", "ocwp"))
    return {"pid": row[0], "start_us": row[1], "database": row[2], "role": row[3]}


def preflight(
    clock_ns: Clock,
    deadline_ns: int,
    *,
    connect: Callable[..., Any] | None = None,
    version_runner: Callable[..., str] | None = None,
) -> None:
    """Fixed tools and disposable ordinary role only; no role initialization here."""
    raw = None
    try:
        _require(_local_versions() == (FULL_PREFLIGHT["python"], "3.3.4", "9.1.1"))
        runner = version_runner or _default_version_runner
        commands = [
            (["node", "--version"], "v" + str(FULL_PREFLIGHT["node"])),
            (["pnpm", "--version"], FULL_PREFLIGHT["pnpm"]),
            (
                ["node", "/app/apps/web/node_modules/@playwright/test/cli.js", "--version"],
                "Version " + str(FULL_PREFLIGHT["playwright"]),
            ),
        ]
        for name in ("pg_dump", "pg_restore", "psql"):
            commands.append(([name, "--version"], None))
        commands.append((["git", "--version"], None))
        for command, expected in commands:
            actual = runner(command, timeout=_remaining(clock_ns, deadline_ns) / 1000)
            _remaining(clock_ns, deadline_ns)
            if command[0] == "git":
                _require(actual.startswith("git version ") and len(actual) < 256)
            elif expected is None:
                _require(
                    re.fullmatch(r"[a-z_]+ \(PostgreSQL\) 18\.4(?: \([^\n]+\))?", actual)
                    is not None
                )
            else:
                _require(actual == expected)
        raw = _connect(clock_ns, deadline_ns, connect or _default_connect, autocommit=True)
        _role(raw, clock_ns, deadline_ns)
        settings = _query(
            raw, SETTINGS_SQL, clock_ns, deadline_ns, (list(FULL_POSTGRES_SETTINGS),), many=True
        )
        _require(
            type(settings) is list
            and len(settings) == len(FULL_POSTGRES_SETTINGS)
            and dict(settings) == FULL_POSTGRES_SETTINGS
        )
        bootstrap = _query(raw, BOOTSTRAP_SQL, clock_ns, deadline_ns)
        _require(type(bootstrap) is tuple and len(bootstrap) == 1 and bootstrap[0] is False)
        _idle(raw)
    except Exception:
        raise DatabaseRefusal() from None
    finally:
        if raw is not None:
            try:
                raw.close()
            except Exception:
                raise DatabaseRefusal() from None
    _remaining(clock_ns, deadline_ns)


def open_observer(
    clock_ns: Clock, deadline_ns: int, *, connect: Callable[..., Any] | None = None
) -> Any:
    raw = None
    try:
        raw = _connect(clock_ns, deadline_ns, connect or _default_connect, autocommit=True)
        _role(raw, clock_ns, deadline_ns)
        _backend(_query(raw, IDENTITY_SQL, clock_ns, deadline_ns))
        _require(raw.autocommit is True)
        _idle(raw)
        return raw
    except Exception:
        if raw is not None:
            with suppress(Exception):
                raw.close()
        raise DatabaseRefusal() from None


def observe_absence(
    connection: Any, backend: dict[str, object], clock_ns: Clock, deadline_ns: int
) -> bool:
    try:
        _require(type(backend) is dict and set(backend) == {"pid", "start_us", "database", "role"})
        checked = _backend(tuple(backend[key] for key in ("pid", "start_us", "database", "role")))
        _require(connection.autocommit is True)
        _idle(connection)
        row = _query(
            connection,
            ABSENCE_SQL,
            clock_ns,
            deadline_ns,
            tuple(checked[key] for key in ("pid", "start_us", "database", "role")),
        )
        _idle(connection)
        _require(
            type(row) is tuple
            and len(row) == 5
            and type(row[0]) is bool
            and row[1:] == ("on", "ocwp", "ocwp", "ocwp")
        )
        return not row[0]
    except Exception:
        raise DatabaseRefusal() from None


@dataclass
class CleanSession:
    session: Any
    connection: Any
    raw: Any
    backend: dict[str, object]
    engine: Any

    def close(self, clock_ns: Clock, deadline_ns: int) -> None:
        _remaining(clock_ns, deadline_ns)
        failed = False
        for target in (self.session, self.connection, self.raw):
            try:
                if target is not self.raw or not self.raw.closed:
                    _remaining(clock_ns, deadline_ns)
                    target.close()
                    _remaining(clock_ns, deadline_ns)
            except Exception:
                failed = True
        try:
            _remaining(clock_ns, deadline_ns)
            self.engine.dispose()
            _remaining(clock_ns, deadline_ns)
        except Exception:
            failed = True
        if failed:
            raise DatabaseRefusal() from None


def open_clean_session(
    clock_ns: Clock,
    deadline_ns: int,
    *,
    connect: Callable[..., Any] | None = None,
    engine_factory: Callable[..., Any] | None = None,
    session_factory: Callable[..., Any] | None = None,
) -> CleanSession:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Row
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import NullPool

    raw: Any = None
    connection: Any = None
    engine: Any = None
    session: Any = None
    try:
        raw = _connect(clock_ns, deadline_ns, connect or _default_connect, autocommit=False)
        _role(raw, clock_ns, deadline_ns)
        original = _backend(_query(raw, IDENTITY_SQL, clock_ns, deadline_ns))
        raw.commit()
        _remaining(clock_ns, deadline_ns)
        _idle(raw)
        acquired = False

        def creator() -> Any:
            nonlocal acquired
            _require(not acquired)
            acquired = True
            return raw

        engine = (engine_factory or create_engine)(
            "postgresql+psycopg://", creator=creator, poolclass=NullPool
        )
        connection = engine.connect()
        _remaining(clock_ns, deadline_ns)
        _require(connection.connection.driver_connection is raw)
        role_row = connection.exec_driver_sql(ROLE_SQL).fetchone()
        _validate_role_row(tuple(role_row) if isinstance(role_row, Row) else role_row)
        _remaining(clock_ns, deadline_ns)
        identity_row = connection.exec_driver_sql(IDENTITY_SQL).fetchone()
        observed = _backend(tuple(identity_row) if isinstance(identity_row, Row) else identity_row)
        _require(observed == original)
        connection.commit()
        _remaining(clock_ns, deadline_ns)
        session = (session_factory or Session)(bind=connection, autobegin=False)
        _require(
            session.get_bind() is connection
            and not session.in_transaction()
            and not connection.in_transaction()
            and connection.connection.driver_connection is raw
        )
        _idle(raw)
        _remaining(clock_ns, deadline_ns)
        return CleanSession(session, connection, raw, original, engine)
    except Exception:
        for target in (session, connection, raw):
            if target is not None:
                with suppress(Exception):
                    target.close()
        if engine is not None:
            with suppress(Exception):
                engine.dispose()
        raise DatabaseRefusal() from None


def close_observer(connection: Any, clock_ns: Clock, deadline_ns: int) -> None:
    """No extra cleanup window; the owner handles a native close that blocks."""
    try:
        _remaining(clock_ns, deadline_ns)
        connection.close()
        _remaining(clock_ns, deadline_ns)
    except Exception:
        raise DatabaseRefusal() from None
