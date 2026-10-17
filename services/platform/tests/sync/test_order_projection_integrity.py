"""Finite source-prepared cases; not executed locally (containment unavailable)."""

import json

import pytest
from cycling_workshop.sync import order_projection_integrity as codec


def projection():
    return dict(
        order_id="order",
        customer_id="customer",
        bicycle_id=None,
        organization_id="org",
        location_id="location",
        state="AUTHORIZED",
        reported_problem='  é🚲\\"\n  ',
        intake_condition=None,
        accessories="",
        priority="normal",
        diagnosis="preserve  spaces",
        created_at="2026-10-17T00:00:00+00:00",
        updated_at="2026-10-17T00:00:00.000001+00:00",
        version=2,
    )


def decode(raw):
    return codec.decode_order_projection(raw, stored_octets=len(raw.encode("utf-8")))


def test_roundtrip_preserves_strings_and_freezes_snapshot():
    value = projection()
    prepared = codec.encode_order_projection(value)
    value["diagnosis"] = "changed"
    assert prepared.payload["diagnosis"] == "preserve  spaces"
    with pytest.raises(TypeError):
        prepared.payload["diagnosis"] = "changed"
    assert decode(prepared.raw_json) == prepared
    raw = json.dumps(projection(), ensure_ascii=True, indent=2)
    decoded = decode(raw)
    assert decoded.raw_json == raw
    assert decoded.canonical_utf8 == prepared.canonical_utf8


@pytest.mark.parametrize("key", list(projection()))
def test_every_field_is_required(key):
    value = projection()
    del value[key]
    with pytest.raises(codec.OrderProjectionIntegrityError):
        codec.encode_order_projection(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("order_id", "a b"),
        ("customer_id", ""),
        ("bicycle_id", 1),
        ("organization_id", "a" * 37),
        ("location_id", "\t"),
        ("state", "unknown"),
        ("reported_problem", None),
        ("priority", False),
        ("intake_condition", []),
        ("accessories", {}),
        ("diagnosis", 3),
        ("created_at", "2026-10-17T00:00:00Z"),
        ("updated_at", "2026-10-17T00:00:00.0+00:00"),
        ("version", True),
        ("version", 0),
        ("version", 2147483648),
        ("diagnosis", "\x00"),
        ("diagnosis", "\ud800"),
    ],
)
def test_full_field_domains(field, value):
    payload = projection() | {field: value}
    with pytest.raises(codec.OrderProjectionIntegrityError):
        codec.encode_order_projection(payload)
    raw = json.dumps(payload)
    with pytest.raises(codec.OrderProjectionIntegrityError):
        decode(raw)


@pytest.mark.parametrize("token", ["2.0", "2e0", "NaN", "Infinity", "-Infinity", "9" * 200])
def test_numeric_lexemes_rejected_before_decode(token):
    raw = json.dumps(projection()).replace('"version": 2', '"version": ' + token)
    with pytest.raises(codec.OrderProjectionIntegrityError):
        decode(raw)


@pytest.mark.parametrize(
    "raw",
    [
        '{"version":1,"version":2}',
        '{"x":"\\u0000"}',
        '{"x":"\\ud800"}',
        "[" * 13 + "0" + "]" * 13,
        '{"x": [1,2}',
        '{"x": tru}',
    ],
)
def test_duplicate_unicode_depth_and_malformed_rejection(raw):
    with pytest.raises(codec.OrderProjectionIntegrityError):
        decode(raw)


def test_preflight_precedes_json_loads(monkeypatch):
    def unsafe(*args, **kwargs):
        pytest.fail("unsafe decoder reached")
    monkeypatch.setattr(codec.json, "loads", unsafe)
    for raw in ('[' * 13 + '0' + ']' * 13, '{"x":' + '9' * 200 + '}', '{"x":2e0}'):
        with pytest.raises(codec.OrderProjectionIntegrityError):
            decode(raw)


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize(
    "limit_name", ["ORDER_SOURCE_MAX_BYTES", "ORDER_CANONICAL_MAX_BYTES", "ORDER_RAW_MAX_BYTES"]
)
def test_each_byte_boundary(monkeypatch, offset, limit_name):
    payload = projection()
    prepared = codec.encode_order_projection(payload)
    sizes = {
        "ORDER_SOURCE_MAX_BYTES": sum(len(payload[key].encode("utf-8")) for key in
            ("reported_problem", "intake_condition", "accessories", "priority", "diagnosis")
            if payload[key] is not None),
        "ORDER_CANONICAL_MAX_BYTES": len(prepared.canonical_utf8),
        "ORDER_RAW_MAX_BYTES": prepared.raw_octets,
    }
    monkeypatch.setattr(codec, limit_name, sizes[limit_name] + offset)
    if offset < 0:
        with pytest.raises(codec.OrderProjectionLimitError):
            codec.encode_order_projection(payload)
    else:
        assert codec.encode_order_projection(payload).payload == payload


def test_stored_count_exact_and_raw_budget(monkeypatch):
    prepared = codec.encode_order_projection(projection())
    for count in (True, 0, prepared.raw_octets - 1, prepared.raw_octets + 1):
        with pytest.raises(codec.OrderProjectionIntegrityError):
            codec.decode_order_projection(prepared.raw_json, stored_octets=count)
    monkeypatch.setattr(codec, "ORDER_RAW_MAX_BYTES", prepared.raw_octets - 1)
    with pytest.raises(codec.OrderProjectionLimitError):
        decode(prepared.raw_json)


def test_extra_field_and_maximum_version():
    with pytest.raises(codec.OrderProjectionIntegrityError):
        codec.encode_order_projection(projection() | {"extra": None})
    assert codec.encode_order_projection(projection() | {"version": 2147483647})


def test_duplicate_key_in_otherwise_valid_projection():
    raw = json.dumps(projection())
    duplicate = raw[:-1] + ', "version": 2}'
    with pytest.raises(codec.OrderProjectionIntegrityError, match="invalid JSON"):
        decode(duplicate)


def test_escaped_strings_are_not_number_or_depth_tokens():
    payload = projection() | {"diagnosis": '[' * 40 + '9' * 200 + '2e0\\"' + ']' * 40}
    prepared = codec.encode_order_projection(payload)
    assert decode(prepared.raw_json).payload == payload
    assert decode(json.dumps(payload, ensure_ascii=True)).payload == payload


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_raw_decode_exact_byte_boundary(monkeypatch, offset):
    prepared = codec.encode_order_projection(projection())
    limit = prepared.raw_octets + 2
    monkeypatch.setattr(codec, "ORDER_RAW_MAX_BYTES", limit)
    raw = prepared.raw_json + " " * (2 + offset)
    if offset > 0:
        with pytest.raises(codec.OrderProjectionLimitError):
            decode(raw)
    else:
        assert decode(raw).canonical_utf8 == prepared.canonical_utf8


def test_preflight_unicode_rejection_precedes_decoder(monkeypatch):
    def unsafe(*args, **kwargs):
        pytest.fail("unsafe decoder reached")
    monkeypatch.setattr(codec.json, "loads", unsafe)
    for raw in ('{"x":"\\u0000"}', '{"x":"\\ud800"}', '{"x":"\\udfff"}'):
        with pytest.raises(codec.OrderProjectionIntegrityError):
            decode(raw)
