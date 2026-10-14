"""Identity HTTP responses must not be retained by browser or shared caches."""

import logging
from collections.abc import Iterator

import httpx
import pytest
from cycling_workshop.app import create_app
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_auth_api import build_client

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "synthetic changed password"
SUPPLIED_REQUEST_ID = "caller-supplied-private-correlation"
AUTH = "/api/v1/auth"
ADMIN = "/api/v1/admin"
LOCATIONS = "/api/v1/locations"
OPERATIONS = [
    (
        "POST",
        f"{AUTH}/login",
        {"organization_id": "org-1", "username": "admin", "password": PASSWORD},
        200,
    ),
    ("GET", f"{AUTH}/me", None, 200),
    ("POST", f"{AUTH}/logout-all", None, 204),
    (
        "POST",
        f"{AUTH}/change-password",
        {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        204,
    ),
    ("GET", f"{ADMIN}/roles", None, 200),
    ("GET", f"{ADMIN}/users", None, 200),
    (
        "POST",
        f"{ADMIN}/users",
        {
            "username": "new-user",
            "display_name": "New user",
            "location_id": "loc-1",
            "role": "TechnicalAdmin",
            "password": PASSWORD,
        },
        201,
    ),
    ("PATCH", f"{ADMIN}/users/target", {"expected_version": 1, "display_name": "Updated"}, 200),
    ("POST", f"{ADMIN}/users/target/revoke-sessions", {"expected_version": 1}, 200),
    (
        "POST",
        f"{ADMIN}/users/target/reset-password",
        {"expected_version": 1, "new_password": NEW_PASSWORD},
        200,
    ),
    ("GET", LOCATIONS, None, 200),
    ("POST", LOCATIONS, {"name": "Second workshop"}, 201),
]


@pytest.fixture
def identity_client() -> Iterator[TestClient]:
    client = build_client()
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        account.location_id = None
        account.capabilities = sorted(CAPABILITIES)
        session.add(
            UserRecord(
                id="target",
                organization_id="org-1",
                location_id="loc-1",
                username="target",
                display_name="Target",
                password_hash=account.password_hash,
                capabilities=[],
                is_active=True,
            )
        )
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", None, frozenset(CAPABILITIES))
    )
    client.headers.update({"Authorization": f"Bearer {token}", "X-Request-ID": SUPPLIED_REQUEST_ID})
    with client:
        yield client
    client.app.state.session_factory.kw["bind"].dispose()


def assert_private_response(response: httpx.Response) -> None:
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert response.headers["x-request-id"] != SUPPLIED_REQUEST_ID


@pytest.mark.parametrize("method,path,body,status", OPERATIONS)
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_success_and_trailing_slash_redirects_are_no_store(
    identity_client, method, path, body, status, trailing_slash
):
    response = identity_client.request(
        method, path + ("/" if trailing_slash else ""), json=body, follow_redirects=True
    )
    assert response.status_code == status, response.text
    assert_private_response(response)
    assert len(response.history) == int(trailing_slash)
    for redirect in response.history:
        assert redirect.status_code == 307
        assert_private_response(redirect)


@pytest.mark.parametrize("method,path,body,status", OPERATIONS)
def test_rejected_authentication_is_no_store(identity_client, method, path, body, status):
    del status
    identity_client.headers["Authorization"] = "Bearer invalid"
    if path == f"{AUTH}/login":
        body = {**body, "password": "synthetic incorrect password"}
    response = identity_client.request(method, path, json=body)
    assert response.status_code == 401
    assert_private_response(response)


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", f"{AUTH}/login", {"password": PASSWORD}),
        ("POST", f"{AUTH}/change-password", {"current_password": PASSWORD}),
        ("GET", f"{ADMIN}/users?limit=0", None),
        ("POST", f"{ADMIN}/users", {"password": PASSWORD}),
        ("PATCH", f"{ADMIN}/users/target", {"expected_version": 0}),
        ("POST", f"{ADMIN}/users/target/revoke-sessions", {"expected_version": 0}),
        ("POST", f"{ADMIN}/users/target/reset-password", {"new_password": PASSWORD}),
        ("GET", f"{LOCATIONS}?limit=0", None),
        ("POST", LOCATIONS, {"name": ""}),
    ],
)
def test_validation_errors_are_redacted_and_no_store(identity_client, method, path, body, caplog):
    response = identity_client.request(method, path, json=body)
    assert response.status_code == 422
    assert_private_response(response)
    for error in response.json()["detail"]:
        assert set(error) == {"loc", "type", "msg"}
    assert PASSWORD not in response.text + caplog.text


@pytest.mark.parametrize("path", [f"{ADMIN}/roles", f"{ADMIN}/users", LOCATIONS])
def test_capability_denials_are_no_store(identity_client, path):
    with identity_client.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = []
    response = identity_client.get(path)
    assert response.status_code == 403
    assert_private_response(response)


@pytest.mark.parametrize("target,version,status", [("target", 2, 409), ("absent", 1, 404)])
def test_safe_command_errors_are_no_store(identity_client, target, version, status):
    response = identity_client.patch(
        f"{ADMIN}/users/{target}", json={"expected_version": version, "display_name": "Updated"}
    )
    assert response.status_code == status
    assert_private_response(response)
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("method,path,body,status", OPERATIONS)
@pytest.mark.parametrize("failure,expected", [(RuntimeError, 500), (SQLAlchemyError, 503)])
def test_failures_are_sanitized_no_store_and_safely_correlated(
    identity_client, method, path, body, status, failure, expected, caplog, monkeypatch
):
    del status
    private_detail = f"private driver and credential: {PASSWORD}"
    # Earlier in-process Alembic migrations disable existing application loggers.
    monkeypatch.setattr(logging.getLogger("cycling_workshop.app"), "disabled", False)

    def fail():
        raise failure(private_detail)

    identity_client.app.dependency_overrides[get_session] = fail
    identity_client.app.dependency_overrides[principal_from_request] = fail
    client = TestClient(identity_client.app, raise_server_exceptions=False)
    response = client.request(method, path, json=body, headers=identity_client.headers)
    assert response.status_code == expected
    assert_private_response(response)
    if expected == 500:
        assert response.json() == {"detail": "internal server error"}
        assert "identity request failed" in caplog.text
    else:
        assert response.json()["error"]["code"] == "database_command_failed"
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    for secret in (private_detail, PASSWORD, identity_client.headers["Authorization"]):
        assert secret not in response.text + caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("path", [ADMIN, f"{ADMIN}/", f"{ADMIN}/unknown", f"{ADMIN}/unknown/"])
def test_admin_family_not_found_responses_are_no_store(path):
    response = TestClient(create_app(Settings(environment="test"))).get(path)
    assert response.status_code == 404
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        f"{AUTH}/login-extra",
        f"{AUTH}/me-extra",
        f"{AUTH}/logout-all-extra",
        f"{AUTH}/change-password-extra",
        f"{AUTH}/context-extra",
        f"{AUTH}/login/nested",
        f"{ADMIN}-extra",
        f"{ADMIN}-extra/users",
        f"{LOCATIONS}-extra",
        f"{LOCATIONS}/nested",
        "/api/v1/customers/absent",
        "/health/live",
    ],
)
def test_unrelated_route_cache_behavior_is_unchanged(path):
    response = TestClient(create_app(Settings(environment="test"))).get(path)
    assert "cache-control" not in response.headers


def test_public_health_preserves_caller_supplied_correlation():
    response = TestClient(create_app(Settings(environment="test"))).get(
        "/health/live", headers={"X-Request-ID": SUPPLIED_REQUEST_ID}
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == SUPPLIED_REQUEST_ID
    assert "cache-control" not in response.headers
