"""Explicit quote catalog growth, not route activation or live grant adoption."""

from __future__ import annotations

import pytest
from cycling_workshop.identity import admin_schemas, roles
from cycling_workshop.identity.admin_schemas import GrantSelection
from cycling_workshop.identity.administration import AdministrationService
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.identity.models import UserRecord
from fastapi import HTTPException
from test_administration_api import ADMIN, ALL, BUSINESS, Fixture
from test_administration_api import db as db
from test_context import context_client

QUOTE = {"quotes.read", "quotes.write", "quotes.authorize"}
BRANDING = {"branding.read", "branding.write"}
OLD_CURRENT = ALL | BRANDING
CURRENT = OLD_CURRENT | QUOTE
LEGACY = {
    "Owner": ALL,
    "Administrator": ALL - {"locations.create"},
    "Manager": BUSINESS | {"locations.read"},
    "Mechanic": BUSINESS - {"customers.write", "inventory.write"} | {"locations.read"},
    "Reception": BUSINESS - {"inventory.write"} | {"locations.read"},
    "Sales": BUSINESS - {"orders.write", "inventory.write"} | {"locations.read"},
    "Viewer": {
        "customers.read",
        "bicycles.read",
        "orders.read",
        "inventory.read",
        "sync.pull",
        "locations.read",
    },
    "TechnicalAdmin": set(),
}
OLD_STARTERS = {
    name: grants
    | (
        BRANDING
        if name in {"Owner", "Administrator"}
        else {"branding.read"}
        if name != "TechnicalAdmin"
        else set()
    )
    for name, grants in LEGACY.items()
}


def test_exact_legacy_snapshots_and_only_current_owner_gains_quote_literals():
    assert roles.BUSINESS_CAPABILITIES == BUSINESS and len(BUSINESS) == 10
    assert roles.LEGACY_WILDCARD_CAPABILITIES == ALL and len(ALL) == 17
    assert roles.LEGACY_ROLE_BUNDLES == LEGACY
    assert getattr(roles, "QUOTE_CAPABILITIES", None) == QUOTE
    assert isinstance(roles.QUOTE_CAPABILITIES, frozenset)
    assert roles.CAPABILITIES == CURRENT and len(CURRENT) == 22
    assert roles.ROLE_BUNDLES == {**OLD_STARTERS, "Owner": CURRENT}
    for name, grants in LEGACY.items():
        assert GrantSelection(role=name).resolved_grants() == grants
        assert not roles.concrete_capabilities([name])


def test_v1_catalog_remains_exact_while_v2_exposes_current_explicit_snapshot(db: Fixture):
    headers = db.headers()
    v1 = db.client.get("/api/v1/admin/roles", headers=headers).json()
    assert v1 == {
        "roles": [
            {"name": name, "capabilities": sorted(grants)} for name, grants in LEGACY.items()
        ],
        "capabilities": sorted(ALL),
    }
    response = db.client.get("/api/v2/admin/roles", headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "catalog_version": 2,
        "roles": [
            {"name": name, "capabilities": sorted(grants)}
            for name, grants in {**OLD_STARTERS, "Owner": CURRENT}.items()
        ],
        "capabilities": sorted(CURRENT),
        "legacy_wildcard_capabilities": sorted(ALL),
    }


@pytest.mark.parametrize("literal", sorted(QUOTE))
@pytest.mark.parametrize("base", [set(), {"*"}, {"Owner"}, {"Administrator"}])
def test_quote_literals_are_independent_and_role_names_never_grant_authority(literal, base):
    principal = Principal("u", "o", "l", frozenset(base | {literal}))
    expected = (ALL if "*" in base else set()) | {literal}
    assert roles.concrete_capabilities(principal.capabilities) == expected
    for capability in CURRENT:
        if capability in expected:
            authorize(principal, capability=capability, organization_id="o", location_id="l")
            assert require_capability(capability)(principal) == principal
        else:
            with pytest.raises(PermissionError):
                authorize(principal, capability=capability, organization_id="o", location_id="l")
            with pytest.raises(HTTPException) as error:
                require_capability(capability)(principal)
            assert error.value.status_code == 403


@pytest.mark.parametrize("literal", sorted(QUOTE))
@pytest.mark.parametrize(
    "account_has,token_has", [(False, False), (True, False), (False, True), (True, True)]
)
def test_context_recognizes_only_explicit_quote_token_account_intersection(
    literal, account_has, token_has
):
    account = ["*", *([literal] if account_has else [])]
    token = ["*", *([literal] if token_has else [])]
    client, headers = context_client(account, token)
    response = client.get("/api/v1/auth/context", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body["capabilities"]) == ALL | ({literal} if account_has and token_has else set())
    assert body["protocol"] == 1 and body["policy_revision"] == "ocwp-access-baseline-2"
    assert set(body) == {
        "protocol",
        "principal",
        "account_location_id",
        "selected_location_id",
        "capabilities",
        "authorization_epoch",
        "policy_revision",
        "verified_at",
        "offline_until",
        "snapshot_protocol",
        "dataset_incarnation",
    }


@pytest.mark.parametrize("snapshot", [["*"], sorted(ALL), sorted(OLD_CURRENT)])
def test_supported_old_snapshots_keep_identical_context_epoch_on_catalog_growth(
    monkeypatch, snapshot
):
    client, headers = context_client(snapshot, snapshot)
    current_catalog = roles.CAPABILITIES
    monkeypatch.setattr(roles, "CAPABILITIES", frozenset(OLD_CURRENT))
    before = client.get("/api/v1/auth/context", headers=headers).json()
    monkeypatch.setattr(roles, "CAPABILITIES", current_catalog)
    after = client.get("/api/v1/auth/context", headers=headers).json()
    assert after == before
    assert not set(after["capabilities"]) & QUOTE


def test_unsupported_both_side_preseeded_quote_literal_becomes_recognized(monkeypatch):
    # The old admin API cannot create this state; a manual DB/token seed can.
    client, headers = context_client(["quotes.read"], ["quotes.read"])
    current_catalog = roles.CAPABILITIES
    monkeypatch.setattr(roles, "CAPABILITIES", frozenset(OLD_CURRENT))
    before = client.get("/api/v1/auth/context", headers=headers).json()
    monkeypatch.setattr(roles, "CAPABILITIES", current_catalog)
    after = client.get("/api/v1/auth/context", headers=headers).json()
    assert before["capabilities"] == [] and after["capabilities"] == ["quotes.read"]
    assert before["authorization_epoch"] != after["authorization_epoch"]


@pytest.mark.parametrize(
    "snapshot",
    [
        ["*", "*"],
        [*reversed(sorted(ALL)), "orders.read"],
        [*reversed(sorted(OLD_CURRENT)), "branding.read"],
    ],
)
def test_existing_owner_name_only_patch_preserves_grant_order_duplicates_scope_and_session(
    db: Fixture, snapshot
):
    db.seed("old-owner", location=None, owner=True)
    with db.factory.begin() as session:
        session.get(UserRecord, "old-owner").capabilities = snapshot
    headers = db.headers("old-owner")
    path = "/api/v1/auth/context?selected_location_id=loc-a"
    before = db.client.get(path, headers=headers).json()
    response = db.client.patch(
        f"{ADMIN}/old-owner",
        headers=headers,
        json={"expected_version": 1, "display_name": "Renamed"},
    )
    assert response.status_code == 200, response.text
    with db.factory() as session:
        owner = session.get(UserRecord, "old-owner")
        assert owner.capabilities == snapshot and owner.location_id is None
        assert owner.is_owner and owner.is_active and owner.session_version == 1
        assert owner.version == 2 and owner.display_name == "Renamed"
    after = db.client.get(path, headers=headers).json()
    assert after["authorization_epoch"] == before["authorization_epoch"]
    assert after["capabilities"] == before["capabilities"]


@pytest.mark.parametrize("action", ["create", "promote", "replace"])
@pytest.mark.parametrize("grants", [OLD_CURRENT, CURRENT])
@pytest.mark.parametrize("actor_grants", [OLD_CURRENT, CURRENT])
def test_explicit_owner_changes_require_all_22_and_actor_delegation(
    db: Fixture, action, grants, actor_grants
):
    db.seed("actor", location=None, owner=True, capabilities=actor_grants)
    db.seed("target", location=None, owner=action == "replace", capabilities=OLD_CURRENT)
    headers = db.headers("actor")
    if action == "create":
        response = db.create(
            headers=headers, role=None, capabilities=sorted(grants), location_id=None, is_owner=True
        )
    else:
        response = db.client.patch(
            f"{ADMIN}/target",
            headers=headers,
            json={
                "expected_version": 1,
                "capabilities": sorted(grants),
                "is_owner": True,
            },
        )
    expected = (
        403
        if not grants <= actor_grants
        else 422
        if grants != CURRENT
        else 201
        if action == "create"
        else 200
    )
    assert response.status_code == expected, response.text
    if expected in {200, 201}:
        assert set(response.json()["capabilities"]) == CURRENT and response.json()["is_owner"]
    else:
        with db.factory() as session:
            target = session.get(UserRecord, "target")
            assert target.version == target.session_version == 1
            assert target.capabilities == sorted(OLD_CURRENT)


@pytest.mark.parametrize("literal", sorted(QUOTE))
def test_admin_cannot_delegate_quote_literal_missing_from_account_or_token(db: Fixture, literal):
    for index, (account_has, token_has) in enumerate([(False, True), (True, False), (True, True)]):
        user_id = f"actor-{index}"
        account = ALL | ({literal} if account_has else set())
        token = ALL | ({literal} if token_has else set())
        db.seed(user_id, capabilities=account)
        signed = db.client.app.state.session_tokens.issue(
            Principal(user_id, "org-a", "loc-a", frozenset(token))
        )
        response = db.create(
            headers={"Authorization": f"Bearer {signed}"},
            role=None,
            capabilities=[literal],
            username=f"target-{index}",
        )
        assert response.status_code == (201 if account_has and token_has else 403), response.text
        if response.status_code == 201:
            assert response.json()["capabilities"] == [literal]


def test_post_authentication_lock_does_not_restore_quote_removed_by_initial_intersection(
    db: Fixture,
):
    db.seed("actor", capabilities=CURRENT)
    # Already-narrowed incoming principal remains narrower even if current DB grants grow.
    incoming = Principal("actor", "org-a", "loc-a", frozenset(OLD_CURRENT))
    with db.factory.begin() as session:
        _, effective = AdministrationService.for_fixtures(session).lock_actor(incoming)
        assert effective.capabilities == OLD_CURRENT


def test_quote_catalog_does_not_register_any_quote_routes(db: Fixture):
    assert not any("/quotes" in path for path in db.client.app.openapi()["paths"])


@pytest.mark.parametrize("literal", sorted(QUOTE))
@pytest.mark.parametrize("action", ["create", "patch"])
def test_supported_pre_quote_api_rejects_unknown_quote_literals(
    db: Fixture, monkeypatch, literal, action
):
    monkeypatch.setattr(admin_schemas, "CAPABILITIES", frozenset(OLD_CURRENT))
    db.seed("target", capabilities={"orders.read"})
    if action == "create":
        response = db.create(role=None, capabilities=[literal])
    else:
        response = db.client.patch(
            f"{ADMIN}/target",
            headers=db.headers(),
            json={
                "expected_version": 1,
                "capabilities": [literal],
            },
        )
    assert response.status_code == 422
    with db.factory() as session:
        assert session.get(UserRecord, "target").capabilities == ["orders.read"]
        assert session.get(UserRecord, "target").version == 1


@pytest.mark.parametrize("literal", sorted(QUOTE))
def test_explicit_quote_replacement_revokes_session_and_changes_epoch_only_for_grant(
    db: Fixture, literal
):
    db.seed("actor", capabilities=CURRENT)
    db.seed("target", capabilities={"orders.read"})
    old_headers = db.headers("target")
    before = db.client.get("/api/v1/auth/context", headers=old_headers).json()
    response = db.client.patch(
        f"{ADMIN}/target",
        headers=db.headers("actor"),
        json={
            "expected_version": 1,
            "capabilities": ["orders.read", literal],
        },
    )
    assert response.status_code == 200, response.text
    assert db.client.get("/api/v1/auth/context", headers=old_headers).status_code == 401
    after = db.client.get("/api/v1/auth/context", headers=db.headers("target")).json()
    assert set(after["capabilities"]) == {"orders.read", literal}
    assert before["authorization_epoch"] != after["authorization_epoch"]
    assert before["policy_revision"] == after["policy_revision"] == "ocwp-access-baseline-2"
    with db.factory() as session:
        target = session.get(UserRecord, "target")
        assert target.version == target.session_version == 2
        assert target.location_id == "loc-a" and not target.is_owner


@pytest.mark.parametrize("literal", sorted(QUOTE))
def test_locked_current_account_removal_cannot_be_restored_by_incoming_quote_grant(
    db: Fixture, literal
):
    db.seed("actor", capabilities=OLD_CURRENT)
    incoming = Principal("actor", "org-a", "loc-a", frozenset(OLD_CURRENT | {literal}))
    with db.factory.begin() as session:
        _, effective = AdministrationService.for_fixtures(session).lock_actor(incoming)
        assert effective.capabilities == OLD_CURRENT
