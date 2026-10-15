"""Inactive, pure quote request decoding. No authority or HTTP integration.

Feed actual untrusted body chunks, not Content-Length. A future HTTP wrapper must
reject Content-Encoding before reading, bound its async stream before buffering,
map these fixed errors to private responses and bind decision action to its route.
Decoded values are input only: locked scope/customer/head checks, calculated-money
bounds, fresh authority and atomic effects remain application responsibilities.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, NoReturn

from cycling_workshop.quotes.decisions import DecisionEvidence
from cycling_workshop.quotes.domain import LaborLine, PartLine, QuoteLine
from cycling_workshop.quotes.storage import (
    MAX_SAFE_INTEGER,
    Document,
    JsonValue,
    _array,
    _id,
    _ids,
    _integer,
    _json,
    _mapping,
    _optional_text,
    _string,
    decode_lines,
)

MAX_REQUEST_BYTES = 128 * 1024
MAX_JSON_DEPTH = 12
_TIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)
type DecisionAction = Literal["authorize", "reject", "authorize-partial"]


class QuoteRequestError(ValueError):
    """A fixed code only; never includes a field name, input or evidence."""


@dataclass(frozen=True, slots=True)
class CreateQuoteRequest:
    operation_id: str
    quote_id: str
    expected_order_version: int
    currency: str
    lines: tuple[QuoteLine, ...]


@dataclass(frozen=True, slots=True)
class ReviseQuoteRequest:
    operation_id: str
    quote_id: str
    expected_order_version: int
    lineage_id: str
    expected_head_id: str
    expected_head_version: int
    expected_decision_sequence: int
    lines: tuple[QuoteLine, ...]


@dataclass(frozen=True, slots=True)
class InitialDecisionRequest:
    decision_id: str
    expected_order_version: int
    lineage_id: str
    expected_head_id: str
    expected_head_version: int
    expected_decision_sequence: int
    evidence: DecisionEvidence
    approved_line_ids: tuple[str, ...]
    action: DecisionAction


def _invalid(*_: object) -> NoReturn:
    raise QuoteRequestError("invalid_request")


def _number(lexeme: str) -> int:
    # Bound lexical length/value BEFORE int(); no arbitrary-size construction.
    digits = lexeme.removeprefix("-")
    maximum = str(MAX_SAFE_INTEGER)
    if len(digits) > len(maximum) or (len(digits) == len(maximum) and digits > maximum):
        _invalid()
    return int(lexeme)


def _object(pairs: list[tuple[str, JsonValue]]) -> Document:
    result: Document = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _depth(text: str) -> None:
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _invalid()
        elif char in "]}":
            depth -= 1
    # The JSON parser, not this resource pre-scan, validates balanced syntax.


def decode_request_document(
    chunks: Iterable[bytes], *, content_encoding: str | None = None
) -> Document:
    """Bound actual bytes before joining/decoding. No headers are read here.

    Absence or identity are the only supported encodings. Iterator I/O failures
    propagate; the eventual HTTP adapter owns disconnect/cancellation handling.
    """
    if content_encoding is not None and content_encoding.strip().lower() != "identity":
        raise QuoteRequestError("unsupported_encoding")
    body = bytearray()
    for chunk in chunks:
        if type(chunk) is not bytes:
            _invalid()
        if len(chunk) > MAX_REQUEST_BYTES - len(body):
            raise QuoteRequestError("too_large")
        body.extend(chunk)
    try:
        text = body.decode("utf-8", errors="strict")
        _depth(text)
        document = _json(
            json.loads(
                text,
                parse_int=_number,
                parse_float=_invalid,
                parse_constant=_invalid,
                object_pairs_hook=_object,
            )
        )
        if type(document) is not dict:
            _invalid()
        return document
    except (ValueError, UnicodeError, RecursionError):
        raise QuoteRequestError("invalid_request") from None


def _lines(value: JsonValue) -> tuple[QuoteLine, ...]:
    # Validate raw bounds before domain whitespace/target-order normalization.
    normalized: list[JsonValue] = []
    for item in _array(value):
        if type(item) is not dict:
            _invalid()
        row = dict(item)
        row["description"] = " ".join(_string(row.get("description"), 500).split())
        for field in ("base_line_ids", "scope_line_ids"):
            if field in row:
                row[field] = list(sorted(_ids(row[field])))
        normalized.append(row)
    lines = decode_lines(normalized)
    if not any(isinstance(line, (LaborLine, PartLine)) for line in lines):
        _invalid()
    if len({line.line_id for line in lines}) != len(lines):
        _invalid()
    return lines


def decode_quote_request(
    chunks: Iterable[bytes], *, content_encoding: str | None = None
) -> CreateQuoteRequest | ReviseQuoteRequest:
    row = decode_request_document(chunks, content_encoding=content_encoding)
    try:
        common = "kind operation_id quote_id expected_order_version lines"
        operation_id = _id(row.get("operation_id"), generated=True)
        quote_id = _id(row.get("quote_id"), generated=True)
        order_version = _integer(row.get("expected_order_version"), 1)
        lines = _lines(row.get("lines"))
        if row.get("kind") == "create":
            _mapping(row, common + " currency")
            currency = _string(row["currency"], 3)
            if len(currency) != 3 or not all("A" <= char <= "Z" for char in currency):
                _invalid()
            return CreateQuoteRequest(operation_id, quote_id, order_version, currency, lines)
        if row.get("kind") == "revise":
            _mapping(
                row,
                common + " lineage_id expected_head_id expected_head_version "
                "expected_decision_sequence",
            )
            lineage_id = _id(row["lineage_id"], generated=True)
            head_id = _id(row["expected_head_id"], generated=True)
            if quote_id in (lineage_id, head_id):
                _invalid()
            return ReviseQuoteRequest(
                operation_id,
                quote_id,
                order_version,
                lineage_id,
                head_id,
                _integer(row["expected_head_version"], 1),
                _integer(row["expected_decision_sequence"]),
                lines,
            )
        _invalid()
    except (ValueError, UnicodeError):
        raise QuoteRequestError("invalid_request") from None


def _evidence(value: JsonValue) -> DecisionEvidence:
    row = _mapping(value, "party_kind party_id channel decided_at source_reference note")
    if row["party_kind"] != "customer" or row["channel"] not in (
        "in_person",
        "phone",
        "email",
        "messaging",
        "written",
    ):
        _invalid()
    timestamp = row["decided_at"]
    if type(timestamp) is not str or not _TIME.fullmatch(timestamp) or timestamp.endswith("-00:00"):
        _invalid()
    instant = datetime.fromisoformat(timestamp.upper()).astimezone(UTC)
    return DecisionEvidence(
        "customer",
        _id(row["party_id"]),
        _string(row["channel"], 20),
        instant,
        _optional_text(row["source_reference"], 200),
        _optional_text(row["note"], 2000),
    )


def decode_initial_decision_request(
    chunks: Iterable[bytes], *, action: DecisionAction, content_encoding: str | None = None
) -> InitialDecisionRequest:
    """Action is supplied separately; this function does not authenticate its caller.

    Authorize derives all charge selections from the locked revision later;
    reject has none. Only authorize-partial admits an explicit whole-line list.
    Neither membership nor proper-subset status can be proven without that revision.
    """
    row = decode_request_document(chunks, content_encoding=content_encoding)
    try:
        if action not in ("authorize", "reject", "authorize-partial"):
            _invalid()
        keys = (
            "decision_id expected_order_version lineage_id expected_head_id "
            "expected_head_version expected_decision_sequence evidence"
        )
        if action == "authorize-partial":
            keys += " approved_line_ids"
        _mapping(row, keys)
        selection = _ids(row["approved_line_ids"]) if action == "authorize-partial" else ()
        if action == "authorize-partial" and (
            not selection or len(selection) != len(set(selection))
        ):
            _invalid()
        return InitialDecisionRequest(
            _id(row["decision_id"], generated=True),
            _integer(row["expected_order_version"], 1),
            _id(row["lineage_id"], generated=True),
            _id(row["expected_head_id"], generated=True),
            _integer(row["expected_head_version"], 1),
            _integer(row["expected_decision_sequence"]),
            _evidence(row["evidence"]),
            tuple(sorted(selection)),
            action,
        )
    except (ValueError, UnicodeError, OverflowError):
        raise QuoteRequestError("invalid_request") from None
