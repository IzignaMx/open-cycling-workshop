from pathlib import Path

from scripts.database.backup_postgres import backup_postgres, verify_postgres_backup


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, command: list[str], *, env: dict[str, str]) -> None:
        self.calls.append((command, env))
        if command[0] == "pg_dump":
            Path(command[command.index("--file") + 1]).write_bytes(b"fake custom dump")


def test_backup_uses_libpq_environment_instead_of_password_in_command(tmp_path: Path) -> None:
    runner = FakeRunner()
    output = tmp_path / "backup.dump"

    backup_postgres(
        "postgresql+psycopg://ocwp:s3cret@db.internal:5432/ocwp",
        output,
        runner=runner,
    )

    command, env = runner.calls[0]
    assert command == ["pg_dump", "--format=custom", "--file", str(output)]
    assert env["PGHOST"] == "db.internal"
    assert env["PGPORT"] == "5432"
    assert env["PGUSER"] == "ocwp"
    assert env["PGDATABASE"] == "ocwp"
    assert env["PGPASSWORD"] == "s3cret"
    assert "s3cret" not in " ".join(command)


def test_verify_invokes_pg_restore_list(tmp_path: Path) -> None:
    runner = FakeRunner()
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"fake")

    verify_postgres_backup(dump, runner=runner)

    assert runner.calls[0][0] == ["pg_restore", "--list", str(dump)]
