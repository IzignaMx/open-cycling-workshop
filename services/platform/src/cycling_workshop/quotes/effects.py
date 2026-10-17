"""Typed immutable order effects and validation of their retained source rows.

These values are receipts, never authority or a caller-prepared transition plan.
The application must create them from actual inserts in its owning transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes.commands import QuoteRepositoryCommand, RecordQuoteDecisionCommand
from cycling_workshop.quotes.models import QuoteOperationRecord
from cycling_workshop.quotes.storage import (
    _id,
    _integer,
    _json,
    _mapping,
    canonical_bytes,
)
from cycling_workshop.service_orders.models import ServiceOrderEventRecord
from cycling_workshop.sync.models import ChangeRecord


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
        _integer(self.resulting_order_version, 1)
        _integer(self.change_cursor, 1)


def _order_effects(operation: QuoteOperationRecord) -> QuoteOrderEffects | None:
    values = (
        operation.order_event_id,
        operation.resulting_order_version,
        operation.change_cursor,
        operation.order_outbox_id,
    )
    if all(value is None for value in values):
        return None
    if (
        operation.order_event_id is None
        or operation.resulting_order_version is None
        or operation.change_cursor is None
        or operation.order_outbox_id is None
    ):
        raise ValueError("order effect receipt must be complete or absent")
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
    event: ServiceOrderEventRecord,
    change: ChangeRecord,
    outbox: OutboxRecord,
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
    if (
        event.event_id,
        event.organization_id,
        event.order_id,
        event.from_state,
        event.to_state,
        event.action,
        event.actor_id,
        event.note,
        _utc(event.occurred_at),
    ) != (
        effects.order_event_id,
        command.organization_id,
        command.order_id,
        "DIAGNOSIS",
        target,
        action,
        command.actor_id,
        None,
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
    # This is the existing generic order projection, not a quote logical record.
    # Preserve its strict strings/nullable strings and existing JSON shape;
    # do not charge it to, or impose, the quote financial-record byte budget.
    payload = _mapping(
        _json(change.payload),
        "order_id customer_id bicycle_id organization_id location_id state reported_problem "
        "intake_condition accessories priority diagnosis created_at updated_at version",
    )
    for name in ("order_id", "customer_id", "organization_id", "location_id"):
        _id(payload[name])
    if payload["bicycle_id"] is not None:
        _id(payload["bicycle_id"])
    _integer(payload["version"], 1)
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
    for name in ("reported_problem", "priority"):
        if type(payload[name]) is not str:
            raise ValueError("order projection text required")
    for name in ("intake_condition", "accessories", "diagnosis"):
        if payload[name] is not None and type(payload[name]) is not str:
            raise ValueError("order projection nullable text required")
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
    ) or canonical_bytes(outbox.payload) != canonical_bytes(payload):
        raise ValueError("order outbox disagrees with retained change")
