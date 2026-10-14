"""Fixed v1 wire vectors and byte-level validation before Pydantic coercion."""

import asyncio
import hashlib
import json
from copy import deepcopy
from decimal import Decimal

import pytest
from cycling_workshop.sync.proof import (
    MAX_JSON_DEPTH,
    MUTATION_BODY_LIMIT,
    PROOF_PREFIX,
    InvalidCommandProof,
    MutationBodyProofMiddleware,
    canonical_command_bytes,
    command_digest,
    parse_command_proofs,
)

VECTOR = {
    "mutation_id": "01929840-0000-7000-8000-000000000001",
    "entity_type": "customer",
    "entity_id": "01929840-0000-7000-8000-000000000002",
    "operation": "create",
    "organization_id": "org-1",
    "location_id": "loc-1",
    "base_version": None,
    "occurred_at": "2026-10-14T12:30:00.123456+02:30",
    "payload": {
        "display_name": "Ána 🚲",
        "ignored": [None, True, False, -0.0, 1.25, {"é": "e\u0301", "e\u0301": "é"}],
    },
}
CANONICAL = (
    '{"base_version":null,"entity_id":"01929840-0000-7000-8000-000000000002",'
    '"entity_type":"customer","location_id":"loc-1",'
    '"mutation_id":"01929840-0000-7000-8000-000000000001",'
    '"occurred_at":"2026-10-14T10:00:00.123456Z","operation":"create",'
    '"organization_id":"org-1","payload":{"display_name":"Ána 🚲",'
    '"ignored":[null,true,false,0,1.25,{"e\u0301":"é","é":"e\u0301"}]}}'
)
# Fixed SHA-256 calculated independently over the documented prefix and literal.
GOLDEN_DIGEST = "2df7459256df801b5f752e17a6efb632daf13fd1bdd6cf7612b77a67cd432c42"


def wire(command: object = VECTOR) -> bytes:
    return json.dumps({"mutations": [command]}, ensure_ascii=False).encode()


def test_fixed_complete_command_unicode_number_timestamp_vector() -> None:
    expected = PROOF_PREFIX + CANONICAL.encode("utf-8")
    assert hashlib.sha256(expected).hexdigest() == GOLDEN_DIGEST
    assert canonical_command_bytes(VECTOR) == expected
    assert command_digest(VECTOR) == GOLDEN_DIGEST
    assert parse_command_proofs(wire(), strict=True) == (GOLDEN_DIGEST,)


def test_equivalent_key_order_escapes_numbers_and_exact_timezone_normalization() -> None:
    command = dict(reversed(list(VECTOR.items())))
    command["occurred_at"] = "2026-10-14T10:00:00.123456Z"
    raw = json.dumps({"mutations": [command]}, ensure_ascii=True).replace("-0.0", "0e0")
    raw = raw.replace("1.25", "1.2500e0")
    assert parse_command_proofs(raw.encode(), strict=True) == (GOLDEN_DIGEST,)


@pytest.mark.parametrize("value", [None, False, True, 0, 1, "1", [], {}, "é", "e\u0301"])
def test_full_payload_values_and_primitive_types_are_not_collapsed(value: object) -> None:
    command = {**VECTOR, "payload": {"ignored": value}}
    assert command_digest(command) != GOLDEN_DIGEST
    values = [None, False, True, 0, 1, "1", [], {}, "é", "e\u0301"]
    assert len(
        {command_digest({**VECTOR, "payload": {"ignored": item}}) for item in values}
    ) == len(values)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-14T10:00:00",
        "2026-10-14",
        1791972000,
        True,
        "2026-10-14T10:00:00.1234560Z",
        "2026-10-14T10:00:00.1234567Z",
        "2026-10-14 10:00:00Z",
        "2026-10-14T10:00:00-00:00",
        "2026-10-14T10:00:00+01:60",
        "2026-10-14T10:00:60Z",
        "0001-01-01T00:00:00+01:00",
        "9999-12-31T23:59:59-01:00",
    ],
)
def test_rejects_naive_coerced_finer_and_unrepresentable_timestamps(timestamp: object) -> None:
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(wire({**VECTOR, "occurred_at": timestamp}), strict=True)


@pytest.mark.parametrize(
    "literal",
    [
        "9007199254740992",
        "-9007199254740992",
        "9007199254740992.0",
        "0.10000000000000001",
        "1.0000000000000001",
        "1e-999",
        "1e999",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e20",
    ],
)
def test_rejects_numbers_that_could_be_coerced_into_another_command(literal: str) -> None:
    raw = wire({**VECTOR, "payload": {"ignored": "NUMBER"}}).replace(b'"NUMBER"', literal.encode())
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(raw, strict=True)
    assert parse_command_proofs(raw, strict=False) in {(None,), ()}


@pytest.mark.parametrize(
    "literal", ["0.1", "5e-324", "1.2345678901234567", "9007199254740991", "-0", "1e0"]
)
def test_explicitly_supported_binary64_decimal_subset(literal: str) -> None:
    raw = wire({**VECTOR, "payload": {"ignored": "NUMBER"}}).replace(b'"NUMBER"', literal.encode())
    expected = command_digest({**VECTOR, "payload": {"ignored": Decimal(literal)}})
    assert parse_command_proofs(raw, strict=True) == (expected,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_version", "1"),
        ("base_version", True),
        ("base_version", 1.0),
        ("base_version", -1),
        ("base_version", 2**53),
        ("location_id", 1),
        ("organization_id", " org-1"),
        ("entity_id", "x"),
        ("payload", []),
    ],
)
def test_rejects_coercible_envelope_fields(field: str, value: object) -> None:
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(wire({**VECTOR, field: value}), strict=True)


@pytest.mark.parametrize(
    "kind", ["root", "envelope", "payload", "duplicate", "surrogate", "utf8", "missing"]
)
def test_rejects_unknown_fields_duplicates_and_encoding_ambiguity(kind: str) -> None:
    command = deepcopy(VECTOR)
    if kind == "root":
        raw = json.dumps({"mutations": [command], "ignored": True}).encode()
    elif kind == "envelope":
        raw = wire({**command, "ignored": True})
    elif kind == "payload":
        raw = wire().replace(b'"display_name":', b'"same": 1, "same": 2, "display_name":')
    elif kind == "duplicate":
        raw = wire().replace(b'"base_version": null', b'"base_version": 0, "base_version": null')
    elif kind == "surrogate":
        raw = wire({**command, "payload": {"ignored": "SURROGATE"}}).replace(
            b"SURROGATE", b"\\ud800"
        )
    elif kind == "utf8":
        raw = wire() + b"\xff"
    else:
        del command["base_version"]
        raw = wire(command)
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(raw, strict=True)
    assert parse_command_proofs(raw, strict=False) in {(None,), ()}


def test_legacy_proof_is_positionally_preserved_without_accepting_coercion() -> None:
    invalid = {**VECTOR, "base_version": "1"}
    raw = json.dumps({"mutations": [VECTOR, invalid, VECTOR]}).encode()
    assert parse_command_proofs(raw, strict=False) == (GOLDEN_DIGEST, None, GOLDEN_DIGEST)
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(raw, strict=True)


def test_depth_and_bytes_are_bounded() -> None:
    value: object = None
    for _ in range(MAX_JSON_DEPTH + 1):
        value = [value]
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(wire({**VECTOR, "payload": {"ignored": value}}), strict=True)
    with pytest.raises(InvalidCommandProof):
        parse_command_proofs(b" " * (MUTATION_BODY_LIMIT + 1), strict=False)


def _middleware_call(
    chunks: list[bytes], *, protocol: bytes = b"1"
) -> tuple[list[dict], list[dict], int]:
    received = 0
    sent: list[dict] = []
    passed: list[dict] = []
    scope = {
        "type": "http",
        "path": "/api/v1/sync/mutations",
        "method": "POST",
        "headers": [(b"x-ocwp-write-protocol", protocol)],
    }

    async def receive() -> dict:
        nonlocal received
        part = chunks[received]
        received += 1
        return {"type": "http.request", "body": part, "more_body": received < len(chunks)}

    async def send(message: dict) -> None:
        sent.append(message)

    async def downstream(scope: dict, receive, send) -> None:
        passed.append({"state": scope["state"], "request": await receive()})

    asyncio.run(MutationBodyProofMiddleware(downstream)(scope, receive, send))
    return sent, passed, received


def test_streaming_limit_stops_before_parser_downstream_or_remaining_chunks() -> None:
    sent, passed, received = _middleware_call([b" " * MUTATION_BODY_LIMIT, b"!", wire()])
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["error"]["code"] == "request_too_large"
    assert passed == [] and received == 2


def test_streamed_body_proofs_precede_downstream_and_body_is_replayed_exactly() -> None:
    raw = wire()
    sent, passed, _ = _middleware_call([raw[:5], b"", raw[5:]])
    assert sent == []
    assert passed == [
        {
            "state": {"sync_command_proofs": (GOLDEN_DIGEST,)},
            "request": {"type": "http.request", "body": raw, "more_body": False},
        }
    ]


def test_strict_invalid_body_is_422_but_legacy_invalid_proof_is_not_rewritten() -> None:
    raw = wire({**VECTOR, "base_version": "1"})
    sent, passed, _ = _middleware_call([raw])
    assert sent[0]["status"] == 422 and passed == []
    sent, passed, _ = _middleware_call([raw], protocol=b"0")
    assert sent == []
    assert passed[0]["state"]["sync_command_proofs"] == (None,)
    assert passed[0]["request"]["body"] == raw


def test_second_fixed_control_characters_array_order_vector() -> None:
    command = {
        "mutation_id": "01929840-0000-7000-8000-000000000001",
        "entity_type": "customer",
        "entity_id": "01929840-0000-7000-8000-000000000002",
        "operation": "update",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": 0,
        "occurred_at": "2026-10-14T10:00:00.000000Z",
        "payload": {"a": [1, 2, 3], "z": "\n\t\x00"},
    }
    canonical = (
        '{"base_version":0,"entity_id":"01929840-0000-7000-8000-000000000002","entity_typ'
        'e":"customer","location_id":"loc-1","mutation_id":"01929840-0000-7000-8000-00000'
        '0000001","occurred_at":"2026-10-14T10:00:00.000000Z","operation":"update","organ'
        'ization_id":"org-1","payload":{"a":[1,2,3],"z":"\\n\\t\\u0000"}}'
    )
    assert canonical_command_bytes(command) == PROOF_PREFIX + canonical.encode()
    assert (
        command_digest(command)
        == "bda4c6ebe1a5969752a5e0257a4a517900a4113bb77f0b86fc240add670b2d3e"
    )


def test_key_order_is_unicode_codepoint_order_not_utf16_or_normalization() -> None:
    command = {
        **VECTOR,
        "payload": {"🚲": "astral", "\ue000": "private", "é": "nfc", "e\u0301": "nfd"},
    }
    canonical = canonical_command_bytes(command).decode()
    assert (
        canonical.index('"é":')
        < canonical.index('"é":')
        < canonical.index('"\ue000":')
        < canonical.index('"🚲":')
    )
    assert command_digest({**VECTOR, "payload": {"values": [1, 2]}}) != command_digest(
        {**VECTOR, "payload": {"values": [2, 1]}}
    )
