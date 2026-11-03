"""Prepared PostgreSQL runtime path. Import/pure tests never connect or issue secrets.

Only the future explicitly approved entrypoint may create this authority. It
cannot accept a DSN, existing engine, database name, or connector configuration.
"""

from __future__ import annotations

import json
import os
import re
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.orm import Session

from tests.labs.m2.authority import LabAuthority, LabDenied

PRIVATE = Path("/run/m2-private")
MANIFEST_FILE = PRIVATE / "run.json"
PASSWORD_FILE = PRIVATE / "pg-password"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True)
class OwnedRun:
    nonce: str
    source_commit: str
    source_tree: str

    @property
    def database(self) -> str:
        return "m2_" + self.nonce


def _closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LabDenied(503)
        result[key] = value
    return result


def parse_run_manifest(raw: bytes) -> OwnedRun:
    try:
        if len(raw) > 4096:
            raise ValueError
        value = json.loads(raw, object_pairs_hook=_closed_object)
        if (
            type(value) is not dict
            or set(value) != {"schema", "nonce", "source_commit", "source_tree"}
            or type(value["schema"]) is not int
            or value["schema"] != 1
        ):
            raise ValueError
        for key, pattern in [("nonce", _HEX32), ("source_commit", _HEX40), ("source_tree", _HEX40)]:
            if not isinstance(value[key], str) or not pattern.fullmatch(value[key]):
                raise ValueError
        return OwnedRun(value["nonce"], value["source_commit"], value["source_tree"])
    except Exception:
        raise LabDenied(503) from None


def validate_server_identity(version: object, cluster: object, run: OwnedRun) -> None:
    if type(version) is not int or version != 180004 or cluster != run.database:
        raise LabDenied(503)


def read_private_file(path: Path, maximum: int) -> bytes:
    """Fixed trusted-runtime input, never connector path input; bounded no-follow read."""
    descriptor = None
    try:
        if path not in (MANIFEST_FILE, PASSWORD_FILE) or os.geteuid() <= 0:
            raise ValueError
        parent = path.parent.lstat()
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700
        ):
            raise ValueError
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) not in (0o400, 0o600)
            or not 0 < info.st_size <= maximum
        ):
            raise ValueError
        result = os.read(descriptor, maximum + 1)
        if len(result) > maximum or len(result) != info.st_size:
            raise ValueError
        return result
    except Exception:
        raise LabDenied(503) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _engine(url: URL, *, administration: bool) -> Engine:
    return create_engine(
        url,
        pool_size=1 if administration else 2,
        max_overflow=0,
        pool_timeout=2,
        isolation_level="AUTOCOMMIT" if administration else "READ COMMITTED",
        echo=False,
        hide_parameters=True,
        connect_args={
            "hostaddr": "127.0.0.1",
            "connect_timeout": 2,
            "options": "-c statement_timeout=5000 -c lock_timeout=2000",
        },
    )


class PostgresLabAuthority(LabAuthority):
    """Runtime-only creation from fixed owned files; no constructor configuration."""

    def __init__(self) -> None:
        self.owned_run: OwnedRun | None = None
        self._admin_url: URL | None = None
        self._created_oid: int | None = None
        self.database_removed = False
        try:
            super().__init__()
        except Exception:
            if self._created_oid is not None:
                with suppress(Exception):
                    self._drop_owned_database()
            raise LabDenied(503) from None

    @classmethod
    def create_owned(cls) -> PostgresLabAuthority:
        return cls()

    @property
    def run_deadline(self) -> float:
        return self._run_until

    def _server(self, connection: Connection) -> None:
        if self.owned_run is None:
            raise LabDenied(503)
        version = int(connection.scalar(text("SHOW server_version_num")))
        cluster = connection.scalar(text("SHOW cluster_name"))
        validate_server_identity(version, cluster, self.owned_run)
        if connection.scalar(text("SELECT current_user")) != "m2_lab":
            raise LabDenied(503)

    def _build_engine(self) -> Engine:
        self.owned_run = parse_run_manifest(read_private_file(MANIFEST_FILE, 4096))
        raw = read_private_file(PASSWORD_FILE, 64)
        if re.fullmatch(rb"[0-9a-f]{64}", raw) is None:
            raise LabDenied(503)
        self._admin_url = URL.create(
            "postgresql+psycopg",
            username="m2_lab",
            password=raw.decode("ascii"),
            host="127.0.0.1",
            port=5432,
            database="postgres",
        )
        del raw
        admin = _engine(self._admin_url, administration=True)
        database = self.owned_run.database
        try:
            with admin.connect() as connection:
                self._server(connection)
                exists = connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname=:name)"),
                    {"name": database},
                )
                if exists:
                    raise LabDenied(503)
                # Identifiers come exclusively from the closed lower-hex manifest.
                connection.execute(text(f'CREATE DATABASE "{database}" TEMPLATE template0'))
                connection.execute(
                    text(f"COMMENT ON DATABASE \"{database}\" IS 'm2-owned:{self.owned_run.nonce}'")
                )
                oid = connection.scalar(
                    text("SELECT oid FROM pg_database WHERE datname=:name"), {"name": database}
                )
                if type(oid) is not int or oid <= 0:
                    raise LabDenied(503)
                self._created_oid = oid  # Process-local successful creation witness.
        finally:
            admin.dispose()
        return _engine(self._admin_url.set(database=database), administration=False)

    def _initialize(self) -> None:
        with self._engine.connect() as connection:
            self._server(connection)
            # template0 must contain no non-system relations before any fixture schema.
            occupied = connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
                    "AND n.nspname NOT LIKE 'pg_toast%' AND n.nspname NOT LIKE 'pg_temp_%' "
                    "AND c.relkind IN ('r','p','v','m','S','f'))"
                )
            )
            if occupied:
                raise LabDenied(503)
        super()._initialize()

    def _set_transaction_budgets(self, executor: Session | Connection) -> None:
        if self._engine.dialect.name != "postgresql":
            raise LabDenied(503)
        # PostgreSQL18 transaction_timeout is installed before any authority SQL.
        executor.execute(text("SET LOCAL transaction_timeout = '8s'"))
        executor.execute(text("SET LOCAL lock_timeout = '2s'"))
        executor.execute(text("SET LOCAL statement_timeout = '5s'"))

    def _drop_owned_database(self) -> None:
        if self.owned_run is None or self._created_oid is None or self._admin_url is None:
            raise LabDenied(503)
        admin = _engine(self._admin_url, administration=True)
        try:
            with admin.connect() as connection:
                self._server(connection)
                row = connection.execute(
                    text(
                        "SELECT d.oid, r.rolname, shobj_description(d.oid, 'pg_database') "
                        "FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba "
                        "WHERE d.datname=:name"
                    ),
                    {"name": self.owned_run.database},
                ).one_or_none()
                if (
                    row is None
                    or row[0] != self._created_oid
                    or row[1] != "m2_lab"
                    or row[2] != "m2-owned:" + self.owned_run.nonce
                ):
                    raise LabDenied(503)
                # No FORCE/termination, wildcard drop or existing-database cleanup.
                connection.execute(text(f'DROP DATABASE "{self.owned_run.database}"'))
                if connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname=:name)"),
                    {"name": self.owned_run.database},
                ):
                    raise LabDenied(503)
                self.database_removed = True
        finally:
            admin.dispose()

    def close(self) -> None:
        if self.database_removed and self.cleanup_complete:
            return
        failure = False
        try:
            super().close()
        except Exception:
            failure = True
        try:
            self._drop_owned_database()
        except Exception:
            failure = True
        self._admin_url = None
        if failure or not self.database_removed:
            self._cleanup_complete = False
            raise LabDenied(503) from None
