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


def test_bootstrap_refuses_existing_organization_even_without_users(tmp_path, monkeypatch):
    import pytest
    from cycling_workshop.cli import bootstrap_admin
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import OrganizationRecord

    url = f"sqlite+pysqlite:///{tmp_path / 'not-fresh.sqlite3'}"
    engine = create_engine(url)
    register_models()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(OrganizationRecord(id="preserved", name="Preserved"))
        session.commit()
    password_file = tmp_path / "password.txt"
    password_file.write_text("synthetic-bootstrap-password")
    with pytest.raises(RuntimeError, match="fresh installation"):
        bootstrap_admin(
            Settings(environment="test", database_url=url),
            organization_name="New",
            location_name="New",
            username="new",
            display_name="New",
            password_file=password_file,
        )
    with Session(engine) as session:
        from sqlalchemy import select

        assert list(session.scalars(select(OrganizationRecord.id))) == ["preserved"]
        assert list(session.scalars(select(UserRecord.id))) == []
    engine.dispose()


def test_concurrent_sqlite_bootstraps_create_only_one_fresh_installation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from cycling_workshop.cli import bootstrap_admin
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import OrganizationRecord
    from sqlalchemy import select

    url = f"sqlite+pysqlite:///{tmp_path / 'concurrent-bootstrap.sqlite3'}"
    engine = create_engine(url)
    register_models()
    Base.metadata.create_all(engine)
    password_file = tmp_path / "password.txt"
    password_file.write_text("synthetic-bootstrap-password")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                bootstrap_admin,
                Settings(environment="test", database_url=url),
                organization_name="Synthetic",
                location_name="Synthetic",
                username=f"admin-{index}",
                display_name="Synthetic",
                password_file=password_file,
            )
            for index in range(2)
        ]
        results, errors = [], []
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except RuntimeError as failure:
                errors.append(str(failure))
    assert len(results) == 1
    assert errors == ["bootstrap admin requires a fresh installation"]
    with Session(engine) as session:
        organizations = list(session.scalars(select(OrganizationRecord)))
        assert len(organizations) == 1 and organizations[0].minimum_write_protocol == 0
        assert len(list(session.scalars(select(UserRecord)))) == 1
    engine.dispose()
