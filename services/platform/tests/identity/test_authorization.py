from datetime import timedelta

import pytest
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.identity.security import PasswordService, SessionTokenService


def test_password_service_hashes_and_verifies_without_plaintext_round_trip() -> None:
    service = PasswordService()
    encoded = service.hash("correct horse battery staple")

    assert "correct horse battery staple" not in encoded
    assert service.verify(encoded, "correct horse battery staple") is True
    assert service.verify(encoded, "wrong") is False


def test_session_token_round_trip_preserves_scoped_principal() -> None:
    service = SessionTokenService(
        secret="test-secret-that-is-long-enough-for-tests", ttl=timedelta(minutes=5)
    )
    principal = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=frozenset({"customers.read", "customers.write"}),
    )

    token = service.issue(principal)
    decoded = service.decode(token)

    assert decoded == principal


def test_authorization_is_deny_by_default() -> None:
    principal = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=frozenset(),
    )

    with pytest.raises(PermissionError, match=r"customers\.read"):
        authorize(
            principal,
            capability="customers.read",
            organization_id="org-1",
            location_id="loc-1",
        )


def test_authorization_rejects_cross_tenant_scope_even_with_capability() -> None:
    principal = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=frozenset({"customers.read"}),
    )

    with pytest.raises(PermissionError, match="organization"):
        authorize(
            principal,
            capability="customers.read",
            organization_id="org-2",
            location_id="loc-2",
        )


def test_authorization_allows_matching_capability_and_scope() -> None:
    principal = Principal(
        user_id="user-1",
        organization_id="org-1",
        location_id="loc-1",
        capabilities=frozenset({"customers.read"}),
    )

    authorize(
        principal,
        capability="customers.read",
        organization_id="org-1",
        location_id="loc-1",
    )


def test_password_service_treats_malformed_hash_as_invalid_credentials() -> None:
    service = PasswordService()
    assert service.verify("not-an-argon2-hash", "correct horse battery staple") is False
