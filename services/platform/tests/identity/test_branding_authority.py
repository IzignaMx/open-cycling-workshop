"""Catalog growth must not silently elevate existing account snapshots."""

from __future__ import annotations

import pytest
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import concrete_capabilities
from fastapi import HTTPException
from test_administration_api import ADMIN, ALL, Fixture
from test_administration_api import db as db
from test_context import context_client

BRANDING = {"branding.read", "branding.write"}


@pytest.mark.parametrize("literal", [set(), {"branding.read"}, {"branding.write"}, BRANDING])
def test_wildcard_expands_only_fixed_legacy_grants(literal):
    assert concrete_capabilities(frozenset({"*", *literal})) == ALL | literal
    principal = Principal("u", "o", "l", frozenset({"*", *literal}))
    for capability in BRANDING:
        if capability in literal:
            authorize(principal, capability=capability, organization_id="o", location_id="l")
            assert require_capability(capability)(principal) == principal
        else:
            with pytest.raises(PermissionError):
                authorize(principal, capability=capability, organization_id="o", location_id="l")
            with pytest.raises(HTTPException) as error:
                require_capability(capability)(principal)
            assert error.value.status_code == 403


@pytest.mark.parametrize("literal", [set(), {"branding.read"}, {"branding.write"}, BRANDING])
def test_context_never_adds_branding_from_wildcard_and_preserves_literal_intersection(literal):
    client, headers = context_client(["*", *literal], ["*"])
    assert set(client.get("/api/v1/auth/context", headers=headers).json()["capabilities"]) == ALL
    client, headers = context_client(["*", *literal], ["*", *literal])
    assert (
        set(client.get("/api/v1/auth/context", headers=headers).json()["capabilities"])
        == ALL | literal
    )


def test_v2_catalog_is_explicit_and_v1_catalog_and_aliases_are_frozen(db: Fixture):
    headers = {**db.headers(), "X-Request-ID": "private-input-sentinel"}
    old = db.client.get("/api/v1/admin/roles", headers=headers)
    assert set(old.json()) == {"roles", "capabilities"}
    assert set(old.json()["capabilities"]) == ALL
    current = db.client.get("/api/v2/admin/roles", headers=headers)
    assert current.status_code == 200
    assert current.headers["cache-control"] == "no-store"
    assert current.headers["x-request-id"] != headers["X-Request-ID"]
    body = current.json()
    assert set(body) == {"catalog_version", "roles", "capabilities", "legacy_wildcard_capabilities"}
    assert body["catalog_version"] == 2
    assert set(body["capabilities"]) == ALL | BRANDING
    assert set(body["legacy_wildcard_capabilities"]) == ALL
    roles = {r["name"]: set(r["capabilities"]) for r in body["roles"]}
    assert roles["Owner"] == ALL | BRANDING
    assert roles["Administrator"] == (ALL | BRANDING) - {"locations.create"}
    assert roles["Manager"] & BRANDING == {"branding.read"}
    assert roles["TechnicalAdmin"] == set()
    created = db.create(role="Viewer")
    assert created.status_code == 201 and not set(created.json()["capabilities"]) & BRANDING
    assert db.client.get("/api/v2/admin/roles").status_code == 401


def test_old_owner_unrelated_patch_preserves_exact_grant_bytes(db: Fixture):
    db.seed("old-owner", location=None, owner=True)
    stored = list(reversed(sorted(ALL)))
    with db.factory.begin() as session:
        session.get(UserRecord, "old-owner").capabilities = stored
    headers = db.headers("old-owner")
    response = db.client.patch(
        f"{ADMIN}/old-owner",
        headers=headers,
        json={"expected_version": 1, "display_name": "Changed"},
    )
    assert response.status_code == 200, response.text
    with db.factory() as session:
        user = session.get(UserRecord, "old-owner")
        assert user.capabilities == stored
        assert user.session_version == 1 and user.version == 2
    assert (
        db.client.post(
            f"{ADMIN}/old-owner/revoke-sessions", headers=headers, json={"expected_version": 2}
        ).status_code
        == 200
    )
    assert db.client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    "replacement",
    [{"role": "Owner"}, {"capabilities": sorted(ALL)}, {"location_id": None}, {"is_owner": True}],
)
def test_old_owner_explicit_replacement_requires_full_current_snapshot(db: Fixture, replacement):
    db.seed("old-owner", location=None, owner=True)
    response = db.client.patch(
        f"{ADMIN}/old-owner",
        headers=db.headers("old-owner"),
        json={"expected_version": 1, **replacement},
    )
    assert response.status_code == 422, response.text


def test_old_role_alias_cannot_create_or_promote_current_owner(db: Fixture):
    db.seed("old-owner", location=None, owner=True)
    response = db.create(
        headers=db.headers("old-owner"), role="Owner", is_owner=True, location_id=None
    )
    assert response.status_code == 422


@pytest.mark.parametrize("grants", [["unknown.private"], ["*", "unknown.private"]])
def test_unknown_target_grants_fail_closed_even_for_unrelated_edits(db: Fixture, grants):
    db.seed("actor", location=None, owner=True, capabilities=ALL | BRANDING)
    db.seed("target", capabilities=set(grants))
    headers = db.headers("actor")
    assert (
        db.client.patch(
            f"{ADMIN}/target", headers=headers, json={"expected_version": 1, "display_name": "No"}
        ).status_code
        == 403
    )
    assert (
        db.client.post(
            f"{ADMIN}/target/revoke-sessions", headers=headers, json={"expected_version": 1}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("literal", [set(), {"branding.read"}, {"branding.write"}, BRANDING])
def test_admin_can_delegate_only_explicit_branding_intersection(db: Fixture, literal):
    from cycling_workshop.identity.domain import Principal

    db.seed("wild", location=None, capabilities={"*", *literal})
    token = db.client.app.state.session_tokens.issue(
        Principal("wild", "org-a", None, frozenset({"*"}))
    )
    old_headers = {"Authorization": f"Bearer {token}"}
    fresh_headers = db.headers("wild")
    for capability in BRANDING:
        denied = db.create(
            headers=old_headers, username=f"old-{capability}", role=None, capabilities=[capability]
        )
        assert denied.status_code == 403
        response = db.create(
            headers=fresh_headers,
            username=f"fresh-{capability}",
            role=None,
            capabilities=[capability],
        )
        assert response.status_code == (201 if capability in literal else 403), response.text


def test_old_wildcard_owner_preserves_exact_grants_on_unrelated_edit(db: Fixture):
    db.seed("wild-owner", location=None, owner=True, capabilities={"*"})
    response = db.client.patch(
        f"{ADMIN}/wild-owner",
        headers=db.headers("wild-owner"),
        json={"expected_version": 1, "display_name": "Renamed"},
    )
    assert response.status_code == 200 and response.json()["capabilities"] == ["*"]
    with db.factory() as session:
        assert session.get(UserRecord, "wild-owner").session_version == 1
