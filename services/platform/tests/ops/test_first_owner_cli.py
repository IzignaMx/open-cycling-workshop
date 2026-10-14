from __future__ import annotations

import json
from pathlib import Path

import pytest
from cycling_workshop.cli import main
from cycling_workshop.db.base import Base
from cycling_workshop.db.registry import register_models
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def installation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'first_owner.sqlite3'}"
    engine = create_engine(url)
    register_models()
    Base.metadata.create_all(engine)
    password = "separate-owner-synthetic-password"
    password_file = tmp_path / "owner-password.txt"
    password_file.write_text(password + "\n")
    password_file.chmod(0o600)
    with Session(engine) as session:
        session.add(OrganizationRecord(id="existing-org", name="Existing"))
        session.flush()
        session.add(
            LocationRecord(id="existing-location", organization_id="existing-org", name="First")
        )
        session.flush()
        session.add(
            UserRecord(
                id="bootstrap-admin",
                organization_id="existing-org",
                location_id="existing-location",
                username="admin",
                display_name="Admin",
                password_hash=PasswordService().hash("original-synthetic-password"),
                capabilities=["*"],
                is_active=True,
            )
        )
        session.commit()
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.setenv("OCWP_AUTH_SECRET", "test-first-owner-secret-at-least-32-characters")
    monkeypatch.setenv("OCWP_ENVIRONMENT", "test")
    args = [
        "access",
        "create-first-owner",
        "--organization-id",
        "existing-org",
        "--username",
        " OWNER ",
        "--display-name",
        "Owner",
        "--password-file",
        str(password_file),
    ]
    yield engine, args, password_file, password
    engine.dispose()


def test_first_owner_is_separate_account_and_never_promotes_legacy_admin(installation, capsys):
    engine, args, _, password = installation
    with Session(engine) as session:
        old = session.get(UserRecord, "bootstrap-admin")
        before = (
            old.location_id,
            old.password_hash,
            old.capabilities,
            old.is_active,
            old.is_owner,
            old.version,
            old.session_version,
        )
    assert main(args) == 0
    output_text = capsys.readouterr().out
    output = json.loads(output_text)
    assert output["created"] is True and output["organization_id"] == "existing-org"
    assert output["location_id"] is None and output["user_id"] != "bootstrap-admin"
    assert password not in output_text
    with Session(engine) as session:
        old = session.get(UserRecord, "bootstrap-admin")
        after = (
            old.location_id,
            old.password_hash,
            old.capabilities,
            old.is_active,
            old.is_owner,
            old.version,
            old.session_version,
        )
        assert after == before
        owner = session.get(UserRecord, output["user_id"])
        assert owner.is_owner and owner.location_id is None and owner.username == "owner"
        assert "*" not in owner.capabilities and "users.grants.write" in owner.capabilities
        assert PasswordService().verify(owner.password_hash, password)
        audit = session.scalars(select(IdentityAuditRecord)).one()
        assert audit.action == "user.first_owner_created" and audit.actor_id is None
        assert audit.target_id == owner.id and audit.request_id.startswith("cli-")
        assert password not in json.dumps(audit.after) and owner.password_hash not in json.dumps(
            audit.after
        )


@pytest.mark.parametrize("active", [True, False])
def test_first_owner_refuses_any_existing_owner_even_when_inactive(installation, capsys, active):
    engine, args, _, _ = installation
    assert main(args) == 0
    with Session(engine) as session:
        owner = session.scalars(select(UserRecord).where(UserRecord.is_owner.is_(True))).one()
        owner.is_active = active
        session.commit()
    args[args.index("--username") + 1] = "second-owner"
    assert main(args) == 1
    assert "owner_already_established" in capsys.readouterr().out
    with Session(engine) as session:
        assert len(list(session.scalars(select(UserRecord)))) == 2
        assert len(list(session.scalars(select(IdentityAuditRecord)))) == 1


@pytest.mark.parametrize(
    "problem", ["unknown-org", "duplicate-name", "short-password", "long-password", "missing-file"]
)
def test_first_owner_fails_without_mutation_or_secret_output(installation, capsys, caplog, problem):
    engine, args, password_file, _ = installation
    secret = "sensitive" if problem == "short-password" else "sensitive" * 200
    if problem == "unknown-org":
        args[args.index("--organization-id") + 1] = "unknown"
    elif problem == "duplicate-name":
        args[args.index("--username") + 1] = "ADMIN"
    elif problem == "missing-file":
        args[args.index("--password-file") + 1] = str(password_file.parent / "missing")
    else:
        password_file.write_text(secret)
    assert main(args) == 1
    output = capsys.readouterr()
    assert secret not in output.out + output.err + caplog.text
    with Session(engine) as session:
        assert len(list(session.scalars(select(UserRecord)))) == 1
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_first_owner_has_no_password_argument_or_promotion_shortcut(installation, capsys):
    _, args, _, _ = installation
    for extra in (["--password", "must-not-be-accepted"], ["--promote", "bootstrap-admin"]):
        with pytest.raises(SystemExit) as result:
            main([*args, *extra])
        assert result.value.code == 2
        output = capsys.readouterr()
        assert "must-not-be-accepted" not in output.out + output.err


def test_first_owner_rejects_oversized_file_without_truncating_secret(installation, capsys):
    _, args, password_file, _ = installation
    password_file.write_text("valid-synthetic-password\n" + "\n" * 3000 + "unexpected-tail")
    assert main(args) == 1
    assert "unexpected-tail" not in capsys.readouterr().out


def test_compiled_first_owner_writer_is_admitted_at_floor_one_without_http_composition(
    installation,
    monkeypatch,
    capsys,
):
    engine, args, _, _ = installation
    with Session(engine) as session:
        organization = session.get(OrganizationRecord, "existing-org")
        organization.minimum_write_protocol = 1
        session.commit()
    monkeypatch.setenv("OCWP_CUTOVER_ENABLED", "false")
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["created"] is True
