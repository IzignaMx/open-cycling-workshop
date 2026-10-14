"""Authenticated opaque metadata; possession never replaces bearer authorization."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

from cycling_workshop.api.errors import ApiError

MAX_SEQUENCE = 2**53 - 1
_DOMAIN = b"ocwp:bounded-baseline:v1\x00"
_REFERENCE = re.compile(r"[A-Za-z0-9_-]{32}", re.ASCII)
_TOKEN = re.compile(
    r"b1\.([A-Za-z0-9_-]{32})\.(0|[1-9][0-9]{0,15})\."
    r"(scan|finalize|delta|checkpoint)\.([A-Za-z0-9_-]{43})",
    re.ASCII,
)
_PURPOSES = frozenset({"scan", "finalize", "delta", "checkpoint"})


def _invalid() -> ApiError:
    return ApiError(422, "cursor_invalid", "Invalid continuation")


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def reference_hash(reference: str) -> str:
    if not isinstance(reference, str) or _REFERENCE.fullmatch(reference) is None:
        raise _invalid()
    return hashlib.sha256(reference.encode("ascii")).hexdigest()


def token_hash(token: str) -> str:
    if not isinstance(token, str) or not token.isascii() or not 1 <= len(token) <= 512:
        raise _invalid()
    return hashlib.sha256(token.encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True)
class DecodedContinuation:
    reference: str
    sequence: int
    purpose: str


class BaselineCodec:
    def __init__(self, secret: str):
        if not isinstance(secret, str) or not secret:
            raise _invalid()
        self._key = secret.encode("utf-8")

    def new_reference(self) -> str:
        return secrets.token_urlsafe(24)

    def encode(self, reference: str, sequence: int, purpose: str) -> str:
        reference_hash(reference)
        if type(sequence) is not int or not 0 <= sequence <= MAX_SEQUENCE:
            raise _invalid()
        if not isinstance(purpose, str) or purpose not in _PURPOSES:
            raise _invalid()
        prefix = f"b1.{reference}.{sequence}.{purpose}"
        return f"{prefix}.{self._signature(prefix)}"

    def _signature(self, prefix: str) -> str:
        return _b64(hmac.digest(self._key, _DOMAIN + prefix.encode("ascii"), "sha256"))

    def decode(self, token: str) -> DecodedContinuation:
        if not isinstance(token, str) or not token.isascii() or len(token) > 512:
            raise _invalid()
        match = _TOKEN.fullmatch(token)
        if match is None:
            raise _invalid()
        reference, raw_sequence, purpose, signature = match.groups()
        sequence = int(raw_sequence)
        if sequence > MAX_SEQUENCE:
            raise _invalid()
        prefix = token.rsplit(".", 1)[0]
        # Compare canonical encoded MACs too: alternate base64 pad bits cannot alias.
        if not hmac.compare_digest(signature, self._signature(prefix)):
            raise _invalid()
        return DecodedContinuation(reference, sequence, purpose)
