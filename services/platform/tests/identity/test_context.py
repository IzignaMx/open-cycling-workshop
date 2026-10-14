"""Context is an unactivated server prerequisite, never a baseline credential."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from test_auth_api import build_client

SECRET = "test-secret-that-is-long-enough-for-tests"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def context_client(account_grants, token_grants, *, location="loc-1", ttl=timedelta(hours=12)):
    client = build_client()
    client.app.state.session_tokens = SessionTokenService(secret=SECRET, ttl=ttl, clock=lambda: NOW)
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        account.capabilities = account_grants
        account.location_id = location
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", location, frozenset(token_grants))
    )
    return client, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("account", "token", "expected"),
    [
        (["*"], ["*"], sorted(CAPABILITIES)),
        (["*"], ["customers.read"], []),
        (["customers.read"], ["*"], []),
        (["*", "customers.read"], ["customers.read"], ["customers.read"]),
        (["customers.read"], ["*", "customers.read"], ["customers.read"]),
        (["unknown", "customers.write"], ["unknown", "customers.write"], ["customers.write"]),
        (["customers.read"], [], []),
    ],
)
def test_context_literal_intersection_precedes_known_catalog(account, token, expected):
    client, headers = context_client(account, token)
    response = client.get("/api/v1/auth/context", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["capabilities"] == expected
    assert data["principal"] == {"api_realm": None, "organization_id": "org-1", "user_id": "user-1"}
    assert data["selected_location_id"] == data["account_location_id"] == "loc-1"
    assert data["snapshot_protocol"] is None
    assert data["verified_at"] == "2026-10-14T12:00:00Z"
    assert data["offline_until"] == "2026-10-14T20:00:00Z"
    assert response.headers["cache-control"] == "no-store"


def test_context_lease_is_bounded_by_validated_token_expiry():
    client, headers = context_client([], [], ttl=timedelta(minutes=2))
    response = client.get("/api/v1/auth/context", headers=headers)
    assert response.json()["offline_until"] == "2026-10-14T12:02:00Z"


def test_context_org_scope_requires_concrete_owned_location():
    client, headers = context_client([], [], location=None)
    missing = client.get("/api/v1/auth/context", headers=headers)
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "location_required"
    with client.app.state.session_factory.begin() as session:
        session.add(OrganizationRecord(id="org-2", name="Other"))
        session.add(LocationRecord(id="foreign", organization_id="org-2", name="Other"))
    for location in ("missing", "foreign"):
        assert (
            client.get(
                f"/api/v1/auth/context?selected_location_id={location}", headers=headers
            ).status_code
            == 403
        )
    assert (
        client.get("/api/v1/auth/context?selected_location_id=loc-1", headers=headers).status_code
        == 200
    )


def test_context_location_bound_cannot_select_other_and_must_exist():
    client, headers = context_client([], [])
    assert (
        client.get("/api/v1/auth/context?selected_location_id=other", headers=headers).status_code
        == 403
    )
    with client.app.state.session_factory.begin() as session:
        session.delete(session.get(LocationRecord, "loc-1"))
    assert client.get("/api/v1/auth/context", headers=headers).status_code == 403


def test_epoch_stable_across_display_renewal_and_selection_but_not_session_or_grants():
    client, headers = context_client(["customers.read"], ["customers.read"], location=None)

    def fetch(headers=headers, location="loc-1"):
        response = client.get(
            f"/api/v1/auth/context?selected_location_id={location}", headers=headers
        )
        assert response.status_code == 200
        return response.json()["authorization_epoch"]

    initial = fetch()
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        account.display_name = "Renamed"
        account.version += 1
        session.add(LocationRecord(id="loc-2", organization_id="org-1", name="Second"))
    assert fetch(location="loc-2") == initial
    client.app.state.session_tokens = SessionTokenService(
        secret=SECRET, clock=lambda: NOW + timedelta(minutes=1)
    )
    renewed = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", None, frozenset({"customers.read"}))
    )
    old_claims = jwt.decode(
        headers["Authorization"].split()[1], options={"verify_signature": False}
    )
    new_claims = jwt.decode(renewed, options={"verify_signature": False})
    assert old_claims["iat"] != new_claims["iat"]
    assert old_claims["exp"] != new_claims["exp"]
    assert fetch({"Authorization": f"Bearer {renewed}"}) == initial
    with client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = []
    assert fetch() != initial
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        account.capabilities = ["customers.read"]
        account.session_version = 2
    assert (
        client.get("/api/v1/auth/context?selected_location_id=loc-1", headers=headers).status_code
        == 401
    )
    renewed = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", None, frozenset({"customers.read"}), session_version=2)
    )
    assert fetch({"Authorization": f"Bearer {renewed}"}) != initial


@pytest.mark.parametrize("claim", ["exp", "iat", "nbf"])
@pytest.mark.parametrize("value", [True, "1791979200", 1.5, float("inf"), float("nan"), None])
def test_malformed_signed_temporal_claims_rejected(claim, value):
    service = SessionTokenService(secret=SECRET, clock=lambda: NOW)
    token = service.issue(Principal("user-1", "org-1", "loc-1", frozenset()))
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_signature": False})
    claims[claim] = value
    with pytest.raises(jwt.InvalidTokenError):
        service.decode_session(jwt.encode(claims, SECRET, algorithm="HS256"))


def test_context_no_store_even_for_invalid_session_and_never_trusts_host():
    client, headers = context_client([], [])
    response = client.get(
        "/api/v1/auth/context",
        headers={**headers, "Host": "evil.example", "X-Forwarded-Host": "evil.example"},
    )
    assert response.json()["principal"]["api_realm"] is None
    for params in ({}, {"Authorization": "Bearer invalid"}):
        denied = client.get("/api/v1/auth/context", headers=params)
        assert denied.status_code == 401
        assert denied.headers["cache-control"] == "no-store"


def test_context_checks_expiry_again_after_location_lookup(monkeypatch):
    client, headers = context_client([], [], ttl=timedelta(seconds=60))
    # Unit control for the final response check; real lock waits are separate PG cases.
    times = iter([NOW, NOW, NOW + timedelta(seconds=60)])
    monkeypatch.setattr(client.app.state.session_tokens, "now", lambda: next(times))
    response = client.get("/api/v1/auth/context", headers=headers)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "change", ["expired", "future_iat", "future_nbf", "wrong_issuer", "missing_exp", "signature"]
)
def test_decode_session_retains_authentication_guards(change):
    service = SessionTokenService(secret=SECRET, clock=lambda: NOW)
    token = service.issue(Principal("user-1", "org-1", "loc-1", frozenset()))
    claims = jwt.decode(token, options={"verify_signature": False})
    if change == "expired":
        claims["exp"] = int(NOW.timestamp())
    elif change == "future_iat":
        claims["iat"] = int(NOW.timestamp()) + 1
    elif change == "future_nbf":
        claims["nbf"] = int(NOW.timestamp()) + 1
    elif change == "wrong_issuer":
        claims["iss"] = "other"
    elif change == "missing_exp":
        del claims["exp"]
    encoded = jwt.encode(
        claims, SECRET if change != "signature" else SECRET + "wrong", algorithm="HS256"
    )
    with pytest.raises(jwt.InvalidTokenError):
        service.decode(encoded)


def test_decode_wrapper_preserves_principal_and_expiry_is_internal():
    service = SessionTokenService(secret=SECRET, clock=lambda: NOW)
    principal = Principal("user-1", "org-1", "loc-1", frozenset({"customers.read"}))
    token = service.issue(principal)
    assert service.decode(token) == principal
    assert service.decode_session(token).principal == principal
    assert service.decode_session(token).expires_at == NOW + timedelta(hours=8)


@pytest.mark.parametrize("location", ["", "x" * 37, "\x00"])
def test_selected_location_query_bounds_and_no_store(location):
    client, headers = context_client([], [])
    response = client.get(
        "/api/v1/auth/context", params={"selected_location_id": location}, headers=headers
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"


def test_context_unexpected_failure_is_sanitized_and_no_store():
    from cycling_workshop.db.dependencies import get_session
    from fastapi.testclient import TestClient

    client, headers = context_client([], [])

    def failed_session():
        raise RuntimeError("private driver information must never be returned")

    client.app.dependency_overrides[get_session] = failed_session
    response = TestClient(client.app, raise_server_exceptions=False).get(
        "/api/v1/auth/context", headers=headers
    )
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "internal server error"}


def test_context_unexpected_failure_rolls_back_and_logs_without_private_details(
    monkeypatch, caplog
):
    import cycling_workshop.identity.context as context_module
    from sqlalchemy import event

    client, headers = context_client([], [])
    rolled_back = []
    event.listen(
        client.app.state.session_factory, "after_rollback", lambda session: rolled_back.append(True)
    )

    def fail_after_lock(*args):
        raise RuntimeError("private driver credential and claims")

    monkeypatch.setattr(context_module, "effective_principal", fail_after_lock)
    response = client.get("/api/v1/auth/context", headers=headers)
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert rolled_back == [True]
    assert "authenticated context request failed" in caplog.text
    assert "private driver credential" not in caplog.text
    assert headers["Authorization"] not in caplog.text
