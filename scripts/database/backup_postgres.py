"""Database-only logical backups. A readable archive is not a proven recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

Runner = Callable[..., None]
EngineFactory = Callable[..., Engine]
ROOT = Path(__file__).resolve().parents[2]
DUMP_NAME = "database.dump"
MANIFEST_NAME = "manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
# Official PostgreSQL container metadata; none are libpq connection defaults.
POSTGRES_IMAGE_ENV = {"PG_MAJOR", "PG_VERSION", "PG_SHA256", "PGDATA"}
URL_OPTIONS = {
    "sslmode": "PGSSLMODE",
    "sslrootcert": "PGSSLROOTCERT",
    "sslcert": "PGSSLCERT",
    "sslkey": "PGSSLKEY",
    "channel_binding": "PGCHANNELBINDING",
    "connect_timeout": "PGCONNECT_TIMEOUT",
}


class BackupError(RuntimeError):
    """An operator-safe message: never include raw database/subprocess exceptions."""


def _libpq_env(database_url: str) -> dict[str, str]:
    # psycopg uses in-process libpq defaults while child tools get a new env.
    # Refuse ambient overrides so preflight and restore cannot reach different hosts.
    if any(key.startswith("PG") and key not in POSTGRES_IMAGE_ENV for key in os.environ):
        raise BackupError("unset ambient PostgreSQL connection variables before this operation")
    try:
        url = make_url(database_url)
    except Exception:
        raise ValueError("invalid PostgreSQL database URL") from None
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("PostgreSQL database URL required")
    if not url.database or not url.username:
        raise ValueError("explicit database name and user are required")
    if any(key not in URL_OPTIONS for key in url.query):
        raise ValueError("unsupported PostgreSQL URL option")
    # PG* can redirect libpq through a service file or override TLS unexpectedly.
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PG", "OCWP_"))}
    env.update(
        PGHOST=url.host or "localhost",
        PGPORT=str(url.port or 5432),
        PGUSER=url.username,
        PGDATABASE=url.database,
        PGCONNECT_TIMEOUT="10",
        PGAPPNAME="ocwp-backup",
    )
    if url.password is not None:
        env["PGPASSWORD"] = url.password
    for key, value in url.query.items():
        if not isinstance(value, str):
            raise ValueError("repeated PostgreSQL URL options are unsupported")
        env[URL_OPTIONS[key]] = value
    try:
        if not 1 <= int(env["PGCONNECT_TIMEOUT"]) <= 60:
            raise ValueError
    except ValueError:
        raise ValueError("connect_timeout must be an integer from 1 to 60 seconds") from None
    return env


def _run(command: list[str], *, env: dict[str, str]) -> None:
    try:
        # Dump/restore errors can include row contents. Do not print or retain stderr.
        subprocess.run(
            command,
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3600,
        )
    except subprocess.TimeoutExpired:
        raise BackupError("PostgreSQL command timed out; no success is claimed") from None
    except (OSError, subprocess.CalledProcessError):
        raise BackupError(
            "PostgreSQL command failed; check client versions, access and storage"
        ) from None


def _invoke(runner: Runner, command: list[str], env: dict[str, str]) -> None:
    try:
        runner(command, env=env)
    except BackupError:
        raise
    except Exception:
        raise BackupError("PostgreSQL command failed; no success is claimed") from None


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup_postgres(
    database_url: str,
    output: Path,
    *,
    runner: Runner = _run,
    snapshot: str | None = None,
) -> Path:
    """Write a new custom archive atomically; refuse any existing destination."""
    env = _libpq_env(database_url)
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.exists() or output.is_symlink():
        raise BackupError("backup destination already exists")
    if snapshot is not None and not re.fullmatch(r"[0-9A-Fa-f-]+", snapshot):
        raise BackupError("invalid exported database snapshot")
    fd, temporary_name = tempfile.mkstemp(prefix=".ocwp-dump-", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        command = ["pg_dump", "--format=custom", "--no-password", "--file", str(temporary)]
        if snapshot is not None:
            command.extend(["--snapshot", snapshot])
        _invoke(runner, command, env)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise BackupError("pg_dump did not produce a non-empty backup")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        # A link is an atomic no-clobber publication on the same filesystem.
        os.link(temporary, output)
    except FileExistsError:
        raise BackupError("backup destination already exists") from None
    finally:
        temporary.unlink(missing_ok=True)
    return output


def verify_postgres_backup(dump: Path, *, runner: Runner = _run) -> None:
    """Check archive TOC readability only, NOT data integrity or restorability."""
    if dump.is_symlink() or not dump.is_file() or dump.stat().st_size == 0:
        raise BackupError("backup file is missing, unsafe or empty")
    _invoke(runner, ["pg_restore", "--list", str(dump.absolute())], _offline_env())


def _offline_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith(("PG", "OCWP_"))}


def _engine(database_url: str, engine_factory: EngineFactory) -> Engine:
    env = _libpq_env(database_url)
    url = make_url(database_url).set(drivername="postgresql+psycopg")
    url = url.set(host=url.host or "localhost", port=url.port or 5432)
    try:
        return engine_factory(
            url,
            echo=False,
            hide_parameters=True,
            connect_args={
                "connect_timeout": int(env["PGCONNECT_TIMEOUT"]),
                "application_name": "ocwp-backup",
            },
        )
    except Exception:
        raise BackupError("database connection configuration is invalid") from None


def _database_metadata(connection: Connection) -> dict[str, Any]:
    version = int(connection.execute(text("SHOW server_version_num")).scalar_one())
    foreign_tables = connection.execute(
        text("SELECT count(*) FROM pg_catalog.pg_foreign_table")
    ).scalar_one()
    if foreign_tables:
        raise BackupError("foreign table data is outside this backup tool's supported scope")
    tables = connection.execute(
        text(
            "SELECT n.nspname, c.relname FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('r', 'p', 'm') "
            "AND n.nspname <> 'information_schema' AND n.nspname !~ '^pg_' "
            "ORDER BY n.nspname, c.relname"
        )
    ).all()
    if ("public", "alembic_version") not in tables:
        raise BackupError("source has no public Alembic schema revision")
    revisions = list(
        connection.execute(
            text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
        )
        .scalars()
        .all()
    )
    if not revisions:
        raise BackupError("source Alembic revision is empty")
    quote = connection.dialect.identifier_preparer.quote_identifier
    counts = []
    for schema, name in tables:
        count = connection.exec_driver_sql(
            f"SELECT count(*) FROM {quote(schema)}.{quote(name)}"
        ).scalar_one()
        counts.append({"schema": schema, "name": name, "rows": int(count)})
    return {"postgres_version_num": version, "schema_revisions": revisions, "tables": counts}


def _application_version() -> str:
    with (ROOT / "services/platform/pyproject.toml").open("rb") as stream:
        value = tomllib.load(stream)["project"]["version"]
    if not isinstance(value, str) or not value:
        raise BackupError("application version is unavailable")
    return value


def _schema_heads() -> list[str]:
    return sorted(ScriptDirectory(str(ROOT / "services/platform/migrations")).get_heads())


def _write_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    descriptor = os.open(directory / MANIFEST_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def create_backup_bundle(
    database_url: str,
    directory: Path,
    *,
    runner: Runner = _run,
    engine_factory: EngineFactory = create_engine,
    snapshot_observer: Callable[[Connection], None] | None = None,
) -> Path:
    """Capture counts/dump in one snapshot; optionally observe it before dumping.

    The observer must only read and retain bounded references in caller-owned
    memory. It cannot change the database-only manifest or the completion claim.
    An observer failure aborts this generation before publication.
    """
    _libpq_env(database_url)
    directory = directory.absolute()
    try:
        directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    except FileExistsError:
        raise BackupError("backup generation already exists; choose a new directory") from None
    engine = _engine(database_url, engine_factory)
    try:
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                connection.execute(text("SET LOCAL row_security = off"))
                connection.execute(text("SET LOCAL statement_timeout = '1h'"))
                snapshot_started_at = datetime.now(UTC).isoformat()
                snapshot = connection.execute(text("SELECT pg_export_snapshot()")).scalar_one()
                metadata = _database_metadata(connection)
                if snapshot_observer is not None:
                    snapshot_observer(connection)
                dump = backup_postgres(
                    database_url, directory / DUMP_NAME, runner=runner, snapshot=snapshot
                )
        verify_postgres_backup(dump, runner=runner)
        manifest = {
            "format_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "snapshot_started_at": snapshot_started_at,
            "scope": "postgresql-only",
            "application": {
                "name": "open-cycling-workshop-platform",
                "version": _application_version(),
            },
            "database": metadata,
            "archive": {"file": DUMP_NAME, "bytes": dump.stat().st_size, "sha256": _sha256(dump)},
            "restore_tested": False,
            "excludes": ["external-blob-payloads", "client-indexeddb", "configuration-and-secrets"],
        }
        # Manifest is the completion marker; missing/partial manifests always fail verification.
        _write_manifest(directory, manifest)
    except BackupError:
        raise
    except Exception:
        raise BackupError("backup failed; incomplete generation must not be used") from None
    finally:
        engine.dispose()
    return directory


def _require(condition: object) -> None:
    if not condition:
        raise ValueError("invalid manifest field")


def _manifest(directory: Path) -> dict[str, Any]:
    path = directory / MANIFEST_NAME
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise BackupError("backup manifest is missing, unsafe or oversized")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        _require(isinstance(value, dict))
        _require(value["format_version"] == 1 and type(value["format_version"]) is int)
        _require(value["scope"] == "postgresql-only")
        _require(value["restore_tested"] is False)
        _require(isinstance(value["created_at"], str))
        _require(datetime.fromisoformat(value["created_at"]).tzinfo is not None)
        _require(isinstance(value["snapshot_started_at"], str))
        _require(datetime.fromisoformat(value["snapshot_started_at"]).tzinfo is not None)
        _require(value["application"]["name"] == "open-cycling-workshop-platform")
        _require(isinstance(value["application"]["version"], str))
        archive = value["archive"]
        _require(archive["file"] == DUMP_NAME)
        _require(type(archive["bytes"]) is int and archive["bytes"] > 0)
        _require(re.fullmatch(r"[a-f0-9]{64}", archive["sha256"]))
        db = value["database"]
        _require(type(db["postgres_version_num"]) is int and db["postgres_version_num"] >= 100000)
        revisions = db["schema_revisions"]
        _require(isinstance(revisions, list) and revisions)
        _require(all(isinstance(revision, str) and revision for revision in revisions))
        _require(revisions == sorted(set(revisions)))
        _require(isinstance(db["tables"], list) and db["tables"])
        names = set()
        for table in db["tables"]:
            _require(isinstance(table["schema"], str) and table["schema"])
            _require(isinstance(table["name"], str) and table["name"])
            _require(type(table["rows"]) is int and table["rows"] >= 0)
            _require((table["schema"], table["name"]) not in names)
            names.add((table["schema"], table["name"]))
        _require(("public", "alembic_version") in names)
    except (AssertionError, KeyError, TypeError, ValueError, OSError):
        raise BackupError("backup manifest is invalid or unsupported") from None
    return cast(dict[str, Any], value)


def verify_backup_bundle(directory: Path, *, runner: Runner = _run) -> dict[str, Any]:
    """Verify SHA256, size and archive TOC. This deliberately does not claim recovery."""
    manifest = _manifest(directory)
    dump = directory / DUMP_NAME
    if dump.is_symlink() or not dump.is_file():
        raise BackupError("backup integrity failure: archive missing or unsafe")
    archive = manifest["archive"]
    if dump.stat().st_size != archive["bytes"] or _sha256(dump) != archive["sha256"]:
        raise BackupError("backup integrity failure: archive size or SHA256 differs")
    verify_postgres_backup(dump, runner=runner)
    return {"status": "integrity_checked_not_restored", "manifest": manifest}


# Fresh template databases contain public, plpgsql and built-ins in system schemas.
# Refuse even empty tables, views, sequences, routines, types, extra schemas/extensions,
# large objects and foreign servers. Never issue DROP, --clean or --create.
EMPTY_TARGET_QUERY = """
SELECT EXISTS (
    SELECT 1 FROM pg_catalog.pg_namespace
      WHERE nspname NOT IN ('public', 'information_schema') AND nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_collation c JOIN pg_catalog.pg_namespace n ON n.oid=c.collnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_operator o JOIN pg_catalog.pg_namespace n ON n.oid=o.oprnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_opclass o JOIN pg_catalog.pg_namespace n ON n.oid=o.opcnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_opfamily o JOIN pg_catalog.pg_namespace n ON n.oid=o.opfnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_conversion c JOIN pg_catalog.pg_namespace n ON n.oid=c.connamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_ts_config c JOIN pg_catalog.pg_namespace n ON n.oid=c.cfgnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_ts_dict d JOIN pg_catalog.pg_namespace n ON n.oid=d.dictnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_ts_parser p JOIN pg_catalog.pg_namespace n ON n.oid=p.prsnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL
    SELECT 1 FROM pg_catalog.pg_ts_template t
      JOIN pg_catalog.pg_namespace n ON n.oid=t.tmplnamespace
      WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
    UNION ALL SELECT 1 FROM pg_catalog.pg_publication
    UNION ALL SELECT 1 FROM pg_catalog.pg_default_acl
    UNION ALL SELECT 1 FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql'
    UNION ALL SELECT 1 FROM pg_catalog.pg_largeobject_metadata
    UNION ALL SELECT 1 FROM pg_catalog.pg_event_trigger
    UNION ALL SELECT 1 FROM pg_catalog.pg_foreign_server
    UNION ALL SELECT 1 FROM pg_catalog.pg_foreign_data_wrapper
)
"""


def _assert_empty_target(connection: Connection) -> int:
    if connection.execute(text(EMPTY_TARGET_QUERY)).scalar_one():
        raise BackupError("restore target is not empty; use a fresh dedicated database")
    others = connection.execute(
        text(
            "SELECT count(*) FROM pg_catalog.pg_stat_activity "
            "WHERE datname=current_database() AND pid <> pg_backend_pid()"
        )
    ).scalar_one()
    if others:
        raise BackupError("restore target has other clients; stop them before restoring")
    return int(connection.execute(text("SHOW server_version_num")).scalar_one())


def restore_backup_bundle(
    directory: Path,
    target_url: str,
    *,
    confirm_empty_target: bool = False,
    runner: Runner = _run,
    engine_factory: EngineFactory = create_engine,
) -> dict[str, Any]:
    """Restore to a pre-created isolated EMPTY database and compare schema/counts.

    Successful restoration is committed before metadata checks; on mismatch the
    caller must quarantine the new target. The source and archive are never changed.
    """
    if not confirm_empty_target:
        raise BackupError("explicit confirm_empty_target is required")
    env = _libpq_env(target_url)
    checked = verify_backup_bundle(directory, runner=runner)
    manifest = checked["manifest"]
    expected = manifest["database"]
    if expected["schema_revisions"] != _schema_heads():
        raise BackupError(
            "backup schema does not match this release; use its matching recovery release"
        )
    if manifest["application"]["version"] != _application_version():
        raise BackupError("backup application version does not match this recovery release")
    engine = _engine(target_url, engine_factory)
    started = datetime.now(UTC)
    # --dbname accepts a libpq connection string; quote the name so it cannot
    # inject host/user/other parameters even if the database name contains "=".
    dbname = env["PGDATABASE"].replace("\\", "\\\\").replace("'", "\\'")
    try:
        # The lock serializes this tool's invocations, not arbitrary clients.
        # The operator must keep API/worker/migrations away from the fresh target.
        with engine.connect() as lock_connection, lock_connection.begin():
            acquired = lock_connection.execute(
                text("SELECT pg_try_advisory_xact_lock(1329813328, 1380275028)")
            ).scalar_one()
            if not acquired:
                raise BackupError("another restore is running against this target")
            target_version = _assert_empty_target(lock_connection)
            if target_version // 10000 != expected["postgres_version_num"] // 10000:
                raise BackupError(
                    "source and target PostgreSQL majors must match for this recovery tool"
                )
            _invoke(
                runner,
                [
                    "pg_restore",
                    "--no-password",
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname",
                    f"dbname='{dbname}'",
                    str((directory / DUMP_NAME).absolute()),
                ],
                env,
            )
            with engine.connect() as connection:
                connection = connection.execution_options(isolation_level="REPEATABLE READ")
                with connection.begin():
                    connection.execute(text("SET TRANSACTION READ ONLY"))
                    connection.execute(text("SET LOCAL row_security = off"))
                    connection.execute(text("SET LOCAL statement_timeout = '1h'"))
                    restored = _database_metadata(connection)
            if (
                restored["schema_revisions"] != expected["schema_revisions"]
                or restored["tables"] != expected["tables"]
            ):
                raise BackupError(
                    "restored schema or row counts differ; isolate the target and investigate"
                )
    except BackupError:
        raise
    except Exception:
        raise BackupError(
            "restore or checks failed; isolate the target; no recovery is claimed"
        ) from None
    finally:
        engine.dispose()
    finished = datetime.now(UTC)
    return {
        "status": "database_restore_checked",
        "scope": "postgresql-only",
        "backup_sha256": manifest["archive"]["sha256"],
        "backup_created_at": manifest["created_at"],
        "snapshot_started_at": manifest["snapshot_started_at"],
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "schema_revisions": restored["schema_revisions"],
        "tables_checked": len(restored["tables"]),
        "application_smoke_tested": False,
        "blob_payloads_checked": False,
        "client_pending_mutations_checked": False,
    }


def _url_from_environment(prefix: str) -> str:
    value = os.environ.get(prefix)
    filename = os.environ.get(f"{prefix}_FILE")
    if bool(value) == bool(filename):
        raise BackupError(f"set exactly one of {prefix} or {prefix}_FILE")
    if filename:
        try:
            value = Path(filename).read_text(encoding="utf-8").strip()
        except OSError:
            raise BackupError("database URL secret file cannot be read") from None
    if not value:
        raise BackupError("database URL is empty")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("backup", "verify", "restore"):
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path)
        if name == "restore":
            command.add_argument("--confirm-empty-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.operation == "backup":
            create_backup_bundle(_url_from_environment("OCWP_DATABASE_URL"), args.directory)
            result: dict[str, Any] = {
                "status": "backup_created_not_restored",
                "scope": "postgresql-only",
            }
        elif args.operation == "verify":
            result = verify_backup_bundle(args.directory)
            result.pop("manifest")  # Do not log database metadata unnecessarily.
        else:
            result = restore_backup_bundle(
                args.directory,
                _url_from_environment("OCWP_RESTORE_DATABASE_URL"),
                confirm_empty_target=args.confirm_empty_target,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except BackupError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print("operation failed; no successful backup or recovery is claimed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
