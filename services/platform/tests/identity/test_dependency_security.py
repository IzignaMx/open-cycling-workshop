"""Executable regression coverage for the audited JWT and HTTP dependency boundary."""

import base64
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.security import SessionTokenService
from starlette.requests import Request
from test_auth_api import build_client

SECRET = "synthetic-dependency-test-secret-at-least-64-characters-for-hs512-control"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def session_service() -> SessionTokenService:
    return SessionTokenService(secret=SECRET, clock=lambda: NOW)


def test_noncanonical_signature_is_not_an_alternate_session_serialization() -> None:
    service = session_service()
    principal = Principal("user-1", "org-1", "loc-1", frozenset({"customers.read"}))
    token = service.issue(principal)
    assert service.decode(token) == principal
    with pytest.raises(jwt.InvalidTokenError):
        service.decode(token + "!!!!")


def test_deep_unsigned_header_raises_the_documented_token_error() -> None:
    # Bounded synthetic input; no network or real account/credential is involved.
    header = base64.urlsafe_b64encode(b"[" * 100_000).rstrip(b"=").decode()
    token = f"{header}.e30.eA"
    with pytest.raises(jwt.InvalidTokenError):
        session_service().decode(token)


def test_unverified_deep_payload_raises_the_documented_token_error() -> None:
    # GHSA-42vr-xj54-vc7v affects the unverified decode used by PyJWKClient.
    # OCWP does not use that flow: its verified decode rejects this bad signature.
    payload = base64.urlsafe_b64encode(b"[" * 100_000).rstrip(b"=").decode()
    token = f"eyJhbGciOiJIUzI1NiJ9.{payload}.eA"
    with pytest.raises(jwt.InvalidSignatureError):
        session_service().decode(token)
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token, options={"verify_signature": False})


def test_unverified_decode_does_not_poison_reused_options() -> None:
    # GHSA-gvp8-978c-rx2q is conditional on options reuse, which OCWP does not do.
    # Exercise the library fix directly rather than claiming that condition exists.
    token = jwt.encode({"exp": 1}, SECRET, algorithm="HS256")
    options = {"verify_signature": False}
    assert jwt.decode(token, options=options) == {"exp": 1}
    assert options == {"verify_signature": False}
    options["verify_signature"] = True
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, SECRET, algorithms=["HS256"], options=options)


@pytest.mark.parametrize("algorithm", ["HS384", "HS512"])
def test_session_algorithm_allowlist_stays_hs256_only(algorithm: str) -> None:
    claims = jwt.decode(
        session_service().issue(Principal("u", "o", "l", frozenset())),
        SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        session_service().decode(jwt.encode(claims, SECRET, algorithm=algorithm))


def test_session_expiry_still_uses_the_injected_clock() -> None:
    service = session_service()
    principal = Principal("u", "o", "l", frozenset())
    token = service.issue(principal)
    expired_service = SessionTokenService(secret=SECRET, clock=lambda: NOW + timedelta(hours=8))
    with pytest.raises(jwt.ExpiredSignatureError):
        expired_service.decode(token)


@pytest.mark.parametrize("host", ["testserver/forged", "testserver?forged", "testserver#forged"])
@pytest.mark.parametrize("authenticated", [False, True])
def test_malformed_host_cannot_remove_private_response_no_store(
    host: str, authenticated: bool
) -> None:
    client = build_client()
    try:
        headers = {"Host": host}
        if authenticated:
            token = client.app.state.session_tokens.issue(
                Principal("user-1", "org-1", "loc-1", frozenset({"customers.read"}))
            )
            headers["Authorization"] = f"Bearer {token}"
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == (200 if authenticated else 401)
        assert response.headers.get("cache-control") == "no-store"
        if authenticated:
            assert response.json()["user_id"] == "user-1"
        else:
            assert response.json() == {"detail": "missing bearer token"}
    finally:
        client.close()
        client.app.state.session_factory.kw["bind"].dispose()


def test_request_path_cannot_replace_url_authority() -> None:
    request = Request(
        {
            "type": "http",
            "scheme": "http",
            "path": "@attacker.invalid",
            "query_string": b"",
            "headers": [(b"host", b"trusted.invalid")],
            "server": ("trusted.invalid", 80),
        }
    )
    assert request.url.hostname == "trusted.invalid"
