"""Bounded, lossless codec for quote-linked complete order projections only."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import cast

from cycling_workshop.service_orders.domain import OrderState

ORDER_SOURCE_MAX_BYTES = 262_144
ORDER_CANONICAL_MAX_BYTES = 262_144
ORDER_RAW_MAX_BYTES = 1_048_576
ORDER_JSON_MAX_DEPTH = 12
ORDER_VERSION_MAX = 2_147_483_647
_FIELDS = frozenset(
    {
        "order_id",
        "customer_id",
        "bicycle_id",
        "organization_id",
        "location_id",
        "state",
        "reported_problem",
        "intake_condition",
        "accessories",
        "priority",
        "diagnosis",
        "created_at",
        "updated_at",
        "version",
    }
)
_SOURCE_FIELDS = ("reported_problem", "intake_condition", "accessories", "priority", "diagnosis")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z", re.ASCII)
type Scalar = str | int | None


class OrderProjectionIntegrityError(ValueError):
    """A retained order projection cannot be accepted without repair."""


class OrderProjectionLimitError(OrderProjectionIntegrityError):
    """The finite quote-linked projection boundary was exceeded."""


@dataclass(frozen=True, slots=True)
class PreparedOrderProjection:
    payload: Mapping[str, Scalar]
    raw_json: str
    raw_octets: int
    canonical_utf8: bytes

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


def _string(value: object) -> str:
    if type(value) is not str:
        raise OrderProjectionIntegrityError("order projection string required")
    if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise OrderProjectionIntegrityError("order projection invalid Unicode")
    return value


def _identity(value: object) -> None:
    value = _string(value)
    if not 1 <= len(value) <= 36 or len(value.encode("utf-8")) > 144:
        raise OrderProjectionIntegrityError("order projection identity size")
    if any(char.isspace() for char in value):
        raise OrderProjectionIntegrityError("order projection identity whitespace")


def _timestamp(value: object) -> None:
    value = _string(value)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise OrderProjectionIntegrityError("order projection timestamp") from error
    if parsed.utcoffset() != timedelta(0) or parsed.isoformat() != value:
        raise OrderProjectionIntegrityError("order projection canonical UTC timestamp required")


def _validated(payload: object) -> dict[str, Scalar]:
    if not isinstance(payload, Mapping) or set(payload) != _FIELDS:
        raise OrderProjectionIntegrityError("order projection exact fields required")
    # Copy before validation; callers retain no reference to the prepared snapshot.
    result = dict(payload)
    for key, value in result.items():
        _string(key)
        if value is not None and type(value) not in (str, int):
            raise OrderProjectionIntegrityError("order projection scalar required")
        if isinstance(value, str):
            _string(value)
    for key in ("order_id", "customer_id", "organization_id", "location_id"):
        _identity(result[key])
    if result["bicycle_id"] is not None:
        _identity(result["bicycle_id"])
    if type(result["state"]) is not str or result["state"] not in {
        state.value for state in OrderState
    }:
        raise OrderProjectionIntegrityError("order projection state")
    for key in _SOURCE_FIELDS:
        if result[key] is not None or key in ("reported_problem", "priority"):
            _string(result[key])
    version = result["version"]
    if type(version) is not int or not 1 <= version <= ORDER_VERSION_MAX:
        raise OrderProjectionIntegrityError("order projection SQL integer version")
    for key in ("created_at", "updated_at"):
        _timestamp(result[key])
    source_octets = 0
    for key in _SOURCE_FIELDS:
        if result[key] is None:
            continue
        value = _string(result[key])
        if len(value) > ORDER_SOURCE_MAX_BYTES:
            raise OrderProjectionLimitError("order effect source payload limit")
        source_octets += len(value.encode("utf-8"))
        if source_octets > ORDER_SOURCE_MAX_BYTES:
            raise OrderProjectionLimitError("order effect source payload limit")
    return cast(dict[str, Scalar], result)


def _canonical(payload: Mapping[str, Scalar]) -> bytes:
    encoded = json.dumps(
        dict(payload), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > ORDER_CANONICAL_MAX_BYTES:
        raise OrderProjectionLimitError("order effect canonical payload limit")
    return encoded


def encode_order_projection(payload: object) -> PreparedOrderProjection:
    validated = _validated(payload)
    canonical = _canonical(validated)
    if len(canonical) > ORDER_RAW_MAX_BYTES:
        raise OrderProjectionLimitError("order effect raw payload limit")
    return PreparedOrderProjection(
        MappingProxyType(validated), canonical.decode("utf-8"), len(canonical), canonical
    )


def _lexical_preflight(raw: str) -> None:
    """Bound nesting and integer conversion before the standard decoder runs.

    JSON grammar remains the decoder's job. Scan string escapes separately so
    brackets/numeric spellings inside a string never count as JSON tokens.
    """
    stack: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char == '"':
            index += 1
            while index < len(raw):
                if raw[index] == "\\":
                    if raw[index : index + 2] == "\\u":
                        digits = raw[index + 2 : index + 6]
                        if len(digits) != 4 or any(
                            c not in "0123456789abcdefABCDEF" for c in digits
                        ):
                            raise OrderProjectionIntegrityError("order projection Unicode escape")
                        codepoint = int(digits, 16)
                        if codepoint == 0 or 0xDC00 <= codepoint <= 0xDFFF:
                            raise OrderProjectionIntegrityError("order projection invalid Unicode")
                        if 0xD800 <= codepoint <= 0xDBFF:
                            low = raw[index + 8 : index + 12]
                            if (
                                raw[index + 6 : index + 8] != "\\u"
                                or len(low) != 4
                                or any(c not in "0123456789abcdefABCDEF" for c in low)
                                or not 0xDC00 <= int(low, 16) <= 0xDFFF
                            ):
                                raise OrderProjectionIntegrityError(
                                    "order projection surrogate pair"
                                )
                            index += 12
                        else:
                            index += 6
                        continue
                    index += 2
                elif raw[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            else:
                raise OrderProjectionIntegrityError("order projection unterminated string")
            continue
        if char in "[{":
            stack.append(char)
            if len(stack) > ORDER_JSON_MAX_DEPTH:
                raise OrderProjectionLimitError("order projection nesting limit")
        elif char in "]}":
            if not stack or stack.pop() != ({"]": "[", "}": "{"}[char]):
                raise OrderProjectionIntegrityError("order projection malformed nesting")
        elif char not in " \t\r\n:,":
            end = index + 1
            while end < len(raw) and raw[end] not in ' \t\r\n,:{}[]"':
                end += 1
            token = raw[index:end]
            if token not in ("null", "true", "false") and (
                len(token) > 11 or _INTEGER.fullmatch(token) is None
            ):
                raise OrderProjectionIntegrityError("order projection integer lexeme required")
            index = end
            continue
        index += 1
    if stack:
        raise OrderProjectionIntegrityError("order projection malformed nesting")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OrderProjectionIntegrityError("order projection duplicate key")
        _string(key)
        if isinstance(value, str):
            _string(value)
        result[key] = value
    return result


def decode_order_projection(raw_json: str, *, stored_octets: int) -> PreparedOrderProjection:
    if type(raw_json) is not str or type(stored_octets) is not int or stored_octets < 1:
        raise OrderProjectionIntegrityError("order projection raw text/count required")
    if stored_octets > ORDER_RAW_MAX_BYTES or len(raw_json) > ORDER_RAW_MAX_BYTES:
        raise OrderProjectionLimitError("order effect raw payload limit")
    _string(raw_json)
    raw_bytes = raw_json.encode("utf-8", errors="strict")
    if len(raw_bytes) > ORDER_RAW_MAX_BYTES:
        raise OrderProjectionLimitError("order effect raw payload limit")
    if len(raw_bytes) != stored_octets:
        raise OrderProjectionIntegrityError("order projection raw count mismatch")
    _lexical_preflight(raw_json)
    try:
        payload = json.loads(raw_json, object_pairs_hook=_pairs)
    except (ValueError, RecursionError) as error:
        raise OrderProjectionIntegrityError("order projection invalid JSON") from error
    validated = _validated(payload)
    canonical = _canonical(validated)
    return PreparedOrderProjection(MappingProxyType(validated), raw_json, stored_octets, canonical)
