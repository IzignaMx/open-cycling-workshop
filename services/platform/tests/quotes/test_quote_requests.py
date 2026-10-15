"""Pure request boundary tests; no HTTP/authority/persistence qualification."""

import json

import pytest
from cycling_workshop.quotes.requests import (
    MAX_REQUEST_BYTES,
    QuoteRequestError,
    decode_quote_request,
)

ID = "019a85e2-0000-7000-8000-000000000001"
LINE = "019a85e2-0000-7000-8000-000000000002"


def create():
    return {
        "kind": "create",
        "operation_id": ID,
        "quote_id": ID,
        "expected_order_version": 1,
        "currency": "MXN",
        "lines": [
            {
                "kind": "labor",
                "line_id": LINE,
                "description": "Tune up",
                "minutes": 60,
                "hourly_rate_minor": 100,
            }
        ],
    }


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


def test_create_decodes_closed_typed_request():
    result = decode_quote_request([raw(create())])
    assert result.quote_id == ID
    assert result.lines[0].minutes == 60


def test_actual_chunk_bytes_are_bounded_before_json_parsing():
    consumed = []

    def chunks():
        yield b" " * MAX_REQUEST_BYTES
        consumed.append(True)
        yield b"x"
        raise AssertionError("must stop consuming after the byte limit")

    with pytest.raises(QuoteRequestError, match="too_large"):
        decode_quote_request(chunks())
    assert consumed == [True]


@pytest.mark.parametrize(
    "extra",
    [
        "totals",
        "actor_id",
        "organization_id",
        "location_id",
        "order_id",
        "created_at",
        "expected_head_id",
        "enrolled",
    ],
)
def test_create_rejects_unowned_or_unknown_fields_without_echo(extra):
    value = create()
    value[extra] = "private evidence secret"
    with pytest.raises(QuoteRequestError) as error:
        decode_quote_request([raw(value)])
    assert str(error.value) == "invalid_request"
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "body",
    [
        b'{"x":1,"x":2}',
        b'{"kind":1,"\\u006bind":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b'{"x":1.0}',
        b'{"x":1e0}',
        b'{"x":9007199254740992}',
        b'{"x":-9007199254740992}',
        b'{"x":' + b"9" * 5000 + b"}",
        b'{"x":"\\ud800"}',
        b'{"\\udfff":1}',
        b'{"x":"\\u0000"}',
        b'{"\\u0000":1}',
        b'{"x":"\xff"}',
        b"\xef\xbb\xbf{}",
        b"{}{}",
        b"[]",
        b"null",
        b"",
    ],
)
def test_rejects_unsafe_json_without_echo(body):
    from cycling_workshop.quotes.requests import decode_request_document

    with pytest.raises(QuoteRequestError, match=r"^invalid_request$"):
        decode_request_document([body])


def test_byte_limit_exact_boundary_and_multibyte_chunk_split():
    from cycling_workshop.quotes.requests import decode_request_document

    assert decode_request_document([b"{}" + b" " * (MAX_REQUEST_BYTES - 2)]) == {}
    body = raw({"text": "🛠"})
    assert decode_request_document([body[:12], body[12:]]) == {"text": "🛠"}
    assert decode_request_document([b"", b"{}", b""]) == {}


def test_depth_precheck_handles_quotes_escapes_and_brackets():
    from cycling_workshop.quotes.requests import decode_request_document

    value = {"x": '\\"[{'}
    for _ in range(11):
        value = {"x": value}
    assert decode_request_document([raw(value)]) == value
    with pytest.raises(QuoteRequestError):
        decode_request_document([raw({"x": value})])
    with pytest.raises(QuoteRequestError):
        decode_request_document([b'{"x":' + b"[" * 1000 + b"0" + b"]" * 1000 + b"}"])


@pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "identity,gzip", ""])
def test_rejects_compressed_before_consuming_body(encoding):
    def chunks():
        raise AssertionError("must reject encoding before body")
        yield b""

    with pytest.raises(QuoteRequestError, match=r"^unsupported_encoding$"):
        decode_quote_request(chunks(), content_encoding=encoding)


def test_identity_encoding_and_safe_integer_extremes():
    from cycling_workshop.quotes.requests import decode_request_document

    assert decode_quote_request([raw(create())], content_encoding=" Identity ").currency == "MXN"
    maximum = 9_007_199_254_740_991
    assert decode_request_document([raw({"x": maximum, "y": -maximum})]) == {
        "x": maximum,
        "y": -maximum,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("minutes", True),
        ("minutes", 0),
        ("minutes", 1_000_001),
        ("minutes", "60"),
        ("minutes", 60.0),
        ("hourly_rate_minor", -1),
        ("hourly_rate_minor", True),
        ("line_id", "legacy"),
        ("line_id", "019a85e2-0000-4000-8000-000000000002"),
        ("description", " " * 501 + "x"),
        ("description", "x" * 501),
        ("description", ""),
        ("description", "\x00"),
        ("extra", "secret"),
    ],
)
def test_line_input_bounds(field, value):
    body = create()
    body["lines"][0][field] = value
    with pytest.raises(QuoteRequestError):
        decode_quote_request([raw(body)])


def test_raw_description_is_normalized_without_truncation():
    body = create()
    body["lines"][0]["description"] = "  Tune\n up  "
    assert decode_quote_request([raw(body)]).lines[0].description == "Tune up"
    body["lines"][0]["description"] = "🛠" * 500
    assert len(decode_quote_request([raw(body)]).lines[0].description) == 500


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_order_version", 0),
        ("expected_order_version", True),
        ("currency", "mxn"),
        ("currency", "US"),
        ("currency", "ÜSD"),
        ("operation_id", ID.upper()),
        ("quote_id", "legacy"),
        ("lines", []),
        ("kind", "other"),
    ],
)
def test_create_field_bounds(field, value):
    body = create()
    body[field] = value
    with pytest.raises(QuoteRequestError):
        decode_quote_request([raw(body)])


def revise():
    body = create()
    del body["currency"]
    body.update(
        kind="revise",
        quote_id="019a85e2-0000-7000-8000-000000000003",
        lineage_id=ID,
        expected_head_id=ID,
        expected_head_version=1,
        expected_decision_sequence=0,
    )
    return body


def test_revise_closed_contract_and_presentation_order():
    from cycling_workshop.quotes.requests import ReviseQuoteRequest

    assert isinstance(decode_quote_request([raw(revise())]), ReviseQuoteRequest)
    for field, value in [
        ("currency", "MXN"),
        ("quote_id", ID),
        ("expected_head_version", 0),
        ("expected_decision_sequence", -1),
    ]:
        body = revise()
        body[field] = value
        with pytest.raises(QuoteRequestError):
            decode_quote_request([raw(body)])


def test_one_hundred_lines_accepted_next_refused_and_duplicates_refused():
    body = create()
    line = body["lines"][0]
    body["lines"] = [dict(line, line_id=f"019a85e2-0000-7000-8000-{i:012x}") for i in range(100)]
    assert len(decode_quote_request([raw(body)]).lines) == 100
    body["lines"].append(dict(line))
    with pytest.raises(QuoteRequestError):
        decode_quote_request([raw(body)])
    body["lines"] = [line, line]
    with pytest.raises(QuoteRequestError):
        decode_quote_request([raw(body)])


def test_all_line_kinds_reference_normalization_and_edge_budget():
    body = create()
    labor = body["lines"][0]
    ids = [f"019a85e2-0000-7000-8000-{i:012x}" for i in range(50)]
    body["lines"] = [dict(labor, line_id=identifier) for identifier in ids]
    for i in range(20):
        body["lines"].append(
            {
                "kind": "tax",
                "line_id": f"019a85e2-0000-7000-8000-{i + 100:012x}",
                "description": "Tax",
                "rate_bps": 10000,
                "base_line_ids": ids[::-1],
            }
        )
    result = decode_quote_request([raw(body)])
    assert result.lines[-1].base_line_ids == tuple(ids)
    body["lines"].append(
        {
            "kind": "discount",
            "line_id": "019a85e2-0000-7000-8000-000000000999",
            "description": "Discount",
            "amount_minor": 1,
            "scope_line_ids": [ids[0]],
        }
    )
    with pytest.raises(QuoteRequestError):
        decode_quote_request([raw(body)])
    body["lines"] = [
        labor,
        {
            "kind": "part",
            "line_id": ids[0],
            "description": "Part",
            "product_id": "legacy-product",
            "quantity": 1_000_000,
            "unit_price_minor": 0,
        },
    ]
    assert len(decode_quote_request([raw(body)]).lines) == 2


def decision():
    return {
        "decision_id": ID,
        "expected_order_version": 1,
        "lineage_id": ID,
        "expected_head_id": ID,
        "expected_head_version": 1,
        "expected_decision_sequence": 0,
        "evidence": {
            "party_kind": "customer",
            "party_id": "legacy-customer",
            "channel": "phone",
            "decided_at": "2026-10-15T12:00:00.123456-06:00",
            "source_reference": None,
            "note": None,
        },
    }


def test_initial_decision_utc_normalization_and_route_selection():
    from datetime import UTC, datetime

    from cycling_workshop.quotes.requests import decode_initial_decision_request

    for action in ("authorize", "reject"):
        result = decode_initial_decision_request([raw(decision())], action=action)
        assert result.evidence.decided_at == datetime(2026, 10, 15, 18, 0, 0, 123456, tzinfo=UTC)
        assert result.approved_line_ids == ()
        assert result.action == action
    body = decision()
    body["approved_line_ids"] = [LINE, ID]
    assert decode_initial_decision_request(
        [raw(body)], action="authorize-partial"
    ).approved_line_ids == (ID, LINE)
    for selection in ([], [LINE, LINE], ["legacy"], [LINE] * 101):
        body["approved_line_ids"] = selection
        with pytest.raises(QuoteRequestError):
            decode_initial_decision_request([raw(body)], action="authorize-partial")


@pytest.mark.parametrize(
    "field",
    [
        "outcome",
        "action",
        "mode",
        "quote_id",
        "recorded_by_actor_id",
        "recorded_at",
        "pricing",
        "reason",
        "supersedes_entry_id",
        "approved_line_ids",
    ],
)
def test_decision_body_cannot_supply_route_or_server_fields(field):
    from cycling_workshop.quotes.requests import decode_initial_decision_request

    body = decision()
    body[field] = "secret"
    with pytest.raises(QuoteRequestError, match=r"^invalid_request$"):
        decode_initial_decision_request([raw(body)], action="authorize")


@pytest.mark.parametrize(
    "field,value",
    [
        ("party_kind", "representative"),
        ("channel", "portal"),
        ("party_id", "x" * 37),
        ("note", "x" * 2001),
        ("note", ""),
        ("source_reference", "x" * 201),
        ("decided_at", "2026-10-15T12:00:00.1234567Z"),
        ("decided_at", "2026-10-15T12:00:00"),
        ("decided_at", "2026-10-15 12:00:00Z"),
        ("decided_at", "2026-10-15T12:00:00+24:00"),
        ("decided_at", "2026-10-15T12:00:00-00:00"),
        ("decided_at", "0001-01-01T00:00:00+23:59"),
        ("decided_at", "2026-02-30T12:00:00Z"),
        ("decided_at", "2026-10-15T12:00:60Z"),
        ("secret_field", "private"),
    ],
)
def test_evidence_rejection_is_bounded(field, value):
    from cycling_workshop.quotes.requests import decode_initial_decision_request

    body = decision()
    body["evidence"][field] = value
    with pytest.raises(QuoteRequestError, match=r"^invalid_request$"):
        decode_initial_decision_request([raw(body)], action="reject")


def test_evidence_text_boundaries_and_channels():
    from cycling_workshop.quotes.requests import decode_initial_decision_request

    body = decision()
    body["evidence"].update(note="🛠" * 2000, source_reference="x" * 200)
    for channel in ("in_person", "phone", "email", "messaging", "written"):
        body["evidence"]["channel"] = channel
        assert (
            decode_initial_decision_request([raw(body)], action="reject").evidence.channel
            == channel
        )


def test_byte_and_depth_refusal_precede_parser(monkeypatch):
    from cycling_workshop.quotes import requests

    def fail_if_parsed(*args, **kwargs):
        raise AssertionError("parser must not run before resource admission")

    monkeypatch.setattr(requests.json, "loads", fail_if_parsed)
    with pytest.raises(QuoteRequestError, match=r"^too_large$"):
        requests.decode_request_document([b"{}", b" " * (MAX_REQUEST_BYTES - 1)])
    with pytest.raises(QuoteRequestError, match=r"^invalid_request$"):
        requests.decode_request_document([b'{"x":' + b"[" * 12 + b"0" + b"]" * 12 + b"}"])


def test_shape_decoding_is_not_calculated_money_admission():
    body = create()
    body["lines"][0].update(minutes=1_000_000, hourly_rate_minor=9_007_199_254_740_991)
    # Each input is bounded; the later domain/storage boundary must reject the
    # calculated gross amount. No scoped Quote or durable command is built here.
    assert decode_quote_request([raw(body)]).lines[0].minutes == 1_000_000


def test_negative_zero_is_an_exact_zero_integer_not_a_positive_version():
    from cycling_workshop.quotes.requests import decode_request_document

    assert decode_request_document([b'{"value":-0}']) == {"value": 0}
    body = raw(create()).replace(b'"expected_order_version": 1', b'"expected_order_version": -0')
    with pytest.raises(QuoteRequestError):
        decode_quote_request([body])
