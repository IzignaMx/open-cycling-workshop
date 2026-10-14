"""The current-user response describes authenticated authority, not raw grants."""

from dataclasses import replace

import pytest
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from test_auth_api import build_client


@pytest.mark.parametrize(
    ("account_grants", "token_grants", "expected"),
    [
        (["customers.read", "customers.write"], ["customers.read"], ["customers.read"]),
        (["customers.read"], ["customers.read", "customers.write"], ["customers.read"]),
        (["customers.read"], [], []),
        (["*"], ["*"], ["*"]),
        (["*"], ["customers.read"], []),
        (["customers.read"], ["*"], []),
    ],
)
def test_me_returns_the_existing_effective_grant_intersection(
    account_grants: list[str], token_grants: list[str], expected: list[str]
) -> None:
    client = build_client()
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        assert account is not None
        account.capabilities = account_grants
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", "loc-1", frozenset(token_grants))
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["capabilities"] == expected
    assert set(response.json()) == {
        "user_id",
        "organization_id",
        "location_id",
        "display_name",
        "capabilities",
    }


@pytest.mark.parametrize(
    ("account_location", "token_location", "expected"),
    [(None, "loc-1", "loc-1"), ("loc-1", None, "loc-1"), (None, None, None)],
)
def test_me_never_widens_the_authenticated_location(
    account_location: str | None, token_location: str | None, expected: str | None
) -> None:
    client = build_client()
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        assert account is not None
        account.location_id = account_location
    token = client.app.state.session_tokens.issue(
        Principal("user-1", "org-1", token_location, frozenset({"customers.read"}))
    )

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["location_id"] == expected


@pytest.mark.parametrize("change", ["session", "deactivate", "scope", "grants", "narrow"])
def test_me_revalidates_persisted_state_after_dependency_authentication(change: str) -> None:
    client = build_client()
    authenticated = Principal("user-1", "org-1", "loc-1", frozenset({"customers.read"}))
    if change == "narrow":
        authenticated = replace(authenticated, location_id=None)
    # Model the earlier dependency snapshot without claiming SQLite lock evidence.
    client.app.dependency_overrides[principal_from_request] = lambda: authenticated
    with client.app.state.session_factory.begin() as session:
        account = session.get(UserRecord, "user-1")
        assert account is not None
        if change == "session":
            account.session_version += 1
        elif change == "deactivate":
            account.is_active = False
        elif change == "scope":
            account.location_id = "loc-other"
        elif change == "grants":
            account.capabilities = []

    response = client.get("/api/v1/auth/me")

    if change in {"session", "deactivate", "scope"}:
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid session"
    else:
        assert response.status_code == 200
        assert response.json()["capabilities"] == ([] if change == "grants" else ["customers.read"])
        assert response.json()["location_id"] == "loc-1"
