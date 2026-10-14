from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

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


@dataclass(frozen=True, slots=True)
class ValidatedSession:
    principal: Principal
    expires_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


class SessionTokenService:
    def __init__(
        self,
        *,
        secret: str,
        ttl: timedelta = timedelta(hours=8),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("session secret must contain at least 32 characters")
        self._secret = secret
        self._ttl = ttl
        self._clock = clock

    def now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("session clock must be timezone-aware")
        return now.astimezone(UTC)

    def issue(self, principal: Principal) -> str:
        now = self.now()
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
        if principal.dataset_incarnation is not None:
            claims["di"] = principal.dataset_incarnation
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def decode(self, token: str) -> Principal:
        return self.decode_session(token).principal

    def decode_session(self, token: str) -> ValidatedSession:
        claims = jwt.decode(
            token,
            self._secret,
            algorithms=["HS256"],
            issuer="ocwp",
            options={
                "require": ["exp", "iat", "sub", "org", "caps"],
                # Validate temporal claims below against the same injected clock
                # used for issue, post-lock revalidation and offline leases.
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
        for name in ("exp", "iat", "nbf"):
            if name not in claims and name == "nbf":
                continue
            if type(claims[name]) is not int:
                raise jwt.InvalidTokenError("temporal claims must be finite integers")
        now = self.now().timestamp()
        if claims["iat"] > now or claims.get("nbf", claims["iat"]) > now:
            raise jwt.ImmatureSignatureError("session is not yet valid")
        if claims["exp"] <= now:
            raise jwt.ExpiredSignatureError("session expired")
        if claims["exp"] <= claims["iat"]:
            raise jwt.InvalidTokenError("invalid session lifetime")
        try:
            expires_at = datetime.fromtimestamp(claims["exp"], UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise jwt.InvalidTokenError("invalid expiry") from exc
        capabilities = claims.get("caps")
        if not isinstance(capabilities, list) or not all(
            isinstance(value, str) for value in capabilities
        ):
            raise jwt.InvalidTokenError("caps claim must be a string list")
        location_id = claims.get("loc")
        if location_id is not None and not isinstance(location_id, str):
            raise jwt.InvalidTokenError("loc claim must be a string or null")
        incarnation = claims.get("di")
        if "di" in claims:
            try:
                if not isinstance(incarnation, str) or str(UUID(incarnation)) != incarnation:
                    raise ValueError("invalid incarnation")
            except (ValueError, TypeError, AttributeError) as exc:
                raise jwt.InvalidTokenError("invalid incarnation") from exc
        principal = Principal(
            user_id=str(claims["sub"]),
            organization_id=str(claims["org"]),
            location_id=location_id,
            capabilities=frozenset(capabilities),
            session_version=int(claims.get("sv", 1)),
            dataset_incarnation=incarnation,
            expires_at=expires_at,
        )

        return ValidatedSession(principal=principal, expires_at=expires_at)
