from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
import jwt

from cycling_workshop.identity.domain import Principal
from cycling_workshop.shared.ids import new_id


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        if len(password) < 12:
            raise ValueError("password must contain at least 12 characters")
        return self._hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False


class SessionTokenService:
    def __init__(self, *, secret: str, ttl: timedelta = timedelta(hours=8)) -> None:
        if len(secret) < 32:
            raise ValueError("session secret must contain at least 32 characters")
        self._secret = secret
        self._ttl = ttl

    def issue(self, principal: Principal) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "iss": "ocwp",
            "sub": principal.user_id,
            "org": principal.organization_id,
            "loc": principal.location_id,
            "caps": sorted(principal.capabilities),
            "sv": principal.session_version,
            "iat": now,
            "nbf": now,
            "exp": now + self._ttl,
            "jti": new_id(),
        }
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def decode(self, token: str) -> Principal:
        claims = jwt.decode(
            token,
            self._secret,
            algorithms=["HS256"],
            issuer="ocwp",
            options={"require": ["exp", "iat", "sub", "org", "caps"]},
        )
        capabilities = claims.get("caps")
        if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
            raise jwt.InvalidTokenError("caps claim must be a string list")
        location_id = claims.get("loc")
        if location_id is not None and not isinstance(location_id, str):
            raise jwt.InvalidTokenError("loc claim must be a string or null")
        return Principal(
            user_id=str(claims["sub"]),
            organization_id=str(claims["org"]),
            location_id=location_id,
            capabilities=frozenset(capabilities),
            session_version=int(claims.get("sv", 1)),
        )
