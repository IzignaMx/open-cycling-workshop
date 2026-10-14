"""HTTP authorization regressions; SQLite does not prove row-lock concurrency."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

PASSWORD = "local-test-initial-password"
ADMIN = "/api/v1/admin/users"
BUSINESS = {
    "customers.read",
    "customers.write",
    "bicycles.read",
    "bicycles.write",
    "orders.read",
    "orders.write",
    "inventory.read",
    "inventory.write",
    "sync.pull",
    "sync.push",
}
ADMINISTRATION = {
    "users.read",
    "users.write",
    "users.grants.write",
    "users.sessions.revoke",
    "users.credentials.reset",
    "locations.read",
    "locations.create",
}
ALL = BUSINESS | ADMINISTRATION


@dataclass
class Fixture:
    client: TestClient
    factory: sessionmaker[Session]
    password_hash: str

    def seed(
        self,
        user_id: str,
        *,
        organization: str = "org-a",
        location: str | None = "loc-a",
        capabilities: set[str] | None = None,
        owner: bool = False,
    ) -> None:
        with self.factory.begin() as session:
            record = UserRecord(
                id=user_id,
                organization_id=organization,
                location_id=location,
                username=user_id,
                display_name=user_id,
                password_hash=self.password_hash,
                capabilities=sorted(ALL if capabilities is None else capabilities),
                is_active=True,
            )
            # Added by this increment; using setattr allows the first test to
            # reach the absent HTTP endpoint against the original model.
            record.is_owner = owner
            session.add(record)

    def headers(self, user: str = "admin", organization: str = "org-a") -> dict[str, str]:
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": organization,
                "username": user,
                "password": PASSWORD,
            },
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def create(self, *, headers: dict[str, str] | None = None, **fields: Any):
        return self.client.post(
            ADMIN,
            headers=headers or self.headers(),
            json={
                "username": "mechanic",
                "display_name": "Mechanic",
                "location_id": "loc-a",
                "role": "Mechanic",
                "password": PASSWORD,
                **fields,
            },
        )


@pytest.fixture
def db() -> Iterator[Fixture]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add_all(
            [OrganizationRecord(id="org-a", name="A"), OrganizationRecord(id="org-b", name="B")]
        )
        session.flush()
        session.add_all(
            [
                LocationRecord(id="loc-a", organization_id="org-a", name="A1"),
                LocationRecord(id="loc-a2", organization_id="org-a", name="A2"),
                LocationRecord(id="loc-b", organization_id="org-b", name="B1"),
            ]
        )
    app = create_app(
        Settings(
            environment="test",
            database_url=str(engine.url),
            log_level="WARNING",
            auth_secret="administration-test-secret-at-least-32",
        ),
        session_factory=factory,
    )
    with TestClient(app) as client:
        fixture = Fixture(client, factory, PasswordService().hash(PASSWORD))
        fixture.seed("admin")
        yield fixture
    engine.dispose()


def test_create_user_normalizes_username_and_issues_exact_role_grants(db: Fixture) -> None:
    response = db.create(username="  MeChAnIc  ")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["username"] == "mechanic"
    assert body["version"] == 1 and body["is_owner"] is False
    assert set(body["capabilities"]) == {
        "customers.read",
        "bicycles.read",
        "bicycles.write",
        "orders.read",
        "orders.write",
        "inventory.read",
        "sync.pull",
        "sync.push",
        "locations.read",
    }
    assert "password" not in response.text
    with db.factory() as session:
        record = session.get(UserRecord, body["user_id"])
        assert record is not None and record.password_hash.startswith("$argon2id$")
        assert record.password_hash != PASSWORD
    me = db.client.get("/api/v1/auth/me", headers=db.headers("mechanic"))
    assert me.json()["capabilities"] == body["capabilities"]
    assert db.create(username=" MECHANIC ").status_code == 409


def test_role_catalog_covers_only_implemented_capabilities_and_technical_admin_has_none(
    db: Fixture,
):
    response = db.client.get("/api/v1/admin/roles", headers=db.headers())
    assert response.status_code == 200
    body = response.json()
    assert set(body["capabilities"]) == ALL
    roles = {role["name"]: set(role["capabilities"]) for role in body["roles"]}
    assert set(roles) == {
        "Owner",
        "Administrator",
        "Manager",
        "Mechanic",
        "Reception",
        "Sales",
        "Viewer",
        "TechnicalAdmin",
    }
    assert roles["TechnicalAdmin"] == set()
    assert roles["Owner"] == ALL
    assert roles["Administrator"] == ALL - {"locations.create"}
    assert roles["Manager"] == BUSINESS | {"locations.read"}
    assert roles["Viewer"] == {
        "customers.read",
        "bicycles.read",
        "orders.read",
        "inventory.read",
        "sync.pull",
        "locations.read",
    }
    assert roles["Reception"] == BUSINESS - {"inventory.write"} | {"locations.read"}
    assert roles["Sales"] == BUSINESS - {"inventory.write", "orders.write"} | {"locations.read"}
    created = db.create(role="TechnicalAdmin")
    assert created.status_code == 201
    assert created.json()["capabilities"] == []
    assert (
        db.client.get("/api/v1/customers/absent", headers=db.headers("mechanic")).status_code == 403
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"capabilities": ["*"]},
        {"capabilities": ["unknown.read"]},
        {"role": "unknown"},
        {"role": "Viewer", "capabilities": []},
        {"role": None},
        {"role": None, "capabilities": None},
        {"organization_id": "org-b"},
        {"user_id": "chosen-id"},
        {"session_version": 999},
        {"username": "   "},
        {"display_name": "   "},
    ],
)
def test_create_rejects_ambiguous_or_unrecognized_grants_and_overrides(db: Fixture, patch: dict):
    if "capabilities" in patch and "role" not in patch:
        patch = {"role": None, **patch}
    response = db.create(**patch)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("location", ["loc-b", "loc-a2", None])
def test_location_admin_cannot_create_outside_own_location(db: Fixture, location: str | None):
    assert db.create(location_id=location).status_code == 403


def test_creation_requires_both_account_and_grant_capabilities(db: Fixture):
    for index, grants in enumerate(({"users.write"}, {"users.grants.write"}, set())):
        user = f"limited-{index}"
        db.seed(user, capabilities=grants)
        assert db.create(headers=db.headers(user), role="TechnicalAdmin").status_code == 403


def test_explicit_grants_are_concrete_and_cannot_exceed_actor(db: Fixture):
    db.seed("limited", capabilities={"users.write", "users.grants.write", "customers.read"})
    denied = db.create(headers=db.headers("limited"), role=None, capabilities=["customers.write"])
    assert denied.status_code == 403
    allowed = db.create(headers=db.headers("limited"), role=None, capabilities=["customers.read"])
    assert allowed.status_code == 201
    assert allowed.json()["capabilities"] == ["customers.read"]


def test_scoped_paginated_user_and_location_lists_do_not_leak(db: Fixture):
    db.seed("other-local", location="loc-a2")
    db.seed("foreign", organization="org-b", location="loc-b")
    db.seed("wide", location=None)
    db.seed("z-user", capabilities=set())
    headers = db.headers()
    first = db.client.get(ADMIN, params={"limit": 1}, headers=headers)
    assert first.status_code == 200
    assert [u["user_id"] for u in first.json()["items"]] == ["admin"]
    second = db.client.get(
        ADMIN, params={"limit": 1, "after_id": first.json()["next_cursor"]}, headers=headers
    )
    assert [u["user_id"] for u in second.json()["items"]] == ["z-user"]
    assert second.json()["next_cursor"] is None
    assert db.client.get(ADMIN, params={"limit": 201}, headers=headers).status_code == 422
    locations = db.client.get("/api/v1/locations", headers=headers)
    assert locations.status_code == 200
    assert [v["location_id"] for v in locations.json()["items"]] == ["loc-a"]
    db.seed("no-grants", capabilities=set())
    for path in (ADMIN, "/api/v1/admin/roles", "/api/v1/locations"):
        assert db.client.get(path, headers=db.headers("no-grants")).status_code == 403


@pytest.mark.parametrize(
    "path", ["/api/v1/admin/users", "/api/v1/admin/roles", "/api/v1/locations"]
)
def test_lists_require_authentication(db: Fixture, path: str):
    assert db.client.get(path).status_code == 401


def test_patch_name_versions_without_revoking_and_rejects_stale_updates(db: Fixture):
    created = db.create().json()
    user_id = created["user_id"]
    target_headers = db.headers("mechanic")
    updated = db.client.patch(
        f"{ADMIN}/{user_id}",
        headers=db.headers(),
        json={
            "expected_version": 1,
            "display_name": "New name",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["display_name"] == "New name"
    assert updated.json()["version"] == 2
    assert db.client.get("/api/v1/auth/me", headers=target_headers).status_code == 200
    assert (
        db.client.patch(
            f"{ADMIN}/{user_id}",
            headers=db.headers(),
            json={
                "expected_version": 1,
                "display_name": "Lost update",
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "change",
    [
        {"is_active": False},
        {"role": "Viewer"},
        {"location_id": "loc-a2"},
        {"location_id": None},
    ],
)
def test_security_changes_invalidate_issued_tokens(db: Fixture, change: dict):
    db.seed("owner", location=None, owner=True)
    user_id = db.create().json()["user_id"]
    target_headers = db.headers("mechanic")
    response = db.client.patch(
        f"{ADMIN}/{user_id}",
        headers=db.headers("owner"),
        json={
            "expected_version": 1,
            **change,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    assert db.client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    if change.get("is_active") is False:
        assert (
            db.client.post(
                "/api/v1/auth/login",
                json={
                    "organization_id": "org-a",
                    "username": "mechanic",
                    "password": PASSWORD,
                },
            ).status_code
            == 401
        )
        active = db.client.get(ADMIN, headers=db.headers(), params={"active": False}).json()
        assert [user["user_id"] for user in active["items"]] == [user_id]


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "missing version"},
        {"expected_version": 0, "is_active": False},
        {"expected_version": 1},
        {"expected_version": 1, "display_name": None},
        {"expected_version": 1, "is_owner": None},
        {"expected_version": 1, "is_active": None},
        {"expected_version": 1, "role": "Viewer", "capabilities": []},
        {"expected_version": 1, "capabilities": ["*"]},
        {"expected_version": 1, "username": "renamed"},
        {"expected_version": 1, "organization_id": "org-b"},
        {"expected_version": True, "display_name": "Boolean version"},
    ],
)
def test_patch_rejects_missing_version_invalid_and_unrecognized_fields(db: Fixture, payload: dict):
    response = db.client.patch(f"{ADMIN}/admin", headers=db.headers(), json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("command", ["patch", "revoke-sessions", "reset-password"])
@pytest.mark.parametrize("target", ["foreign", "other-local", "wide", "privileged", "owner"])
def test_management_cannot_cross_existing_scope_or_privileged_target(
    db: Fixture, command: str, target: str
):
    db.seed("foreign", organization="org-b", location="loc-b", capabilities=set())
    db.seed("other-local", location="loc-a2", capabilities=set())
    db.seed("wide", location=None, capabilities=set())
    db.seed("privileged", capabilities=ALL)
    db.seed("owner", location=None, owner=True)
    db.seed("manager", capabilities=ADMINISTRATION)
    headers = db.headers("manager")
    payload = {"expected_version": 1}
    if command == "patch":
        response = db.client.patch(
            f"{ADMIN}/{target}", headers=headers, json={**payload, "is_active": False}
        )
    else:
        if command == "reset-password":
            payload["new_password"] = "another-local-test-password"
        response = db.client.post(f"{ADMIN}/{target}/{command}", headers=headers, json=payload)
    assert response.status_code == (404 if target == "foreign" else 403), response.text
    with db.factory() as session:
        record = session.get(UserRecord, target)
        assert record is not None and record.is_active and record.version == 1


@pytest.mark.parametrize(
    "capability,command",
    [
        ("users.write", "patch"),
        ("users.sessions.revoke", "revoke-sessions"),
        ("users.credentials.reset", "reset-password"),
    ],
)
def test_each_management_command_requires_its_capability(
    db: Fixture, capability: str, command: str
):
    db.seed("limited", capabilities=ALL - {capability})
    db.seed("target", capabilities=set())
    headers = db.headers("limited")
    payload = {"expected_version": 1}
    if command == "patch":
        response = db.client.patch(
            f"{ADMIN}/target", headers=headers, json={**payload, "display_name": "Updated"}
        )
    else:
        if command == "reset-password":
            payload["new_password"] = "replacement-test-password"
        response = db.client.post(f"{ADMIN}/target/{command}", headers=headers, json=payload)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "change",
    [
        {"role": "TechnicalAdmin"},
        {"location_id": None},
        {"is_owner": True},
    ],
)
def test_grants_scope_and_owner_changes_require_grant_administration(db: Fixture, change: dict):
    db.seed("limited", location=None, capabilities=ALL - {"users.grants.write"})
    db.seed("target", capabilities=set())
    response = db.client.patch(
        f"{ADMIN}/target", headers=db.headers("limited"), json={"expected_version": 1, **change}
    )
    assert response.status_code == 403


def test_local_admin_cannot_move_target_outside_scope_or_self_escalate(db: Fixture):
    db.seed("target", capabilities=set())
    for location in ("loc-a2", "loc-b", None):
        assert (
            db.client.patch(
                f"{ADMIN}/target",
                headers=db.headers(),
                json={
                    "expected_version": 1,
                    "location_id": location,
                },
            ).status_code
            == 403
        )
    db.seed("limited", capabilities={"users.write", "users.grants.write"})
    assert (
        db.client.patch(
            f"{ADMIN}/limited",
            headers=db.headers("limited"),
            json={
                "expected_version": 1,
                "role": "Administrator",
            },
        ).status_code
        == 403
    )


def test_non_owner_cannot_designate_owner_even_with_all_capabilities(db: Fixture):
    db.seed("wide", location=None)
    assert (
        db.create(
            headers=db.headers("wide"), location_id=None, role="Owner", is_owner=True
        ).status_code
        == 403
    )
    db.seed("target", location=None)
    assert (
        db.client.patch(
            f"{ADMIN}/target",
            headers=db.headers("wide"),
            json={
                "expected_version": 1,
                "is_owner": True,
            },
        ).status_code
        == 403
    )


def test_owner_transfer_self_demotion_and_last_owner_guard(db: Fixture):
    from cycling_workshop.identity.audit import IdentityAuditRecord

    db.seed(
        "owner", location=None, owner=True, capabilities=ALL | {"branding.read", "branding.write"}
    )
    headers = db.headers("owner")
    for change in ({"is_active": False}, {"is_owner": False}, {"role": "Viewer"}):
        response = db.client.patch(
            f"{ADMIN}/owner", headers=headers, json={"expected_version": 1, **change}
        )
        assert response.status_code in {409, 422}, response.text
    with db.factory() as session:
        assert list(session.scalars(select(IdentityAuditRecord))) == []
    second = db.create(
        headers=headers,
        username="successor",
        location_id=None,
        role=None,
        capabilities=sorted(ALL | {"branding.read", "branding.write"}),
        is_owner=True,
    )
    assert second.status_code == 201, second.text
    assert second.json()["is_owner"] is True
    response = db.client.patch(
        f"{ADMIN}/owner",
        headers=headers,
        json={
            "expected_version": 1,
            "is_owner": False,
            "role": "Viewer",
            "location_id": "loc-a",
        },
    )
    assert response.status_code == 200, response.text
    assert db.client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        db.client.patch(
            f"{ADMIN}/{second.json()['user_id']}",
            headers=db.headers("successor"),
            json={"expected_version": 1, "is_active": False},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"location_id": "loc-a"},
        {"role": "Viewer"},
    ],
)
def test_owner_designation_requires_org_scope_and_full_recovery_permissions(
    db: Fixture, fields: dict
):
    db.seed("owner", location=None, owner=True)
    response = db.create(
        headers=db.headers("owner"),
        **{
            "location_id": None,
            "role": "Owner",
            "is_owner": True,
            **fields,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("command", ["revoke-sessions", "reset-password"])
def test_revoke_and_reset_version_and_reject_old_sessions(db: Fixture, command: str):
    user_id = db.create().json()["user_id"]
    target_headers = db.headers("mechanic")
    payload = {"expected_version": 1}
    if command == "reset-password":
        payload["new_password"] = "replacement-local-test-password"
    result = db.client.post(f"{ADMIN}/{user_id}/{command}", headers=db.headers(), json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 2
    assert db.client.get("/api/v1/auth/me", headers=target_headers).status_code == 401
    assert (
        db.client.post(
            f"{ADMIN}/{user_id}/{command}", headers=db.headers(), json=payload
        ).status_code
        == 409
    )
    if command == "reset-password":
        for password, code in ((PASSWORD, 401), (payload["new_password"], 200)):
            assert (
                db.client.post(
                    "/api/v1/auth/login",
                    json={"organization_id": "org-a", "username": "mechanic", "password": password},
                ).status_code
                == code
            )


def test_self_password_change_requires_current_secret_and_revokes_every_session(db: Fixture):
    db.seed("no-grants", capabilities=set())
    first, second = db.headers("no-grants"), db.headers("no-grants")
    path = "/api/v1/auth/change-password"
    assert (
        db.client.post(
            path,
            headers=first,
            json={"current_password": "wrong", "new_password": "another-local-test-password"},
        ).status_code
        == 401
    )
    assert db.client.get("/api/v1/auth/me", headers=first).status_code == 200
    response = db.client.post(
        path,
        headers=first,
        json={"current_password": PASSWORD, "new_password": "another-local-test-password"},
    )
    assert response.status_code == 204, response.text
    for headers in (first, second):
        assert db.client.get("/api/v1/auth/me", headers=headers).status_code == 401
    for password, code in ((PASSWORD, 401), ("another-local-test-password", 200)):
        assert (
            db.client.post(
                "/api/v1/auth/login",
                json={"organization_id": "org-a", "username": "no-grants", "password": password},
            ).status_code
            == code
        )


def test_location_creation_requires_org_scope_and_explicit_capability(db: Fixture):
    path = "/api/v1/locations"
    assert db.client.post(path, headers=db.headers(), json={"name": "New"}).status_code == 403
    db.seed("wide", location=None, capabilities={"locations.read", "locations.create"})
    response = db.client.post(path, headers=db.headers("wide"), json={"name": "  New workshop  "})
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "New workshop"
    assert response.json()["organization_id"] == "org-a"
    assert len(response.json()["location_id"]) == 36
    assert len(db.client.get(path, headers=db.headers("wide")).json()["items"]) == 3
    assert (
        db.client.post(
            path, headers=db.headers("wide"), json={"name": "Elsewhere", "organization_id": "org-b"}
        ).status_code
        == 422
    )
    db.seed("no-grants", location=None, capabilities=set())
    assert (
        db.client.post(path, headers=db.headers("no-grants"), json={"name": "New"}).status_code
        == 403
    )


@pytest.mark.parametrize(
    "path,password_key,base",
    [
        (
            ADMIN,
            "password",
            {"username": "new", "display_name": "New", "role": "Viewer", "location_id": "loc-a"},
        ),
        (f"{ADMIN}/admin/reset-password", "new_password", {"expected_version": 1}),
        ("/api/v1/auth/change-password", "new_password", {"current_password": PASSWORD}),
        ("/api/v1/auth/login", "password", {"organization_id": "org-a", "username": "admin"}),
    ],
)
@pytest.mark.parametrize(
    "secret", ["x" * 1100, {"unexpected": "CREDENTIAL_SENTINEL"}, 998877665544]
)
def test_invalid_credentials_are_never_echoed_or_logged(
    db: Fixture, caplog: pytest.LogCaptureFixture, path: str, password_key: str, base: dict, secret
):
    headers = db.headers()
    response = db.client.post(path, headers=headers, json={**base, password_key: secret})
    assert response.status_code == 422, response.text
    text = response.text + caplog.text
    sentinel = (
        secret
        if isinstance(secret, str)
        else ("CREDENTIAL_SENTINEL" if isinstance(secret, dict) else str(secret))
    )
    assert sentinel not in text
    assert PASSWORD not in text
    assert '"input"' not in response.text


def test_too_short_new_password_is_redacted(db: Fixture, caplog: pytest.LogCaptureFixture):
    result = db.create(password="secretshort")
    assert result.status_code == 422
    assert "secretshort" not in result.text + caplog.text


def test_each_success_audits_only_safe_fields_and_correlates_server_generated_request_id(
    db: Fixture,
):
    from cycling_workshop.identity.audit import IdentityAuditRecord

    headers = {**db.headers(), "X-Request-ID": "untrusted-password-sentinel"}
    result = db.create(headers=headers)
    assert result.status_code == 201
    user_id = result.json()["user_id"]
    assert (
        db.client.patch(
            f"{ADMIN}/{user_id}",
            headers=db.headers(),
            json={
                "expected_version": 1,
                "display_name": "Name changed",
            },
        ).status_code
        == 200
    )
    assert (
        db.client.post("/api/v1/auth/logout-all", headers=db.headers("mechanic")).status_code == 204
    )
    with db.factory() as session:
        audits = list(session.scalars(select(IdentityAuditRecord).order_by(IdentityAuditRecord.id)))
        assert [audit.action for audit in audits] == [
            "user.created",
            "user.updated",
            "user.sessions_revoked",
        ]
        assert audits[0].request_id == result.headers["X-Request-ID"]
        assert audits[0].request_id != headers["X-Request-ID"]
        encoded = json.dumps(
            [
                {key: value for key, value in audit.__dict__.items() if key != "_sa_instance_state"}
                for audit in audits
            ],
            default=str,
        )
        for value in (PASSWORD, db.password_hash, "untrusted-password-sentinel", "Name changed"):
            assert value not in encoded
        assert audits[0].before is None
        assert audits[1].before["version"] == 1 and audits[1].after["version"] == 2
        assert audits[2].before["session_version"] == 1 and audits[2].after["session_version"] == 2


def test_audit_failure_rolls_back_user_mutation(db: Fixture):
    from cycling_workshop.identity.audit import IdentityAuditRecord

    def fail_audit(*_args):
        raise RuntimeError("synthetic audit persistence failure")

    event.listen(IdentityAuditRecord, "before_insert", fail_audit)
    try:
        response = db.create()
        assert response.status_code == 500
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"detail": "internal server error"}
    finally:
        event.remove(IdentityAuditRecord, "before_insert", fail_audit)
    with db.factory() as session:
        assert list(session.scalars(select(UserRecord.username))) == ["admin"]
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_normalized_username_length_is_bounded_after_unicode_case_expansion(db: Fixture):
    # U+0130 lowercases to two codepoints; PostgreSQL stores VARCHAR(160).
    response = db.create(username="İ" * 160)
    assert response.status_code == 422


def test_database_error_is_generic_and_does_not_log_credential_parameters(db: Fixture, caplog):
    from sqlalchemy.exc import SQLAlchemyError

    def fail_insert(*_args):
        raise SQLAlchemyError(f"synthetic driver failure: {PASSWORD} {db.password_hash}")

    event.listen(UserRecord, "before_insert", fail_insert)
    try:
        response = db.create()
    finally:
        event.remove(UserRecord, "before_insert", fail_insert)
    assert response.status_code == 503
    assert PASSWORD not in response.text + caplog.text
    assert db.password_hash not in response.text + caplog.text
    with db.factory() as session:
        assert list(session.scalars(select(UserRecord.username))) == ["admin"]


@pytest.mark.parametrize("command", ["name", "deactivate", "demote", "reset", "revoke"])
def test_org_wide_full_grant_non_owner_cannot_administer_protected_owner(db: Fixture, command: str):
    from cycling_workshop.identity.audit import IdentityAuditRecord

    db.seed("wide-non-owner", location=None)
    db.seed("protected-owner", location=None, owner=True)
    headers = db.headers("wide-non-owner")
    if command in {"name", "deactivate", "demote"}:
        changes = {
            "name": {"display_name": "Forbidden"},
            "deactivate": {"is_active": False},
            "demote": {"is_owner": False},
        }
        response = db.client.patch(
            f"{ADMIN}/protected-owner",
            headers=headers,
            json={"expected_version": 1, **changes[command]},
        )
    else:
        endpoint = "reset-password" if command == "reset" else "revoke-sessions"
        payload = {"expected_version": 1}
        if command == "reset":
            payload["new_password"] = "forbidden-replacement-password"
        response = db.client.post(
            f"{ADMIN}/protected-owner/{endpoint}", headers=headers, json=payload
        )
    assert response.status_code == 403, response.text
    with db.factory() as session:
        target = session.get(UserRecord, "protected-owner")
        assert target is not None
        assert target.is_active and target.is_owner and target.display_name == "protected-owner"
        assert target.password_hash == db.password_hash
        assert target.version == target.session_version == 1
        assert list(session.scalars(select(IdentityAuditRecord))) == []


def test_inactive_owner_does_not_satisfy_last_active_owner_guard(db: Fixture):
    db.seed("owner", location=None, owner=True)
    db.seed("inactive-owner", location=None, owner=True)
    with db.factory.begin() as session:
        session.get(UserRecord, "inactive-owner").is_active = False
    response = db.client.patch(
        f"{ADMIN}/owner",
        headers=db.headers("owner"),
        json={"expected_version": 1, "is_active": False},
    )
    assert response.status_code == 409


@pytest.mark.parametrize("field", ["username", "display_name", "location_id"])
def test_create_rejects_nul_in_postgres_text_fields(db: Fixture, field: str):
    response = db.create(**{field: "nul\x00value"})
    assert response.status_code == 422


def test_location_and_patch_names_reject_nul(db: Fixture):
    db.seed("wide", location=None)
    assert (
        db.client.post(
            "/api/v1/locations", headers=db.headers("wide"), json={"name": "nul\x00value"}
        ).status_code
        == 422
    )
    assert (
        db.client.patch(
            f"{ADMIN}/admin",
            headers=db.headers(),
            json={"expected_version": 1, "display_name": "nul\x00value"},
        ).status_code
        == 422
    )


def test_login_username_rejects_blank_and_nul_values(db: Fixture):
    for username in ("  ", "nul\x00value"):
        response = db.client.post(
            "/api/v1/auth/login",
            json={"organization_id": "org-a", "username": username, "password": PASSWORD},
        )
        assert response.status_code == 422


def test_list_cursor_and_target_id_reject_nul_before_database_queries(db: Fixture):
    for path in (ADMIN, "/api/v1/locations"):
        assert (
            db.client.get(
                path, headers=db.headers(), params={"after_id": "nul\x00value"}
            ).status_code
            == 422
        )
    response = db.client.patch(
        f"{ADMIN}/nul%00value",
        headers=db.headers(),
        json={"expected_version": 1, "display_name": "New name"},
    )
    assert response.status_code == 422


def test_validation_does_not_echo_unknown_property_names_containing_secret_input(db: Fixture):
    sentinel = "mistaken-password-as-property-name"
    response = db.create(**{sentinel: "unexpected"})
    assert response.status_code == 422
    assert sentinel not in response.text
