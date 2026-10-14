"""Versioned, exact wire-command equality; this is not authentication.

See docs/10-spec-development/2026-10-14-command-receipt-proof.md. The raw-body
middleware runs before Pydantic so coercion cannot downgrade a stored proof.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cycling_workshop.sync.domain import MutationEnvelope

PROOF_VERSION = 1
PROOF_PREFIX = b"ocwp-sync-command-proof-v1\n"
MUTATION_BODY_LIMIT = 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_SAFE_INTEGER = 2**53 - 1
_FIELDS = frozenset(
    {
        "mutation_id",
        "entity_type",
        "entity_id",
        "operation",
        "organization_id",
        "location_id",
        "base_version",
        "occurred_at",
        "payload",
    }
)
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class InvalidCommandProof(ValueError):
    """Raw input has no supported, unambiguous v1 command identity."""


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def valid_actor(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 36
        and not any(character.isspace() for character in value)
        and not any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    )


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InvalidCommandProof("duplicate JSON object key")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise InvalidCommandProof("nonfinite JSON number")


def _string(value: str) -> str:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise InvalidCommandProof("surrogate is not a Unicode scalar value")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _number(value: int | float | Decimal) -> str:
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise InvalidCommandProof("integer is outside the interoperable safe range")
        return str(value)
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    binary = float(number)
    if not number.is_finite() or not math.isfinite(binary):
        raise InvalidCommandProof("number is not finite")
    if number != Decimal(str(binary)):
        raise InvalidCommandProof("number does not round-trip through binary64")
    if number == number.to_integral_value() and number.copy_abs() > MAX_SAFE_INTEGER:
        raise InvalidCommandProof("integer is outside the interoperable safe range")
    if number.is_zero():
        return "0"
    # No Decimal.normalize(): its ambient precision could silently round input.
    plain = format(number, "f")
    return plain.rstrip("0").rstrip(".") if "." in plain else plain


def _canonical(value: object, *, depth: int = 0) -> str:
    if depth > MAX_JSON_DEPTH:
        raise InvalidCommandProof("JSON nesting exceeds supported depth")
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, str):
        return _string(value)
    if type(value) in (int, float, Decimal):
        return _number(value)  # type: ignore[arg-type]
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item, depth=depth + 1) for item in value) + "]"
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return (
            "{"
            + ",".join(
                _string(key) + ":" + _canonical(value[key], depth=depth + 1)
                for key in sorted(value)
            )
            + "}"
        )
    raise InvalidCommandProof("unsupported JSON value")


def _timestamp(value: object) -> str:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise InvalidCommandProof("timestamp must be aware ISO text with microsecond precision")
    # RFC3339 -00:00 denotes an unknown local offset, not known UTC.
    if value.endswith("-00:00"):
        raise InvalidCommandProof("timestamp offset is unknown")
    if value[-6:-5] in {"+", "-"} and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise InvalidCommandProof("timestamp offset is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError) as exc:
        raise InvalidCommandProof("timestamp is outside the supported range") from exc


def canonical_command_bytes(command: object) -> bytes:
    """Return v1 bytes, including the domain separator, or reject without coercion."""
    if not isinstance(command, dict) or set(command) != _FIELDS:
        raise InvalidCommandProof("command must contain exactly the complete envelope fields")
    for field in ("mutation_id", "entity_id", "organization_id", "location_id"):
        identity = command[field]
        if not valid_actor(identity):
            raise InvalidCommandProof("command identity is invalid")
        if field in {"mutation_id", "entity_id"} and len(str(identity)) != 36:
            raise InvalidCommandProof("mutation and entity identity must have 36 characters")
    if command["entity_type"] not in ("customer", "bicycle", "service_order"):
        raise InvalidCommandProof("unsupported entity type")
    if command["operation"] not in ("create", "update"):
        raise InvalidCommandProof("unsupported operation")
    base = command["base_version"]
    if base is not None and (type(base) is not int or not 0 <= base <= MAX_SAFE_INTEGER):
        raise InvalidCommandProof("base_version must be a safe nonnegative integer or null")
    if not isinstance(command["payload"], dict):
        raise InvalidCommandProof("payload must be an object")
    normalized = {**command, "occurred_at": _timestamp(command["occurred_at"])}
    try:
        return PROOF_PREFIX + _canonical(normalized).encode("utf-8")
    except (ValueError, OverflowError, InvalidOperation) as exc:
        raise InvalidCommandProof("command is not representable") from exc


def command_digest(command: object) -> str:
    return hashlib.sha256(canonical_command_bytes(command)).hexdigest()


def envelope_digest(envelope: MutationEnvelope) -> str:
    """Recheck an already validated envelope; never substitutes for raw validation."""
    return command_digest(
        {
            "mutation_id": envelope.mutation_id,
            "entity_type": envelope.entity_type,
            "entity_id": envelope.entity_id,
            "operation": envelope.operation,
            "organization_id": envelope.organization_id,
            "location_id": envelope.location_id,
            "base_version": envelope.base_version,
            "occurred_at": envelope.occurred_at.isoformat(),
            "payload": dict(envelope.payload),
        }
    )


def parse_command_proofs(body: bytes, *, strict: bool) -> tuple[str | None, ...]:
    """One positional raw proof per command. Legacy ambiguity never yields proof."""
    if len(body) > MUTATION_BODY_LIMIT:
        raise InvalidCommandProof("mutation request exceeds byte limit")
    try:
        document = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=Decimal,
            parse_constant=_constant,
        )
        if not isinstance(document, dict) or set(document) != {"mutations"}:
            raise InvalidCommandProof("batch must contain only mutations")
        mutations = document["mutations"]
        if not isinstance(mutations, list) or not 1 <= len(mutations) <= 100:
            raise InvalidCommandProof("batch must contain 1 to 100 mutations")
        proofs: list[str | None] = []
        for mutation in mutations:
            try:
                proofs.append(command_digest(mutation))
            except (ValueError, OverflowError, InvalidOperation, RecursionError) as exc:
                if strict:
                    raise InvalidCommandProof("invalid canonical command") from exc
                proofs.append(None)
        return tuple(proofs)
    except (ValueError, OverflowError, InvalidOperation, RecursionError) as exc:
        if strict:
            raise InvalidCommandProof("invalid canonical mutation batch") from exc
        return ()


class MutationBodyProofMiddleware:
    """Bound streamed input and prepare raw proofs before FastAPI/Pydantic reads it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope["path"].rstrip("/") != "/api/v1/sync/mutations"
        ):
            await self.app(scope, receive, send)
            return
        buffer = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(buffer) + len(chunk) > MUTATION_BODY_LIMIT:
                await self._error(send, status=413, code="request_too_large")
                return
            buffer.extend(chunk)
            if not message.get("more_body", False):
                break
        protocols = [
            value for key, value in scope["headers"] if key.lower() == b"x-ocwp-write-protocol"
        ]
        strict = protocols == [b"1"]
        body = bytes(buffer)
        try:
            proofs = parse_command_proofs(body, strict=strict)
        except InvalidCommandProof:
            await self._error(send, status=422, code="invalid_canonical_command")
            return
        scope.setdefault("state", {})["sync_command_proofs"] = proofs
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _error(send: Send, *, status: int, code: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": json.dumps(
                    {
                        "error": {
                            "code": code,
                            "message": "mutation request cannot be admitted",
                            "details": {},
                            "request_id": None,
                        }
                    }
                ).encode("utf-8"),
            }
        )
