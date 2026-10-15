"""Version-one private persistence codecs; not HTTP DTOs or a grant boundary.

The pure domain remains arbitrary precision. These codecs bound stored snapshots,
retain exact canonical evidence and refuse corrupt or noncanonical reconstruction.
"""

from __future__ import annotations

import json
import re
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from uuid import UUID

from cycling_workshop.quotes.decisions import (
    ApprovedCharge,
    ApprovedDiscount,
    ApprovedPricing,
    ApprovedTax,
    DecisionCommand,
    DecisionEvidence,
    EntryRecording,
    LineDecision,
    QuoteDecisionEntry,
    QuoteDecisionLedger,
)
from cycling_workshop.quotes.domain import (
    DiscountLine,
    LaborLine,
    PartLine,
    Quote,
    QuoteLine,
    TaxLine,
)

MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_RECORD_BYTES = 256 * 1024
MAX_HISTORY_BYTES = 16 * 1024 * 1024
MAX_REVISIONS = 32
MAX_DECISIONS = 128
MAX_LINES = 100
MAX_EDGES = 1000

type JsonValue = bool | int | str | list[JsonValue] | dict[str, JsonValue] | None
type Document = dict[str, JsonValue]

_LINE_KINDS = {LaborLine: "labor", PartLine: "part", TaxLine: "tax", DiscountLine: "discount"}
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z\Z")


def _json(value: object, depth: int = 0) -> JsonValue:
    if depth > 12:
        raise ValueError("quote storage JSON exceeds depth limit")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("quote storage integer exceeds safe range")
        return value
    if type(value) is str:
        if "\x00" in value:
            raise ValueError("quote storage text contains NUL")
        try:
            value.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("quote storage text is not valid UTF-8") from exc
        return value
    if type(value) is list:
        return [_json(item, depth + 1) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        for key in value:
            _json(key, depth + 1)
        return {key: _json(item, depth + 1) for key, item in value.items()}
    raise ValueError("quote storage requires exact JSON values")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        _json(value), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _document(value: object, depth: int = 0) -> JsonValue:
    if depth > 12:
        raise ValueError("quote storage document exceeds nesting limit")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("quote storage timestamp requires a timezone")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        result = {
            field.name: _document(getattr(value, field.name), depth + 1) for field in fields(value)
        }
        kind = _LINE_KINDS.get(type(value))
        if kind is not None:
            result["kind"] = kind
        return result
    if isinstance(value, (tuple, list)):
        if len(value) > MAX_LINES:
            raise ValueError("quote storage document exceeds array limit")
        return [_document(item, depth + 1) for item in value]
    return _json(value, depth)


def _mapping(value: object, keys: str) -> Document:
    if type(value) is not dict or set(value) != set(keys.split()):
        raise ValueError("quote storage object has missing or unknown fields")
    return value


def _array(value: JsonValue, maximum: int = MAX_LINES) -> list[JsonValue]:
    if type(value) is not list or len(value) > maximum:
        raise ValueError("quote storage list exceeds shape or count limit")
    return value


def _string(value: JsonValue, maximum: int, *, required: bool = True) -> str:
    if type(value) is not str or len(value) > maximum or len(value.encode("utf-8")) > maximum * 4:
        raise ValueError("quote storage text exceeds shape or size limit")
    if required and not value.strip():
        raise ValueError("quote storage text must be nonblank")
    return value


def _optional_text(value: JsonValue, maximum: int) -> str | None:
    return None if value is None else _string(value, maximum)


def _id(value: JsonValue, *, generated: bool = False) -> str:
    result = _string(value, 36)
    if any(char.isspace() for char in result):
        raise ValueError("quote storage identity cannot contain whitespace")
    if generated:
        try:
            parsed = UUID(result)
        except ValueError as exc:
            raise ValueError("new quote storage identity requires UUIDv7") from exc
        if parsed.version != 7 or str(parsed) != result:
            raise ValueError("new quote storage identity requires canonical UUIDv7")
    return result


def _optional_id(value: JsonValue, *, generated: bool = False) -> str | None:
    return None if value is None else _id(value, generated=generated)


def _integer(value: JsonValue, minimum: int = 0, maximum: int = MAX_SAFE_INTEGER) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("quote storage integer exceeds shape or range")
    return value


def _timestamp(value: JsonValue) -> datetime:
    if type(value) is not str or not _TIMESTAMP.fullmatch(value):
        raise ValueError("quote storage requires canonical microsecond UTC timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid quote storage timestamp") from exc


def _optional_timestamp(value: JsonValue) -> datetime | None:
    return None if value is None else _timestamp(value)


def _ids(value: JsonValue) -> tuple[str, ...]:
    return tuple(_id(item, generated=True) for item in _array(value))


def _same(original: object, document: object) -> None:
    # Byte equality also distinguishes true from 1, unlike Python dict equality.
    if canonical_bytes(_document(original)) != canonical_bytes(document):
        raise ValueError("quote storage snapshot is noncanonical or inconsistent")


def _record(value: object) -> Document:
    document = _json(value)
    if type(document) is not dict or len(canonical_bytes(document)) > MAX_RECORD_BYTES:
        raise ValueError("quote storage record exceeds shape or byte limit")
    return document


def encode_lines(lines: tuple[QuoteLine, ...]) -> list[JsonValue]:
    if (
        type(lines) is not tuple
        or len(lines) > MAX_LINES
        or any(type(line) not in _LINE_KINDS for line in lines)
    ):
        raise ValueError("bounded typed quote line tuple required")
    document = _document(lines)
    if type(document) is not list:
        raise ValueError("typed quote line sequence required")
    decode_lines(document)
    return document


def decode_lines(value: JsonValue) -> tuple[QuoteLine, ...]:
    result: list[QuoteLine] = []
    edges = 0
    for item in _array(value):
        if type(item) is not dict:
            raise ValueError("typed quote storage line required")
        kind = item.get("kind")
        common = "kind line_id description"
        if kind == "labor":
            row = _mapping(item, common + " minutes hourly_rate_minor")
            line: QuoteLine = LaborLine(
                _id(row["line_id"], generated=True),
                _string(row["description"], 500),
                _integer(row["minutes"], 1, 1_000_000),
                _integer(row["hourly_rate_minor"]),
            )
        elif kind == "part":
            row = _mapping(item, common + " product_id quantity unit_price_minor")
            line = PartLine(
                _id(row["line_id"], generated=True),
                _string(row["description"], 500),
                _id(row["product_id"]),
                _integer(row["quantity"], 1, 1_000_000),
                _integer(row["unit_price_minor"]),
            )
        elif kind == "tax":
            row = _mapping(item, common + " rate_bps base_line_ids")
            targets = _ids(row["base_line_ids"])
            edges += len(targets)
            line = TaxLine(
                _id(row["line_id"], generated=True),
                _string(row["description"], 500),
                _integer(row["rate_bps"], 0, 10_000),
                targets,
            )
        elif kind == "discount":
            row = _mapping(item, common + " amount_minor scope_line_ids")
            targets = _ids(row["scope_line_ids"])
            edges += len(targets)
            line = DiscountLine(
                _id(row["line_id"], generated=True),
                _string(row["description"], 500),
                _integer(row["amount_minor"], 1),
                targets,
            )
        else:
            raise ValueError("unknown quote storage line kind")
        _same(line, item)
        result.append(line)
    if edges > MAX_EDGES:
        raise ValueError("quote storage reference edge limit exceeded")
    return tuple(result)


def encode_quote(quote: Quote) -> Document:
    if type(quote) is not Quote:
        raise ValueError("typed quote required")
    document = _record(_document(quote))
    decode_quote(document)
    return document


def decode_quote(value: object) -> Quote:
    row = _mapping(
        _record(value),
        "quote_id organization_id location_id order_id lines currency "
        "version created_at revises_quote_id superseded_at superseded_by totals",
    )
    quote = Quote(
        quote_id=_id(row["quote_id"], generated=True),
        organization_id=_id(row["organization_id"]),
        location_id=_id(row["location_id"]),
        order_id=_id(row["order_id"]),
        lines=decode_lines(row["lines"]),
        currency=_string(row["currency"], 3),
        version=_integer(row["version"], 1),
        created_at=_timestamp(row["created_at"]),
        revises_quote_id=_optional_id(row["revises_quote_id"], generated=True),
        superseded_at=_optional_timestamp(row["superseded_at"]),
        superseded_by=_optional_id(row["superseded_by"], generated=True),
    )
    _same(quote, row)
    return quote


def decode_evidence(value: JsonValue) -> DecisionEvidence | None:
    if value is None:
        return None
    row = _mapping(value, "party_kind party_id channel decided_at source_reference note")
    return DecisionEvidence(
        _string(row["party_kind"], 20),
        _id(row["party_id"]),
        _string(row["channel"], 20),
        _timestamp(row["decided_at"]),
        _optional_text(row["source_reference"], 200),
        _optional_text(row["note"], 2000),
    )


def encode_decision(command: DecisionCommand) -> Document:
    if type(command) is not DecisionCommand:
        raise ValueError("typed decision command required")
    document = _record(_document(command))
    decode_decision(document)
    return document


def decode_decision(value: object) -> DecisionCommand:
    row = _mapping(
        _record(value),
        "decision_id organization_id location_id order_id lineage_id "
        "quote_id quote_version expected_head_id expected_head_version expected_decision_sequence "
        "recorded_by_actor_id mode outcome approved_line_ids evidence supersedes_entry_id reason",
    )
    command = DecisionCommand(
        decision_id=_id(row["decision_id"], generated=True),
        organization_id=_id(row["organization_id"]),
        location_id=_id(row["location_id"]),
        order_id=_id(row["order_id"]),
        lineage_id=_id(row["lineage_id"], generated=True),
        quote_id=_id(row["quote_id"], generated=True),
        quote_version=_integer(row["quote_version"], 1),
        expected_head_id=_id(row["expected_head_id"], generated=True),
        expected_head_version=_integer(row["expected_head_version"], 1),
        expected_decision_sequence=_integer(row["expected_decision_sequence"]),
        recorded_by_actor_id=_id(row["recorded_by_actor_id"]),
        mode=_string(row["mode"], 30),
        outcome=_string(row["outcome"], 10),
        approved_line_ids=_ids(row["approved_line_ids"]),
        evidence=decode_evidence(row["evidence"]),
        supersedes_entry_id=_optional_id(row["supersedes_entry_id"], generated=True),
        reason=_optional_text(row["reason"], 500),
    )
    _same(command, row)
    return command


def decode_pricing(value: JsonValue) -> ApprovedPricing:
    row = _mapping(
        value,
        "currency approved_line_ids subtotal_minor discount_minor tax_minor "
        "total_minor charges discounts taxes",
    )
    charges: list[ApprovedCharge] = []
    for item in _array(row["charges"]):
        item = _mapping(item, "line_id gross_minor discount_minor net_minor")
        charges.append(
            ApprovedCharge(
                _id(item["line_id"], generated=True),
                _integer(item["gross_minor"]),
                _integer(item["discount_minor"]),
                _integer(item["net_minor"]),
            )
        )
    discounts: list[ApprovedDiscount] = []
    edges = 0
    for item in _array(row["discounts"]):
        item = _mapping(item, "line_id allocations")
        allocations: list[tuple[str, int]] = []
        for pair in _array(item["allocations"]):
            pair = _array(pair, 2)
            if len(pair) != 2:
                raise ValueError("quote allocation requires an ID and amount pair")
            allocations.append((_id(pair[0], generated=True), _integer(pair[1])))
        edges += len(allocations)
        discounts.append(ApprovedDiscount(_id(item["line_id"], generated=True), tuple(allocations)))
    taxes: list[ApprovedTax] = []
    for item in _array(row["taxes"]):
        item = _mapping(item, "line_id base_line_ids amount_minor")
        targets = _ids(item["base_line_ids"])
        edges += len(targets)
        taxes.append(
            ApprovedTax(
                _id(item["line_id"], generated=True), targets, _integer(item["amount_minor"])
            )
        )
    if edges > MAX_EDGES:
        raise ValueError("quote pricing reference edge limit exceeded")
    result = ApprovedPricing(
        _string(row["currency"], 3),
        _ids(row["approved_line_ids"]),
        _integer(row["subtotal_minor"]),
        _integer(row["discount_minor"]),
        _integer(row["tax_minor"]),
        _integer(row["total_minor"]),
        tuple(charges),
        tuple(discounts),
        tuple(taxes),
    )
    _same(result, value)
    return result


def encode_entry(entry: QuoteDecisionEntry) -> Document:
    if type(entry) is not QuoteDecisionEntry:
        raise ValueError("typed decision entry required")
    document = _record(_document(entry))
    decode_entry(document)
    return document


def decode_entry(value: object) -> QuoteDecisionEntry:
    row = _mapping(_record(value), "command sequence recording line_decisions pricing")
    recording = _mapping(row["recording"], "recorded_by_actor_id recorded_at reason")
    decisions: list[LineDecision] = []
    for item in _array(row["line_decisions"]):
        item = _mapping(item, "line_id approved")
        if type(item["approved"]) is not bool:
            raise ValueError("quote per-line decision requires an exact boolean")
        decisions.append(LineDecision(_id(item["line_id"], generated=True), item["approved"]))
    entry = QuoteDecisionEntry(
        decode_decision(row["command"]),
        _integer(row["sequence"], 1),
        EntryRecording(
            _id(recording["recorded_by_actor_id"]),
            _timestamp(recording["recorded_at"]),
            _optional_text(recording["reason"], 500),
        ),
        tuple(decisions),
        decode_pricing(row["pricing"]),
    )
    _same(entry, row)
    return entry


def validate_storage_ledger(ledger: QuoteDecisionLedger) -> None:
    if type(ledger) is not QuoteDecisionLedger:
        raise ValueError("typed complete quote ledger required")
    QuoteDecisionLedger(ledger.history, ledger.entries)
    if len(ledger.history.revisions) > MAX_REVISIONS or len(ledger.entries) > MAX_DECISIONS:
        raise ValueError("quote storage history count limit exceeded")
    for quote in ledger.history.revisions:
        encode_quote(quote)
    for entry in ledger.entries:
        encode_entry(entry)


def validate_history_bytes(logical_records: list[Document]) -> None:
    """Call with each joined financial/result/proof record exactly once."""
    if len(canonical_bytes(logical_records)) > MAX_HISTORY_BYTES:
        raise ValueError("quote storage complete-history byte limit exceeded")
