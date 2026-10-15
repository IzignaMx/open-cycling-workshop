"""Only synthetic fixtures invoke explicit narrow branding grant adoption."""

from __future__ import annotations

import json

import pytest
from cycling_workshop.cli import main
from cycling_workshop.identity.audit import IdentityAuditRecord
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import LEGACY_WILDCARD_CAPABILITIES
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_first_owner_cli import installation as installation


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
        "adopt-branding",
        *[item for key, value in args.items() for item in (f"--{key}", value)],
    ]


@pytest.mark.parametrize(
    ("additional_capabilities", "appended_capabilities"),
    [
        ((), ("branding.read", "branding.write")),
        (("quotes.read", "quotes.read"), ("branding.read", "branding.write")),
        (("quotes.write",), ("branding.read", "branding.write")),
        (("quotes.authorize", "quotes.authorize"), ("branding.read", "branding.write")),
        (("quotes.write", "quotes.read", "quotes.write"), ("branding.read", "branding.write")),
        (
            ("quotes.authorize", "quotes.write", "quotes.read", "quotes.write"),
            ("branding.read", "branding.write"),
        ),
        (("quotes.read", "branding.write", "quotes.read"), ("branding.read",)),
        (("branding.read", "quotes.authorize", "quotes.authorize"), ("branding.write",)),
    ],
    ids=[
        "no-quotes",
        "read-only-duplicates",
        "write-only",
        "authorize-only-duplicates",
        "partial-quotes-ordered-duplicates",
        "all-quotes-ordered-duplicates",
        "existing-branding-write",
        "existing-branding-read",
    ],
)
def test_adoption_adds_only_branding_literals_preserves_other_bytes_and_revokes(
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
            audit.action == "user.branding_adopted"
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
    assert main(adoption_args(**{"expected-version": "8"})) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
        assert owner.capabilities == expected_capabilities
        assert owner.version == 8 and owner.session_version == 10
        assert len(list(session.scalars(select(IdentityAuditRecord)))) == 1


@pytest.mark.parametrize(
    "problem", ["inactive", "not-owner", "incomplete", "unknown", "wrong-org", "wrong-id", "stale"]
)
def test_invalid_adoption_has_no_effect(installation, capsys, problem):
    engine, *_ = installation
    before = setup_owner(engine)
    changes = {}
    with Session(engine) as session:
        owner = session.get(UserRecord, "owner")
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


def test_adoption_invalidates_old_session_and_only_new_admission_gets_branding(
    installation, capsys
):
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
        assert client.get(path, headers={"Authorization": f"Bearer {old}"}).status_code == 200
        assert main(adoption_args()) == 0
        capsys.readouterr()
        assert client.get(path, headers={"Authorization": f"Bearer {old}"}).status_code == 401
        new = app.state.session_tokens.issue(
            Principal(
                "owner",
                "existing-org",
                None,
                frozenset([*before, "branding.read", "branding.write"]),
                session_version=10,
                dataset_incarnation=incarnation,
            )
        )
        response = client.get(path, headers={"Authorization": f"Bearer {new}"})
        assert response.status_code == 200
        assert set(response.json()["capabilities"]) == {
            *before,
            "branding.read",
            "branding.write",
        }
        assert not {"quotes.read", "quotes.write", "quotes.authorize"} & set(
            response.json()["capabilities"]
        )


def test_adoption_requires_explicit_database_configuration(monkeypatch, capsys):
    monkeypatch.delenv("OCWP_DATABASE_URL", raising=False)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    assert main(adoption_args()) == 1
    assert json.loads(capsys.readouterr().out) == {
        "changed": False,
        "error": "database_configuration_required",
    }
