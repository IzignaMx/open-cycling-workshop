"""Finite quote repository commands and versioned semantic proofs.

These private commands provide no user authority or HTTP entry point. Their
caller must retain the existing admission boundary and transaction ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from cycling_workshop.quotes.decisions import DecisionCommand
from cycling_workshop.quotes.domain import Quote, QuoteLine
from cycling_workshop.quotes.storage import (
    Document,
    _id,
    _integer,
    _mapping,
    _record,
    _string,
    canonical_bytes,
    decode_decision,
    decode_lines,
    encode_decision,
    encode_lines,
    encode_quote,
)


def _lines(value: object) -> tuple[QuoteLine, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("quote command requires typed lines")
    return decode_lines(encode_lines(tuple(value)))


def _scope(
    organization_id: str, location_id: str, order_id: str, actor_id: str, version: int
) -> None:
    for value in (organization_id, location_id, order_id, actor_id):
        _id(value)
    _integer(version, 1)


@dataclass(frozen=True, slots=True)
class CreateQuoteCommand:
    operation_id: str
    quote_id: str
    organization_id: str
    location_id: str
    order_id: str
    actor_id: str
    expected_order_version: int
    currency: str
    lines: tuple[QuoteLine, ...]

    def __post_init__(self) -> None:
        _scope(
            self.organization_id,
            self.location_id,
            self.order_id,
            self.actor_id,
            self.expected_order_version,
        )
        _id(self.operation_id, generated=True)
        _id(self.quote_id, generated=True)
        lines = _lines(self.lines)
        # Calculation validates financial shape; this fixed validation time is
        # neither execution metadata nor part of the semantic proof.
        encode_quote(
            Quote.for_order(
                quote_id=self.quote_id,
                organization_id=self.organization_id,
                location_id=self.location_id,
                order_id=self.order_id,
                lines=lines,
                currency=self.currency,
                now=datetime(1970, 1, 1, tzinfo=UTC),
            )
        )
        object.__setattr__(self, "lines", lines)

    @property
    def lineage_id(self) -> str:
        return self.quote_id

    @property
    def expected_head_id(self) -> None:
        return None

    @property
    def expected_head_version(self) -> int:
        return 0

    @property
    def expected_decision_sequence(self) -> int:
        return 0


@dataclass(frozen=True, slots=True)
class ReviseQuoteCommand:
    operation_id: str
    quote_id: str
    organization_id: str
    location_id: str
    order_id: str
    actor_id: str
    expected_order_version: int
    lineage_id: str
    expected_head_id: str
    expected_head_version: int
    expected_decision_sequence: int
    lines: tuple[QuoteLine, ...]

    def __post_init__(self) -> None:
        _scope(
            self.organization_id,
            self.location_id,
            self.order_id,
            self.actor_id,
            self.expected_order_version,
        )
        for value in (self.operation_id, self.quote_id, self.lineage_id, self.expected_head_id):
            _id(value, generated=True)
        _integer(self.expected_head_version, 1)
        _integer(self.expected_decision_sequence)
        if self.quote_id in (self.lineage_id, self.expected_head_id):
            raise ValueError("revision command requires a new revision identity")
        object.__setattr__(self, "lines", _lines(self.lines))


@dataclass(frozen=True, slots=True)
class RecordQuoteDecisionCommand:
    command: DecisionCommand
    expected_order_version: int

    def __post_init__(self) -> None:
        _integer(self.expected_order_version, 1)
        # Retain a canonical immutable copy, not an independently mutable proof.
        object.__setattr__(self, "command", decode_decision(encode_decision(self.command)))

    @property
    def operation_id(self) -> str:
        return self.command.decision_id

    @property
    def quote_id(self) -> str:
        return self.command.quote_id

    @property
    def organization_id(self) -> str:
        return self.command.organization_id

    @property
    def location_id(self) -> str:
        return self.command.location_id

    @property
    def order_id(self) -> str:
        return self.command.order_id

    @property
    def actor_id(self) -> str:
        return self.command.recorded_by_actor_id

    @property
    def lineage_id(self) -> str:
        return self.command.lineage_id

    @property
    def expected_head_id(self) -> str:
        return self.command.expected_head_id

    @property
    def expected_head_version(self) -> int:
        return self.command.expected_head_version

    @property
    def expected_decision_sequence(self) -> int:
        return self.command.expected_decision_sequence


type QuoteRepositoryCommand = CreateQuoteCommand | ReviseQuoteCommand | RecordQuoteDecisionCommand


def operation_proof(command: QuoteRepositoryCommand) -> Document:
    if type(command) is RecordQuoteDecisionCommand:
        return _record(
            {
                "schema_version": 1,
                "kind": "decision",
                "expected_order_version": command.expected_order_version,
                "command": encode_decision(command.command),
            }
        )
    if not isinstance(command, (CreateQuoteCommand, ReviseQuoteCommand)) or type(command) not in (
        CreateQuoteCommand,
        ReviseQuoteCommand,
    ):
        raise ValueError("typed quote repository command required")
    proof: Document = {
        "schema_version": 1,
        "kind": "create" if type(command) is CreateQuoteCommand else "revise",
        "operation_id": command.operation_id,
        "quote_id": command.quote_id,
        "organization_id": command.organization_id,
        "location_id": command.location_id,
        "order_id": command.order_id,
        "actor_id": command.actor_id,
        "expected_order_version": command.expected_order_version,
        "lineage_id": command.lineage_id,
        "expected_head_id": command.expected_head_id,
        "expected_head_version": command.expected_head_version,
        "expected_decision_sequence": command.expected_decision_sequence,
        "lines": encode_lines(command.lines),
    }
    if type(command) is CreateQuoteCommand:
        proof["currency"] = command.currency
    return _record(proof)


def command_from_proof(value: object) -> QuoteRepositoryCommand:
    row = _record(value)
    _integer(row.get("schema_version"), 1, 1)
    kind = row.get("kind")
    if kind == "decision":
        row = _mapping(row, "schema_version kind expected_order_version command")
        result: QuoteRepositoryCommand = RecordQuoteDecisionCommand(
            decode_decision(row["command"]), _integer(row["expected_order_version"], 1)
        )
    else:
        common = (
            "schema_version kind operation_id quote_id organization_id location_id order_id "
            "actor_id expected_order_version lineage_id expected_head_id expected_head_version "
            "expected_decision_sequence lines"
        )
        row = _mapping(row, common + (" currency" if kind == "create" else ""))
        if kind == "create":
            if row["lineage_id"] != row["quote_id"] or row["expected_head_id"] is not None:
                raise ValueError("creation proof requires root identity and absent head")
            _integer(row["expected_head_version"], 0, 0)
            _integer(row["expected_decision_sequence"], 0, 0)
            result = CreateQuoteCommand(
                _id(row["operation_id"], generated=True),
                _id(row["quote_id"], generated=True),
                _id(row["organization_id"]),
                _id(row["location_id"]),
                _id(row["order_id"]),
                _id(row["actor_id"]),
                _integer(row["expected_order_version"], 1),
                _string(row["currency"], 3),
                decode_lines(row["lines"]),
            )
        elif kind == "revise":
            result = ReviseQuoteCommand(
                _id(row["operation_id"], generated=True),
                _id(row["quote_id"], generated=True),
                _id(row["organization_id"]),
                _id(row["location_id"]),
                _id(row["order_id"]),
                _id(row["actor_id"]),
                _integer(row["expected_order_version"], 1),
                _id(row["lineage_id"], generated=True),
                _id(row["expected_head_id"], generated=True),
                _integer(row["expected_head_version"], 1),
                _integer(row["expected_decision_sequence"]),
                decode_lines(row["lines"]),
            )
        else:
            raise ValueError("unknown quote proof operation kind")
    if canonical_bytes(operation_proof(result)) != canonical_bytes(row):
        raise ValueError("quote operation proof is not canonical")
    return result
