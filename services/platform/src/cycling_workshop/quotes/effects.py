"""Typed immutable order effects and validation of their retained source rows.

These values are receipts, never authority or a caller-prepared transition plan.
The application must create them from actual inserts in its owning transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cycling_workshop.quotes.commands import QuoteRepositoryCommand, RecordQuoteDecisionCommand
from cycling_workshop.quotes.models import QuoteOperationRecord
from cycling_workshop.quotes.storage import (
    _id,
    _integer,
    canonical_bytes,
)
from cycling_workshop.service_orders.domain import TransitionResult
from cycling_workshop.sync.order_projection_integrity import (
    PreparedOrderProjection,
    decode_order_projection,
)


@dataclass(frozen=True, slots=True)
class PreparedQuoteOrderEffect:
    """Private pure result; created only inside the locked application call."""

    transition: TransitionResult
    projection: PreparedOrderProjection


@dataclass
class OrderEffectEvent:
    event_id: str
    organization_id: str
    order_id: str
    from_state: str
    to_state: str
    action: str
    actor_id: str
    note_is_null: bool
    occurred_at: datetime


@dataclass
class OrderEffectChange:
    cursor: int
    organization_id: str
    location_id: str
    entity_type: str
    entity_id: str
    operation: str
    entity_version: int
    occurred_at: datetime
    raw_json: str
    raw_octets: int


@dataclass
class OrderEffectOutbox:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    organization_id: str
    location_id: str
    occurred_at: datetime
    raw_json: str
    raw_octets: int


@dataclass(frozen=True, slots=True)
class QuoteOrderEffects:
    order_event_id: str
    resulting_order_version: int
    change_cursor: int
    order_outbox_id: str

    def __post_init__(self) -> None:
        for value in (self.order_event_id, self.order_outbox_id):
            canonical_bytes(value)
            _id(value)
        _integer(self.resulting_order_version, 1, 2147483647)
        _integer(self.change_cursor, 1)


def _order_effects(operation: QuoteOperationRecord) -> QuoteOrderEffects | None:
    values = (
        operation.order_event_id,
        operation.resulting_order_version,
        operation.change_cursor,
        operation.order_outbox_id,
    )
    version = operation.order_effect_version
    if all(value is None for value in values) and version is None:
        return None
    if (
        type(version) is not int
        or version != 1
        or operation.kind != "decision"
        or operation.order_event_id is None
        or operation.resulting_order_version is None
        or operation.change_cursor is None
        or operation.order_outbox_id is None
    ):
        raise ValueError("order effect receipt requires supported version and complete tuple")
    return QuoteOrderEffects(
        operation.order_event_id,
        operation.resulting_order_version,
        operation.change_cursor,
        operation.order_outbox_id,
    )


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime:
        raise ValueError("stored datetime required")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _projection_time(value: object) -> datetime:
    # Preserve the existing order_payload ISO format, including optional
    # microseconds; do not silently normalize altered stored projection bytes.
    if type(value) is not str:
        raise ValueError("order projection timestamp required")
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(0) or result.isoformat() != value:
        raise ValueError("order projection timestamp must be canonical UTC")
    return result


def _validate_order_effects(
    effects: QuoteOrderEffects,
    command: QuoteRepositoryCommand,
    recorded_at: datetime,
    quote_outbox_id: str,
    event: OrderEffectEvent,
    change: OrderEffectChange,
    outbox: OrderEffectOutbox,
) -> None:
    """Validate actual linked rows, independently of today's mutable order row."""
    # A typed value is not itself proof: recheck scalars even if a caller used
    # object.__setattr__ to forge frozen dataclass internals.
    QuoteOrderEffects(
        effects.order_event_id,
        effects.resulting_order_version,
        effects.change_cursor,
        effects.order_outbox_id,
    )
    if not isinstance(command, RecordQuoteDecisionCommand):
        raise ValueError("only a decision may own an order transition")
    proof = command.command
    evidence = proof.evidence
    if (
        proof.mode != "initial"
        or proof.expected_decision_sequence != 0
        or proof.outcome not in ("APPROVE", "PARTIAL", "REJECT")
        or evidence is None
        or evidence.party_kind != "customer"
        or evidence.channel not in ("in_person", "phone", "email", "messaging", "written")
        or effects.resulting_order_version != command.expected_order_version + 1
        or effects.order_event_id != command.operation_id
        or effects.order_outbox_id == quote_outbox_id
    ):
        raise ValueError("order transition disagrees with admitted initial decision")
    action, target = (
        ("reject", "REJECTED") if proof.outcome == "REJECT" else ("authorize", "AUTHORIZED")
    )
    if type(event.note_is_null) is not bool:
        raise ValueError("order event nullness requires an exact boolean")
    if (
        event.event_id,
        event.organization_id,
        event.order_id,
        event.from_state,
        event.to_state,
        event.action,
        event.actor_id,
        event.note_is_null,
        _utc(event.occurred_at),
    ) != (
        effects.order_event_id,
        command.organization_id,
        command.order_id,
        "DIAGNOSIS",
        target,
        action,
        command.actor_id,
        True,
        recorded_at,
    ):
        raise ValueError("order event disagrees with quote receipt")
    _integer(change.cursor, 1)
    _integer(change.entity_version, 1)
    if (
        change.cursor,
        change.organization_id,
        change.location_id,
        change.entity_type,
        change.entity_id,
        change.operation,
        change.entity_version,
        _utc(change.occurred_at),
    ) != (
        effects.change_cursor,
        command.organization_id,
        command.location_id,
        "service_order",
        command.order_id,
        "update",
        effects.resulting_order_version,
        recorded_at,
    ):
        raise ValueError("order change disagrees with quote receipt")
    # The only linked-source representation is guarded raw Text. Never accept
    # an ORM-decoded payload that has already lost duplicate keys/number lexemes.
    change_projection = decode_order_projection(change.raw_json, stored_octets=change.raw_octets)
    outbox_projection = decode_order_projection(outbox.raw_json, stored_octets=outbox.raw_octets)
    payload = change_projection.payload
    if (
        payload["order_id"],
        payload["customer_id"],
        payload["organization_id"],
        payload["location_id"],
        payload["state"],
        payload["version"],
        _projection_time(payload["updated_at"]),
    ) != (
        command.order_id,
        evidence.party_id,
        command.organization_id,
        command.location_id,
        target,
        effects.resulting_order_version,
        recorded_at,
    ) or _projection_time(payload["created_at"]) > recorded_at:
        raise ValueError("order projection disagrees with initial transition")
    if (
        outbox.event_id,
        outbox.event_type,
        outbox.aggregate_type,
        outbox.aggregate_id,
        outbox.organization_id,
        outbox.location_id,
        _utc(outbox.occurred_at),
    ) != (
        effects.order_outbox_id,
        "service_order.updated",
        "service_order",
        command.order_id,
        command.organization_id,
        command.location_id,
        recorded_at,
    ) or outbox_projection.canonical_utf8 != change_projection.canonical_utf8:
        raise ValueError("order outbox disagrees with retained change")
