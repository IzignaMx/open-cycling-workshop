"""Only synthetic fixtures invoke explicit narrow quotes grant adoption."""

from __future__ import annotations

import json

import pytest
from alembic import command
from cycling_workshop.cli import main
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import LEGACY_WILDCARD_CAPABILITIES
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database


@pytest.fixture
def installation(identity_migration_database, monkeypatch):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    with Session(engine) as session:
        session.add(OrganizationRecord(id="existing-org", name="Existing"))
        session.flush()
        session.add(
            LocationRecord(id="existing-location", organization_id="existing-org", name="First")
        )
        session.commit()
    monkeypatch.setenv("OCWP_DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("OCWP_ENVIRONMENT", "test")
    monkeypatch.setenv("OCWP_AUTH_SECRET", "test-quote-adoption-at-least-32-characters")
    yield (engine,)


pytestmark = [
    pytest.mark.usefixtures("identity_migration_database"),
    pytest.mark.parametrize("identity_migration_database", ["sqlite"], indirect=True),
]


def setup_owner(engine, additional_capabilities=()):
    with Session(engine) as session:
        owner = UserRecord(
            id="owner",
            organization_id="existing-org",
            location_id=None,
            username="owner",
            display_name="Synthetic owner",
            password_hash="untouched",
            capabilities=[
                *additional_capabilities,
                *reversed(sorted(LEGACY_WILDCARD_CAPABILITIES)),
            ],
            is_active=True,
            is_owner=True,
            version=7,
            session_version=9,
        )
        session.add(owner)
        session.commit()
        return list(owner.capabilities)


def adoption_args(**changes):
    args = {
        "organization-id": "existing-org",
        "owner-id": "owner",
        "expected-version": "7",
        **changes,
    }
    return [
        "access",
        "adopt-quotes",
        *[item for key, value in args.items() for item in (f"--{key}", value)],
    ]


@pytest.mark.parametrize(
    ("additional_capabilities", "appended_capabilities"),
    [
        ((), ("quotes.authorize", "quotes.read", "quotes.write")),
        (("branding.read", "branding.read"), ("quotes.authorize", "quotes.read", "quotes.write")),
        (("quotes.read", "quotes.read", "branding.write"), ("quotes.authorize", "quotes.write")),
        (("quotes.authorize", "quotes.write"), ("quotes.read",)),
        (("*", "*"), ("quotes.authorize", "quotes.read", "quotes.write")),
    ],
)
def test_adoption_adds_only_quotes_literals_preserves_other_bytes_and_revokes(
    installation, capsys, additional_capabilities, appended_capabilities
):
    engine, *_ = installation
    before = setup_owner(engine, additional_capabilities)
    expected_capabilities = [*before, *appended_capabilities]
    assert main(adoption_args()) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["changed"] and report["user_id"] == "owner" and report["version"] == 8
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert owner.capabilities == expected_capabilities
        assert owner.version == 8 and owner.session_version == 10
        assert owner.password_hash == "untouched" and owner.location_id is None and owner.is_owner
        audit = session.scalars(select(IdentityAuditRecord)).one()
        assert (
            audit.action == "user.quotes_adopted"
            and audit.actor_id is None
            and audit.target_id == "owner"
        )
        assert audit.request_id.startswith("cli-") and "untouched" not in json.dumps(audit.after)
        assert audit.before == {
            "location_id": None,
            "capabilities": sorted(before),
            "is_active": True,
            "is_owner": True,
            "version": 7,
            "session_version": 9,
        }
        assert audit.after == {
            "location_id": None,
            "capabilities": sorted(expected_capabilities),
            "is_active": True,
            "is_owner": True,
            "version": 8,
            "session_version": 10,
        }
    assert main(adoption_args()) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "stale_user_version"
    assert main(adoption_args(**{"expected-version": "8"})) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert owner.capabilities == expected_capabilities
        assert owner.version == 8 and owner.session_version == 10
        assert len(list(session.scalars(select(IdentityAuditRecord)))) == 1


@pytest.mark.parametrize(
    "problem",
    [
        "inactive",
        "not-owner",
        "incomplete",
        "unknown",
        "wrong-org",
        "wrong-id",
        "stale",
        "location",
    ],
)
def test_invalid_adoption_has_no_effect(installation, capsys, problem):
    engine, *_ = installation
    before = setup_owner(engine)
    changes = {}
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        if problem == "location":
            owner.location_id = "existing-location"
            owner.is_owner = False
        if problem == "inactive":
            owner.is_active = False
        if problem == "not-owner":
            owner.is_owner = False
        if problem == "incomplete":
            owner.capabilities = ["users.read"]
        if problem == "unknown":
            owner.capabilities = [*before, "future.private"]
        if problem == "wrong-org":
            changes["organization-id"] = "wrong"
        if problem == "wrong-id":
            changes["owner-id"] = "missing"
        if problem == "stale":
            changes["expected-version"] = "6"
        session.commit()
        before = list(owner.capabilities)
    assert main(adoption_args(**changes)) == 1
    assert json.loads(capsys.readouterr().out)["changed"] is False
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert owner.version == 7 and owner.session_version == 9 and owner.capabilities == before
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_adoption_invalidates_old_session_and_only_new_admission_gets_quotes(installation, capsys):
    from cycling_workshop.app import create_app
    from cycling_workshop.identity.domain import Principal
    from cycling_workshop.settings import Settings
    from cycling_workshop.tenancy.models import OrganizationRecord
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    engine, *_ = installation
    before = setup_owner(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    app = create_app(Settings(environment="test", cutover_enabled=True), session_factory=factory)
    with factory() as session:
        incarnation = session.get(OrganizationRecord, "existing-org").dataset_incarnation
    old = app.state.session_tokens.issue(
        Principal(
            "owner",
            "existing-org",
            None,
            frozenset(before),
            session_version=9,
            dataset_incarnation=incarnation,
        )
    )
    with TestClient(app) as client:
        path = "/api/v1/auth/context?selected_location_id=existing-location"
        initial = client.get(path, headers={"Authorization": f"Bearer {old}"})
        assert initial.status_code == 200
        old_epoch = initial.json()["authorization_epoch"]
        assert main(adoption_args()) == 0
        capsys.readouterr()
        assert client.get(path, headers={"Authorization": f"Bearer {old}"}).status_code == 401
        new = app.state.session_tokens.issue(
            Principal(
                "owner",
                "existing-org",
                None,
                frozenset([*before, "quotes.read", "quotes.write", "quotes.authorize"]),
                session_version=10,
                dataset_incarnation=incarnation,
            )
        )
        response = client.get(path, headers={"Authorization": f"Bearer {new}"})
        assert response.status_code == 200
        assert response.json()["authorization_epoch"] != old_epoch
        assert set(response.json()["capabilities"]) == {
            *before,
            "quotes.read",
            "quotes.write",
            "quotes.authorize",
        }
        assert not {"branding.read", "branding.write"} & set(response.json()["capabilities"])


def test_adoption_requires_explicit_database_configuration(monkeypatch, capsys):
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    assert main(adoption_args()) == 1
    assert json.loads(capsys.readouterr().out) == {
        "changed": False,
        "error": "database_configuration_required",
    }


@pytest.mark.parametrize("revision", [None, "0011", "0012", "0014"])
def test_adoption_refuses_missing_or_unsupported_schema(installation, capsys, revision):
    from sqlalchemy import text

    engine, *_ = installation
    before = setup_owner(engine)
    with engine.begin() as connection:
        if revision is None:
            connection.execute(text("DROP TABLE alembic_version"))
        else:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :revision"), {"revision": revision}
            )
    assert main(adoption_args()) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "quote_adoption_schema_required"
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert (owner.capabilities, owner.version, owner.session_version) == (before, 7, 9)
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_adoption_audit_failure_rolls_back_every_change(installation, monkeypatch, capsys):
    from cycling_workshop.identity import quote_cli
    from sqlalchemy.exc import SQLAlchemyError

    engine, *_ = installation
    before = setup_owner(engine)
    reached = []
    original = quote_cli.append_audit

    def fail_after_audit(*args, **kwargs):
        original(*args, **kwargs)
        reached.append(True)
        raise SQLAlchemyError("private database sentinel")

    monkeypatch.setattr(quote_cli, "append_audit", fail_after_audit)
    assert main(adoption_args()) == 1
    assert reached == [True]
    output = capsys.readouterr().out
    assert json.loads(output) == {"changed": False, "error": "quote_adoption_failed"}
    assert "private" not in output
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert (owner.capabilities, owner.version, owner.session_version) == (before, 7, 9)
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_adoption_does_not_change_floor_incarnation_or_other_accounts(installation, capsys):
    engine, *_ = installation
    setup_owner(engine)
    with Session(engine) as session:
        org = session.get(OrganizationRecord, "existing-org")
        before = (org.minimum_write_protocol, org.dataset_incarnation)
        session.add(
            UserRecord(
                id="other-owner",
                organization_id="existing-org",
                location_id=None,
                username="other",
                display_name="Other",
                password_hash="untouched",
                capabilities=["*"],
                is_active=True,
                is_owner=True,
            )
        )
        session.commit()
    assert main(adoption_args()) == 0
    capsys.readouterr()
    with Session(engine) as session:
        org = session.get(OrganizationRecord, "existing-org")
        assert (org.minimum_write_protocol, org.dataset_incarnation) == before
        other = session.get(UserRecord, "other-owner")
        assert other.capabilities == ["*"] and other.session_version == other.version == 1


@pytest.mark.parametrize("damage", ["table", "column", "count"])
def test_adoption_refuses_stamped_but_incomplete_schema(installation, capsys, damage):
    from sqlalchemy import text

    engine, *_ = installation
    before = setup_owner(engine)
    with engine.begin() as connection:
        if damage == "table":
            connection.execute(text("DROP TABLE quote_line_targets"))
        elif damage == "column":
            connection.execute(
                text(
                    "ALTER TABLE quote_operations RENAME COLUMN order_effect_version "
                    "TO missing_effect_version"
                )
            )
        else:
            connection.execute(
                text("ALTER TABLE sync_changes DROP COLUMN order_payload_raw_octets")
            )
    assert main(adoption_args()) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["error"] in {"quote_adoption_schema_required", "quote_adoption_failed"}
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert (owner.capabilities, owner.version, owner.session_version) == (before, 7, 9)
        assert list(session.scalars(select(IdentityAuditRecord))) == []
