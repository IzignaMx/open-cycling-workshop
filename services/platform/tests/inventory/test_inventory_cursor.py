"""Exact cross-client cursor bytes, Unicode scalar order and calendar bounds."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.inventory.cursor import (
    InventoryCursor,
    canonical_timestamp,
    decode_cursor,
    encode_cursor,
    parse_timestamp,
)
from cycling_workshop.inventory.read_repository import movement_statement
from sqlalchemy.dialects import postgresql, sqlite

CURSOR = InventoryCursor("org-a", "loc-a", "product-a", "2026-10-15T00:00:00.000001Z", "move-a")
EXACT = (
    "eyJiZWZvcmVfbW92ZW1lbnRfaWQiOiJtb3ZlLWEiLCJiZWZvcmVfb2NjdXJyZWRfYXQiOiIyMDI2LTEw"
    "LTE1VDAwOjAwOjAwLjAwMDAwMVoiLCJsb2NhdGlvbl9pZCI6ImxvYy1hIiwib3JnYW5pemF0aW9uX2lk"
    "Ijoib3JnLWEiLCJwcm9kdWN0X2lkIjoicHJvZHVjdC1hIiwidmVyc2lvbiI6MX0"
)


def decode(value: str) -> InventoryCursor:
    return decode_cursor(
        value, organization_id="org-a", location_id="loc-a", product_id="product-a"
    )


def token(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_exact_adr_cursor_bytes() -> None:
    assert encode_cursor(CURSOR) == EXACT
    assert decode(EXACT) == CURSOR


@pytest.mark.parametrize(
    "timestamp",
    [
        "0001-01-01T00:00:00.000000Z",
        "9999-12-31T23:59:59.999999Z",
        "2000-02-29T12:01:02.000000Z",
        "2026-10-15T00:00:00.000001Z",
    ],
)
def test_exact_calendar_and_microsecond_roundtrip(timestamp: str) -> None:
    assert canonical_timestamp(parse_timestamp(timestamp)) == timestamp
    assert (
        decode(encode_cursor(replace(CURSOR, before_occurred_at=timestamp))).before_occurred_at
        == timestamp
    )


@pytest.mark.parametrize(
    "value",
    [
        "0000-01-01T00:00:00.000000Z",
        "10000-01-01T00:00:00.000000Z",
        "1900-02-29T00:00:00.000000Z",
        "2026-02-30T00:00:00.000000Z",
        "2026-10-15T00:00:60.000000Z",
        "2026-10-15T24:00:00.000000Z",
        "2026-10-15T00:00:00Z",
        "2026-10-15T00:00:00.000Z",
        "2026-10-15T00:00:00.000000+00:00",
        "2026-10-15t00:00:00.000000z",
        "2026-10-15T00:00:00.0000000Z",
        "2026-10-15T00:00:00.000000Z\n",
    ],
)
def test_cursor_refuses_noncanonical_and_invalid_timestamp(value: str) -> None:
    with pytest.raises(ApiError) as failure:
        decode(encode_cursor(replace(CURSOR, before_occurred_at=value)))
    assert (failure.value.status_code, failure.value.code) == (422, "invalid_inventory_cursor")


@pytest.mark.parametrize("value", ["", "x" * 37, "nul\x00id", "\ud800", "\udfff", 1, True, None])
@pytest.mark.parametrize(
    "field", ["before_movement_id", "organization_id", "location_id", "product_id"]
)
def test_cursor_refuses_invalid_ids(field: str, value: object) -> None:
    payload = asdict(CURSOR) | {field: value}
    encoded = token(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(ApiError, match="invalid inventory cursor"):
        decode(encoded)


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None, 0, 2])
def test_version_is_exact_integer_one(version: object) -> None:
    payload = asdict(CURSOR) | {"version": version}
    with pytest.raises(ApiError):
        decode(token(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()))


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "a" * 2049,
        EXACT + "=",
        EXACT + "\n",
        EXACT + "+",
        EXACT + "/",
        "a",
        "é",
        token(b"\xff"),
        token(b"[1,2,3]"),
        token(b"null"),
        token(b"{}"),
        token(b'{"version":1,"version":1}'),
        token(b" " * 1025),
        token(b"[" * 1000 + b"]" * 1000),
    ],
)
def test_malformed_cursor_is_one_bounded_error(encoded: str) -> None:
    with pytest.raises(ApiError) as failure:
        decode(encoded)
    assert failure.value.details is None
    assert failure.value.message == "invalid inventory cursor"


def test_cursor_rejects_duplicate_field_even_if_duplicate_value_is_correct() -> None:
    raw = json.dumps(asdict(CURSOR), sort_keys=True, separators=(",", ":"))
    with pytest.raises(ApiError):
        decode(token(raw.replace('"version":1', '"version":1,"version":1').encode()))


@pytest.mark.parametrize("change", ["unknown", "missing", "spaces", "order", "escaped", "pad_bits"])
def test_cursor_requires_exact_canonical_encoding(change: str) -> None:
    payload = asdict(CURSOR)
    if change == "unknown":
        payload["extra"] = "private-canary"
    elif change == "missing":
        del payload["product_id"]
    raw = json.dumps(payload, sort_keys=change != "order", separators=(",", ":"))
    if change == "spaces":
        raw = " " + raw
    if change == "escaped":
        raw = raw.replace("move-a", "move-\\u0061")
    encoded = token(raw.encode())
    if change == "pad_bits":
        # Low trailing bits are ignored by base64 decoders, but are not canonical.
        encoded = EXACT[:-1] + "1"
    with pytest.raises(ApiError):
        decode(encoded)


@pytest.mark.parametrize("field", ["organization_id", "location_id", "product_id"])
def test_cursor_never_authorizes_another_scope(field: str) -> None:
    with pytest.raises(ApiError):
        decode(encode_cursor(replace(CURSOR, **{field: "other"})))


@pytest.mark.parametrize("identifier", ["é", "\ue000", "\U00010000", "\U0010ffff", "x" * 36])
def test_valid_scalar_ids_are_lossless(identifier: str) -> None:
    cursor = replace(CURSOR, before_movement_id=identifier)
    assert decode(encode_cursor(cursor)) == cursor


def test_sql_has_same_binary_collation_in_order_and_cursor_predicate() -> None:
    for dialect, name, collation in [
        (postgresql.dialect(), "postgresql", '"C"'),
        (sqlite.dialect(), "sqlite", '"BINARY"'),
    ]:
        query = movement_statement(
            organization_id="org-a",
            location_id="loc-a",
            product_id="product-a",
            limit=1,
            before=CURSOR,
            dialect=name,
        )
        sql = str(query.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
        assert sql.count("COLLATE " + collation) == 2
        assert "actor_id" not in sql and "note" not in sql
        assert "LIMIT 2" in sql
        assert "inventory_movements.location_id = 'loc-a'" in sql
        assert "inventory_movements.product_id = 'product-a'" in sql
        assert "inventory_movements.organization_id = 'org-a'" in sql


def test_timestamp_zero_microseconds_and_naive_sqlite_are_explicit() -> None:
    assert canonical_timestamp(datetime(1, 1, 1)) == "0001-01-01T00:00:00.000000Z"
    assert canonical_timestamp(datetime(2026, 10, 15, tzinfo=UTC)) == "2026-10-15T00:00:00.000000Z"
