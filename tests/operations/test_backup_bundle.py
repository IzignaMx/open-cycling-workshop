from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.database import backup_postgres as backup


class Runner:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.fail = fail

    def __call__(self, command: list[str], *, env: dict[str, str]) -> None:
        self.calls.append((command, env))
        if command[0] == "pg_dump":
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMP synthetic archive")
        if self.fail:
            raise subprocess.CalledProcessError(1, command, stderr="password=very-secret")


def source_metadata() -> dict[str, object]:
    return {
        "postgres_version_num": 180004,
        "schema_revisions": ["0006"],
        "tables": [
            {"schema": "public", "name": "alembic_version", "rows": 1},
            {"schema": "public", "name": "customers", "rows": 2},
        ],
    }


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(backup, "_database_metadata", lambda connection: source_metadata())
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    path = tmp_path / "generation"
    backup.create_backup_bundle(
        "postgresql+psycopg://user:very-secret@localhost/source",
        path,
        runner=Runner(),
        engine_factory=lambda *args, **kwargs: engine,
    )
    return path


def test_bundle_captures_snapshot_manifest_and_integrity(bundle: Path) -> None:
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["format_version"] == 1
    assert manifest["database"]["schema_revisions"] == ["0006"]
    assert manifest["database"]["tables"][1]["rows"] == 2
    assert manifest["application"]["version"]
    assert manifest["scope"] == "postgresql-only"
    assert manifest["restore_tested"] is False
    assert "very-secret" not in (bundle / "manifest.json").read_text()
    result = backup.verify_backup_bundle(bundle, runner=Runner())
    assert result["status"] == "integrity_checked_not_restored"


def test_changed_archive_rejected_before_pg_restore(bundle: Path) -> None:
    (bundle / "database.dump").write_bytes(b"corrupt")
    runner = Runner()
    with pytest.raises(backup.BackupError, match="integrity"):
        backup.verify_backup_bundle(bundle, runner=runner)
    assert not runner.calls


def test_missing_manifest_is_not_a_backup(tmp_path: Path) -> None:
    with pytest.raises(backup.BackupError, match="manifest"):
        backup.verify_backup_bundle(tmp_path, runner=Runner())


def test_existing_generation_never_overwritten(bundle: Path) -> None:
    before = (bundle / "manifest.json").read_bytes()
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.create_backup_bundle("postgresql://user@localhost/source", bundle, runner=Runner())
    assert (bundle / "manifest.json").read_bytes() == before


def test_restore_requires_explicit_confirmation(bundle: Path) -> None:
    with pytest.raises(backup.BackupError, match="confirm"):
        backup.restore_backup_bundle(bundle, "postgresql://user@localhost/target", runner=Runner())


def test_restore_refuses_any_user_objects(bundle: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = MagicMock()
    monkeypatch.setattr(
        backup,
        "_assert_empty_target",
        MagicMock(side_effect=backup.BackupError("target is not empty")),
    )
    runner = Runner()
    with pytest.raises(backup.BackupError, match="not empty"):
        backup.restore_backup_bundle(
            bundle,
            "postgresql://user@localhost/target",
            confirm_empty_target=True,
            runner=runner,
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert not any("--dbname" in call[0] for call in runner.calls)


def test_restore_transactional_and_checks_metadata(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = MagicMock()
    monkeypatch.setattr(backup, "_assert_empty_target", lambda connection: 180004)
    runner = Runner()
    result = backup.restore_backup_bundle(
        bundle,
        "postgresql://user:very-secret@localhost/target",
        confirm_empty_target=True,
        runner=runner,
        engine_factory=lambda *args, **kwargs: engine,
    )
    command, env = next(call for call in runner.calls if "--dbname" in call[0])
    assert "--single-transaction" in command
    assert "--exit-on-error" in command
    assert "--no-owner" in command
    assert "--no-privileges" in command
    assert "--clean" not in command
    assert "very-secret" not in " ".join(command)
    assert env["PGDATABASE"] == "target"
    assert result["status"] == "database_restore_checked"
    assert result["application_smoke_tested"] is False


def test_post_restore_mismatch_is_not_success(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = MagicMock()
    monkeypatch.setattr(backup, "_assert_empty_target", lambda connection: 180004)
    changed = source_metadata()
    changed["schema_revisions"] = ["wrong"]
    monkeypatch.setattr(backup, "_database_metadata", lambda connection: changed)
    with pytest.raises(backup.BackupError, match="isolate"):
        backup.restore_backup_bundle(
            bundle,
            "postgresql://user@localhost/target",
            confirm_empty_target=True,
            runner=Runner(),
            engine_factory=lambda *args, **kwargs: engine,
        )


def test_subprocess_failure_does_not_leak_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, ["pg_dump"], stderr="very-secret customer data")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(backup.BackupError) as caught:
        backup.backup_postgres("postgresql://user:very-secret@localhost/source", tmp_path / "dump")
    assert "very-secret" not in str(caught.value)
    assert "customer data" not in str(caught.value)
    assert not (tmp_path / "dump").exists()


def test_failed_dump_does_not_publish_partial_output(tmp_path: Path) -> None:
    output = tmp_path / "dump"
    with pytest.raises(backup.BackupError):
        backup.backup_postgres(
            "postgresql://user@localhost/source", output, runner=Runner(fail=True)
        )
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_libpq_connection_options_are_preserved() -> None:
    env = backup._libpq_env("postgresql+psycopg://user@localhost/source?sslmode=require")
    assert env["PGSSLMODE"] == "require"
    assert "PGSERVICE" not in env
    assert "PGPASSWORD" not in env


def test_unknown_url_option_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        backup._libpq_env("postgresql://user@localhost/source?unexpected=value")


def test_exported_snapshot_connection_stays_open_through_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.execute.return_value.scalar_one.return_value = "00000003-00000001-1"
    monkeypatch.setattr(backup, "_database_metadata", lambda connection: source_metadata())
    runner = Runner()

    def checked_runner(command: list[str], *, env: dict[str, str]) -> None:
        if command[0] == "pg_dump":
            assert "--snapshot" in command
            assert command[command.index("--snapshot") + 1] == "00000003-00000001-1"
            assert not connection.begin.return_value.__exit__.called
            assert not engine.connect.return_value.__exit__.called
        runner(command, env=env)

    backup.create_backup_bundle(
        "postgresql://user@localhost/source",
        tmp_path / "new",
        runner=checked_runner,
        engine_factory=lambda *args, **kwargs: engine,
    )
    assert connection.begin.return_value.__exit__.called
    assert engine.dispose.called


def test_existing_archive_is_unchanged(tmp_path: Path) -> None:
    dump = tmp_path / "saved.dump"
    dump.write_bytes(b"previous-good-generation")
    runner = Runner()
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.backup_postgres("postgresql://user@localhost/source", dump, runner=runner)
    assert dump.read_bytes() == b"previous-good-generation"
    assert not runner.calls


@pytest.mark.parametrize(
    "change",
    [
        {"format_version": True},
        {"scope": "all-data"},
        {"restore_tested": True},
        {"database": {"postgres_version_num": 180004}},
        {"application": {"name": "wrong", "version": "1"}},
        {"created_at": "not-a-date"},
        {"archive": {"file": "../outside.dump", "bytes": 1, "sha256": "0" * 64}},
    ],
)
def test_invalid_manifest_rejected_before_commands(bundle: Path, change: dict[str, object]) -> None:
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest.update(change)
    path.write_text(json.dumps(manifest))
    runner = Runner()
    with pytest.raises(backup.BackupError, match="manifest"):
        backup.verify_backup_bundle(bundle, runner=runner)
    assert not runner.calls


def test_symlink_archive_rejected(bundle: Path, tmp_path: Path) -> None:
    archive = bundle / "database.dump"
    outside = tmp_path / "outside.dump"
    archive.rename(outside)
    archive.symlink_to(outside)
    with pytest.raises(backup.BackupError, match="unsafe"):
        backup.verify_backup_bundle(bundle, runner=Runner())


def test_target_database_name_cannot_inject_libpq_parameters(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy.engine import URL

    engine = MagicMock()
    monkeypatch.setattr(backup, "_assert_empty_target", lambda connection: 180004)
    name = "target' host=elsewhere user=someone\\end"
    url = URL.create("postgresql+psycopg", username="user", host="localhost", database=name)
    runner = Runner()
    backup.restore_backup_bundle(
        bundle,
        url.render_as_string(hide_password=False),
        confirm_empty_target=True,
        runner=runner,
        engine_factory=lambda *args, **kwargs: engine,
    )
    command = next(command for command, _env in runner.calls if "--dbname" in command)
    assert conninfo_to_dict(command[command.index("--dbname") + 1]) == {"dbname": name}


def test_advisory_lock_refusal_happens_before_restore(bundle: Path) -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = False
    runner = Runner()
    with pytest.raises(backup.BackupError, match="another restore"):
        backup.restore_backup_bundle(
            bundle,
            "postgresql://user@localhost/target",
            confirm_empty_target=True,
            runner=runner,
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert not any("--dbname" in command for command, _env in runner.calls)


def test_other_clients_and_empty_tables_are_refused() -> None:
    connection = MagicMock()
    connection.execute.return_value.scalar_one.return_value = True
    with pytest.raises(backup.BackupError, match="not empty"):
        backup._assert_empty_target(connection)
    first, second = MagicMock(), MagicMock()
    first.scalar_one.return_value = False
    second.scalar_one.return_value = 1
    connection.execute.side_effect = [first, second]
    with pytest.raises(backup.BackupError, match="other clients"):
        backup._assert_empty_target(connection)


def test_mismatched_postgres_major_prevents_restore(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "_assert_empty_target", lambda connection: 170006)
    engine = MagicMock()
    runner = Runner()
    with pytest.raises(backup.BackupError, match="majors must match"):
        backup.restore_backup_bundle(
            bundle,
            "postgresql://user@localhost/target",
            confirm_empty_target=True,
            runner=runner,
            engine_factory=lambda *args, **kwargs: engine,
        )
    assert not any("--dbname" in command for command, _env in runner.calls)


def test_mismatched_schema_prevents_database_access(bundle: Path) -> None:
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["database"]["schema_revisions"] = ["9999"]
    path.write_text(json.dumps(manifest))
    factory = MagicMock()
    with pytest.raises(backup.BackupError, match="schema does not match"):
        backup.restore_backup_bundle(
            bundle,
            "postgresql://user@localhost/target",
            confirm_empty_target=True,
            runner=Runner(),
            engine_factory=factory,
        )
    assert not factory.called


def test_cli_uses_secret_file_and_redacts_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = tmp_path / "database-url"
    secret.write_text("postgresql://user:very-secret@localhost/source\n")
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(secret))
    operation = MagicMock(side_effect=RuntimeError("very-secret from database"))
    monkeypatch.setattr(backup, "create_backup_bundle", operation)
    assert backup.main(["backup", str(tmp_path / "generation")]) == 1
    assert operation.call_args.args[0] == secret.read_text().strip()
    captured = capsys.readouterr()
    assert "very-secret" not in captured.out + captured.err
    assert "operation failed" in captured.err


def test_cli_refuses_ambiguous_url_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCWP_RESTORE_DATABASE_URL", "postgresql://user@localhost/source")
    monkeypatch.setenv("OCWP_RESTORE_DATABASE_URL_FILE", "/private/target")
    with pytest.raises(backup.BackupError, match="exactly one"):
        backup._url_from_environment("OCWP_RESTORE_DATABASE_URL")


@pytest.mark.parametrize(
    "variable", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGSSLMODE"]
)
def test_ambient_libpq_overrides_rejected_before_connection(
    variable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(variable, "unintended-private-value")
    factory = MagicMock()
    with pytest.raises(backup.BackupError, match="ambient PostgreSQL") as caught:
        backup._engine("postgresql://user:password@localhost/db", factory)
    assert not factory.called
    assert "unintended-private-value" not in str(caught.value)


def test_postgres_image_metadata_environment_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in ("PG_MAJOR", "PG_VERSION", "PG_SHA256", "PGDATA"):
        monkeypatch.setenv(variable, "official-image-metadata")
    env = backup._libpq_env("postgresql://user@localhost/db")
    assert env["PGDATABASE"] == "db"
