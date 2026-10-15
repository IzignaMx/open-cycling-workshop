"""Canonical, scope-bound positions for the connected inventory read only."""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from cycling_workshop.api.errors import ApiError

_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_ENCODED = re.compile(r"[A-Za-z0-9_-]{1,2048}")
_KEYS = {
    "version",
    "organization_id",
    "location_id",
    "product_id",
    "before_occurred_at",
    "before_movement_id",
}


def valid_read_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 36
        and "\x00" not in value
        and not any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    )


def canonical_timestamp(value: datetime) -> str:
    # SQLite returns naive DateTime values; persisted inventory times are UTC.
    utc = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise ValueError("invalid timestamp")
    parsed = datetime.fromisoformat(value)
    if canonical_timestamp(parsed) != value:
        raise ValueError("invalid timestamp")
    return parsed


@dataclass(frozen=True, slots=True)
class InventoryCursor:
    organization_id: str
    location_id: str
    product_id: str
    before_occurred_at: str
    before_movement_id: str
    version: int = 1


def encode_cursor(cursor: InventoryCursor) -> str:
    payload = json.dumps(asdict(cursor), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def invalid_cursor() -> ApiError:
    return ApiError(422, "invalid_inventory_cursor", "invalid inventory cursor")


def decode_cursor(
    encoded: str, *, organization_id: str, location_id: str, product_id: str
) -> InventoryCursor:
    try:
        if _ENCODED.fullmatch(encoded) is None:
            raise ValueError("invalid encoding")
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        if len(raw) > 1024:
            raise ValueError("oversized cursor")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(payload, dict) or set(payload) != _KEYS:
            raise ValueError("invalid fields")
        if type(payload["version"]) is not int or payload["version"] != 1:
            raise ValueError("invalid version")
        for key in ("organization_id", "location_id", "product_id", "before_movement_id"):
            if not valid_read_id(payload[key]):
                raise ValueError("invalid identifier")
        parse_timestamp(payload["before_occurred_at"])
        cursor = InventoryCursor(**payload)
        if (
            cursor.organization_id != organization_id
            or cursor.location_id != location_id
            or cursor.product_id != product_id
            or encode_cursor(cursor) != encoded
        ):
            raise ValueError("noncanonical or mismatched cursor")
        return cursor
    except (ValueError, TypeError, OverflowError, UnicodeError, binascii.Error, RecursionError):
        raise invalid_cursor() from None
