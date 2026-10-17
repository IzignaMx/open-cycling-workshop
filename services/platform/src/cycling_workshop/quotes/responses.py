"""Closed command receipts and separately current quote/order projections.

This module grants no authority, loads no history and mounts no routes. Its
caller must project a fully reconstructed, freshly admitted locked snapshot.
Encode before commit and return those exact bytes after commit; a later replay
has the immutable receipt plus that later request's fresh current projections.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, ValidationError, model_validator

from cycling_workshop.quotes.reads import (
    RESPONSE_LIMIT,
    ClosedReadModel,
    CurrentLineage,
    Identifier,
    Money,
    PricingSummary,
    QuoteReadError,
    RevisionID,
    Timestamp,
    Version,
)


class OrderNow(ClosedReadModel):
    """Current scoped state only, never the generic order's personal/free text."""

    organization_id: Identifier
    location_id: Identifier
    order_id: Identifier
    state: Literal[
        "INTAKE",
        "DIAGNOSIS",
        "AUTHORIZED",
        "REJECTED",
        "IN_PROGRESS",
        "WAITING_FOR_PARTS",
        "READY",
        "CLOSED",
        "CANCELLED",
    ]
    version: Version


class DecisionNow(ClosedReadModel):
    """The exact current-head ledger entry, including a retained withdrawal.

    The projector uses the ledger's projection.decision_id and that exact entry
    for sequence. A superseded revision's decision is not a current decision.
    """

    decision_id: RevisionID
    quote_id: RevisionID
    sequence: Version
    outcome: Literal["APPROVE", "REJECT", "PARTIAL", "WITHDRAW"]


class QuoteOnlyEffects(ClosedReadModel):
    """Historical quote persistence; no order transition may be inferred."""

    kind: Literal["quote_only"]
    quote_outbox_id: RevisionID
    order_event_id: None
    resulting_order_version: None
    change_cursor: None
    order_outbox_id: None


class OrderTransitionEffects(ClosedReadModel):
    """Actual allocated immutable effect identities, validated by reconstruction."""

    kind: Literal["order_transition"]
    quote_outbox_id: RevisionID
    order_event_id: Identifier
    resulting_order_version: Version
    change_cursor: Version
    order_outbox_id: Identifier

    @model_validator(mode="after")
    def distinct_delivery_identities(self) -> Self:
        if self.quote_outbox_id == self.order_outbox_id:
            raise ValueError("quote and order outbox identities must differ")
        return self


type Effects = Annotated[QuoteOnlyEffects | OrderTransitionEffects, Field(discriminator="kind")]


class Receipt(ClosedReadModel):
    """Operation-time result only; neither proof nor present execution authority."""

    operation_id: RevisionID
    kind: Literal["create", "revise", "decision"]
    ordinal: Version
    quote_id: RevisionID
    quote_version: Version
    decision_id: RevisionID | None
    decision_sequence: Money
    recorded_at: Timestamp
    recorded_by_actor_id: Identifier
    totals: PricingSummary
    effects: Effects

    @model_validator(mode="after")
    def consistent_kind(self) -> Self:
        # ordinal is already a safe Version; equality also bounds the sum.
        if self.ordinal != self.quote_version + self.decision_sequence:
            raise ValueError("invalid quote receipt ordinal")
        if self.kind == "decision":
            if self.decision_id != self.operation_id or self.decision_sequence < 1:
                raise ValueError("invalid quote decision receipt")
        elif self.decision_id is not None or self.effects.kind != "quote_only":
            raise ValueError("invalid quote revision receipt")
        return self


class CommandResponse(ClosedReadModel):
    """One request's delivery and fresh context around an immutable receipt."""

    delivery: Literal["applied", "replayed"]
    receipt: Receipt
    current: CurrentLineage
    current_decision: DecisionNow | None
    order: OrderNow

    @model_validator(mode="after")
    def consistent_context(self) -> Self:
        if (
            self.order.organization_id,
            self.order.location_id,
            self.order.order_id,
        ) != (
            self.current.organization_id,
            self.current.location_id,
            self.current.order_id,
        ):
            raise ValueError("invalid quote response scope")
        if self.current_decision is not None and (
            self.current_decision.quote_id != self.current.head_quote_id
            or self.current_decision.sequence != self.current.decision_sequence
        ):
            raise ValueError("invalid current quote decision")
        if (
            self.delivery == "applied"
            and self.receipt.kind == "decision"
            and self.receipt.effects.kind != "order_transition"
        ):
            raise ValueError("applied quote decision requires order transition")
        # Receipt/head/order can differ on replay. Expected-order-version + 1,
        # effect association and exact current-entry lookup belong to the
        # admitted service/reconstruction, not inference from these wire fields.
        return self


def encode_command_response(response: CommandResponse) -> bytes:
    """Validate before commit; the caller must send exactly these bounded bytes."""
    if type(response) is not CommandResponse:
        raise QuoteReadError("invalid_quote_projection")
    try:
        # model_copy/model_construct (including nested values) bypass validation.
        checked = CommandResponse.model_validate(response)
        encoded = checked.model_dump_json().encode("utf-8")
    except (ValidationError, ValueError, TypeError, UnicodeError):
        raise QuoteReadError("invalid_quote_projection") from None
    if len(encoded) > RESPONSE_LIMIT:
        raise QuoteReadError("quote_response_too_large")
    return encoded
