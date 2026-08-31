from __future__ import annotations

import json
from pathlib import Path

from cycling_workshop.cli import main
from cycling_workshop.db.base import Base
from cycling_workshop.db.registry import register_models
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_bootstrap_admin_creates_first_tenant_location_and_admin_without_password_in_argv(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database_path = tmp_path / "bootstrap.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    register_models()
    Base.metadata.create_all(create_engine(database_url))
    password_file = tmp_path / "admin-password.txt"
    password_file.write_text("correct horse battery staple\n", encoding="utf-8")
    monkeypatch.setenv("OCWP_DATABASE_URL", database_url)
    monkeypatch.setenv("OCWP_AUTH_SECRET", "test-secret-that-is-long-enough-for-tests")
    monkeypatch.setenv("OCWP_ENVIRONMENT", "test")

    exit_code = main(
        [
            "bootstrap",
            "admin",
            "--organization-name",
            "Taller Uno",
            "--location-name",
            "Principal",
            "--username",
            "  ADMIN  ",
            "--display-name",
            "Administración",
            "--password-file",
            str(password_file),
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["created"] is True
    assert output["organization_id"]
    assert output["location_id"]
    assert output["user_id"]

    with Session(create_engine(database_url)) as session:
        user = session.get(UserRecord, output["user_id"])
        assert user is not None
        assert user.username == "admin"
        assert user.capabilities == ["*"]
        assert PasswordService().verify(user.password_hash, "correct horse battery staple") is True
