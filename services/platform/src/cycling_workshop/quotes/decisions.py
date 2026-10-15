"""Pure quote consent evidence; this module grants no server or stock authority."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from cycling_workshop.quotes.domain import (
    DiscountLine,
    LaborLine,
    PartLine,
    Quote,
    QuoteLine,
    QuoteRevision,
    TaxLine,
    _allocate_discount,
    _identifier,
    _integer,
    _round_half_up,
    _timestamp,
)
from cycling_workshop.quotes.history import QuoteHistory
from cycling_workshop.service_orders.domain import OrderState, ServiceOrder


def _selection(values: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("selection must be a list or tuple")
    for value in values:
        _identifier(value, "selected line ID")
    if len(values) != len(set(values)):
        raise ValueError("selection contains duplicate IDs")
    return tuple(sorted(values))


def _text(value: str | None, field: str) -> None:
    if value is not None and (type(value) is not str or not value.strip()):
        raise ValueError(f"{field} must be nonblank text when supplied")


def _values[T](values: Sequence[T], cls: type[T]) -> tuple[T, ...]:
    if not isinstance(values, (list, tuple)) or any(type(value) is not cls for value in values):
        raise ValueError("expected a sequence of typed immutable values")
    return tuple(values)


@dataclass(frozen=True, slots=True)
class ApprovedCharge:
    line_id: str
    gross_minor: int
    discount_minor: int
    net_minor: int

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        for name in ("gross_minor", "discount_minor", "net_minor"):
            _integer(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ApprovedDiscount:
    line_id: str
    allocations: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        if not isinstance(self.allocations, (list, tuple)):
            raise ValueError("discount allocations must be a sequence")
        copied: list[tuple[str, int]] = []
        for pair in self.allocations:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError("allocation must be an ID and amount pair")
            _identifier(pair[0], "allocation line ID")
            _integer(pair[1], "allocation amount")
            copied.append((pair[0], pair[1]))
        if len({key for key, _ in copied}) != len(copied):
            raise ValueError("duplicate allocation line ID")
        object.__setattr__(self, "allocations", tuple(sorted(copied)))


@dataclass(frozen=True, slots=True)
class ApprovedTax:
    line_id: str
    base_line_ids: tuple[str, ...]
    amount_minor: int

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        _integer(self.amount_minor, "tax amount")
        object.__setattr__(self, "base_line_ids", _selection(self.base_line_ids))


@dataclass(frozen=True, slots=True)
class ApprovedPricing:
    currency: str
    approved_line_ids: tuple[str, ...]
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    charges: tuple[ApprovedCharge, ...]
    discounts: tuple[ApprovedDiscount, ...]
    taxes: tuple[ApprovedTax, ...]

    def __post_init__(self) -> None:
        if (
            type(self.currency) is not str
            or len(self.currency) != 3
            or not all("A" <= char <= "Z" for char in self.currency)
        ):
            raise ValueError("currency must be three uppercase ASCII letters")
        for name in ("subtotal_minor", "discount_minor", "tax_minor", "total_minor"):
            _integer(getattr(self, name), name)
        object.__setattr__(self, "approved_line_ids", _selection(self.approved_line_ids))
        object.__setattr__(self, "charges", _values(self.charges, ApprovedCharge))
        object.__setattr__(self, "discounts", _values(self.discounts, ApprovedDiscount))
        object.__setattr__(self, "taxes", _values(self.taxes, ApprovedTax))


def price_selection(quote: Quote, approved_line_ids: Sequence[str]) -> ApprovedPricing:
    """Keep original discount shares; round once per selected discounted tax base."""
    if type(quote) is not Quote:
        raise ValueError("pricing requires a quote")
    selected = _selection(approved_line_ids)
    gross = {
        line.line_id: (
            _round_half_up(line.minutes * line.hourly_rate_minor, 60)
            if isinstance(line, LaborLine)
            else line.quantity * line.unit_price_minor
        )
        for line in quote.lines
        if isinstance(line, (LaborLine, PartLine))
    }
    if not set(selected).issubset(gross):
        raise ValueError("selection must contain only this revision's charge IDs")
    allocations = {
        line.line_id: _allocate_discount(gross, line)
        for line in quote.lines
        if isinstance(line, DiscountLine)
    }
    discounts = tuple(
        ApprovedDiscount(line_id, tuple((key, shares[key]) for key in selected if key in shares))
        for line_id, shares in sorted(allocations.items())
    )
    charges = tuple(
        ApprovedCharge(
            key,
            gross[key],
            sum(shares.get(key, 0) for shares in allocations.values()),
            gross[key] - sum(shares.get(key, 0) for shares in allocations.values()),
        )
        for key in selected
    )
    net = {charge.line_id: charge.net_minor for charge in charges}
    taxes = tuple(
        ApprovedTax(
            line.line_id,
            tuple(key for key in line.base_line_ids if key in net),
            _round_half_up(
                sum(net.get(key, 0) for key in line.base_line_ids) * line.rate_bps, 10000
            ),
        )
        for line in sorted(quote.lines, key=lambda line: line.line_id)
        if isinstance(line, TaxLine)
    )
    subtotal = sum(charge.gross_minor for charge in charges)
    discount = sum(charge.discount_minor for charge in charges)
    tax = sum(line.amount_minor for line in taxes)
    return ApprovedPricing(
        quote.currency,
        selected,
        subtotal,
        discount,
        tax,
        subtotal - discount + tax,
        charges,
        discounts,
        taxes,
    )


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    party_kind: str
    party_id: str
    channel: str
    decided_at: datetime
    source_reference: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.party_kind not in ("customer", "representative"):
            raise ValueError("unknown decision party kind")
        _identifier(self.party_id, "party_id")
        if self.channel not in ("in_person", "phone", "email", "messaging", "written", "portal"):
            raise ValueError("unknown evidence channel")
        object.__setattr__(self, "decided_at", _timestamp(self.decided_at))
        if self.source_reference is not None:
            _identifier(self.source_reference, "source_reference")
        _text(self.note, "note")


@dataclass(frozen=True, slots=True)
class EntryRecording:
    recorded_by_actor_id: str
    recorded_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.recorded_by_actor_id, "recorded_by_actor_id")
        object.__setattr__(self, "recorded_at", _timestamp(self.recorded_at))
        _text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class DecisionCommand:
    decision_id: str
    organization_id: str
    location_id: str
    order_id: str
    lineage_id: str
    quote_id: str
    quote_version: int
    expected_head_id: str
    expected_head_version: int
    expected_decision_sequence: int
    recorded_by_actor_id: str
    mode: str
    outcome: str
    approved_line_ids: tuple[str, ...]
    evidence: DecisionEvidence | None
    supersedes_entry_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "organization_id",
            "location_id",
            "order_id",
            "lineage_id",
            "quote_id",
            "expected_head_id",
            "recorded_by_actor_id",
        ):
            _identifier(getattr(self, name), name)
        _integer(self.quote_version, "quote_version", minimum=1)
        _integer(self.expected_head_version, "expected_head_version", minimum=1)
        _integer(self.expected_decision_sequence, "expected_decision_sequence")
        if self.mode not in ("initial", "customer_change", "record_correction", "withdraw_record"):
            raise ValueError("unknown decision mode")
        if self.outcome not in ("APPROVE", "REJECT", "PARTIAL", "WITHDRAW"):
            raise ValueError("unknown decision outcome")
        if self.evidence is not None and type(self.evidence) is not DecisionEvidence:
            raise ValueError("evidence must be a typed customer evidence value")
        if self.supersedes_entry_id is not None:
            _identifier(self.supersedes_entry_id, "supersedes_entry_id")
        _text(self.reason, "reason")
        object.__setattr__(self, "approved_line_ids", _selection(self.approved_line_ids))


@dataclass(frozen=True, slots=True)
class LineDecision:
    line_id: str
    approved: bool

    def __post_init__(self) -> None:
        _identifier(self.line_id, "line_id")
        if type(self.approved) is not bool:
            raise ValueError("per-line approval must be an exact boolean")


@dataclass(frozen=True, slots=True)
class QuoteDecisionEntry:
    command: DecisionCommand
    sequence: int
    recording: EntryRecording
    line_decisions: tuple[LineDecision, ...]
    pricing: ApprovedPricing

    def __post_init__(self) -> None:
        if type(self.command) is not DecisionCommand or type(self.recording) is not EntryRecording:
            raise ValueError("entry requires typed command and recording")
        _integer(self.sequence, "decision sequence", minimum=1)
        if not isinstance(self.line_decisions, (list, tuple)):
            raise ValueError("entry line decisions must be a sequence")
        if any(type(line) is not LineDecision for line in self.line_decisions):
            raise ValueError("entry line decisions must be typed")
        object.__setattr__(self, "line_decisions", tuple(self.line_decisions))
        if type(self.pricing) is not ApprovedPricing:
            raise ValueError("entry requires typed calculated pricing")


@dataclass(frozen=True, slots=True)
class DecisionProjection:
    quote_id: str
    quote_version: int
    decision_id: str | None
    outcome: str
    approved_line_ids: tuple[str, ...]
    pricing: ApprovedPricing | None


@dataclass(frozen=True, slots=True)
class QuoteDecisionRecorded:
    event_id: str
    organization_id: str
    location_id: str
    order_id: str
    lineage_id: str
    quote_id: str
    quote_version: int
    sequence: int
    mode: str
    outcome: str
    approved_line_ids: tuple[str, ...]
    declined_line_ids: tuple[str, ...]
    pricing: ApprovedPricing
    evidence_entry_id: str
    supersedes_entry_id: str | None


def _event_for(entry: QuoteDecisionEntry) -> QuoteDecisionRecorded:
    command = entry.command
    return QuoteDecisionRecorded(
        command.decision_id,
        command.organization_id,
        command.location_id,
        command.order_id,
        command.lineage_id,
        command.quote_id,
        command.quote_version,
        entry.sequence,
        command.mode,
        command.outcome,
        command.approved_line_ids,
        tuple(line.line_id for line in entry.line_decisions if not line.approved),
        entry.pricing,
        command.decision_id,
        command.supersedes_entry_id,
    )


def _scope(command: DecisionCommand, history: QuoteHistory) -> None:
    head = history.head
    if (command.organization_id, command.location_id, command.order_id, command.lineage_id) != (
        head.organization_id,
        head.location_id,
        head.order_id,
        history.lineage_id,
    ):
        raise ValueError("decision scope or lineage mismatch")


def _line_decisions(quote: Quote, command: DecisionCommand) -> tuple[LineDecision, ...]:
    if command.outcome == "WITHDRAW":
        return ()
    return tuple(
        LineDecision(line.line_id, line.line_id in command.approved_line_ids)
        for line in sorted(quote.lines, key=lambda line: line.line_id)
        if isinstance(line, (LaborLine, PartLine))
    )


def _admit(
    quote: Quote,
    command: DecisionCommand,
    recording: EntryRecording,
    previous: QuoteDecisionEntry | None,
    previous_customer_time: datetime | None,
) -> None:
    """Validate one entry in its observed history prefix, also on reconstruction."""
    if (command.quote_id, command.quote_version) != (quote.quote_id, quote.version) or (
        command.expected_head_id,
        command.expected_head_version,
    ) != (quote.quote_id, quote.version):
        raise ValueError("decision must target its observed current revision")
    if recording.recorded_by_actor_id != command.recorded_by_actor_id or (
        recording.reason != command.reason
    ):
        raise ValueError("recording must match the canonical command")
    if recording.recorded_at < quote.created_at or (
        quote.superseded_at is not None and recording.recorded_at > quote.superseded_at
    ):
        raise ValueError("recording must be within observed revision's active interval")
    if command.mode == "initial":
        if (
            previous is not None
            or command.supersedes_entry_id is not None
            or command.reason is not None
        ):
            raise ValueError("initial decision cannot replace existing evidence")
    elif (
        previous is None
        or command.supersedes_entry_id != previous.command.decision_id
        or command.reason is None
        or command.supersedes_entry_id == command.decision_id
    ):
        raise ValueError("correction requires latest entry and a reason")
    if (command.mode == "withdraw_record") != (command.outcome == "WITHDRAW"):
        raise ValueError("withdrawal mode and outcome must agree")
    if command.outcome == "WITHDRAW":
        if command.evidence is not None or command.approved_line_ids:
            raise ValueError("withdrawal cannot invent customer evidence or selected lines")
        return
    evidence = command.evidence
    if evidence is None:
        raise ValueError("customer decision requires evidence")
    if not quote.created_at <= evidence.decided_at <= recording.recorded_at:
        raise ValueError("customer decision must be within revision and recording interval")
    if (
        command.mode == "customer_change"
        and previous_customer_time is not None
        and (evidence.decided_at < previous_customer_time)
    ):
        raise ValueError("customer change cannot precede previous customer decision")
    charges = {line.line_id for line in quote.lines if isinstance(line, (LaborLine, PartLine))}
    selected = set(command.approved_line_ids)
    if not selected.issubset(charges):
        raise ValueError("decision references an unknown charge")
    if command.outcome == "APPROVE" and selected != charges:
        raise ValueError("approval must select every charge")
    if command.outcome == "REJECT" and selected:
        raise ValueError("rejection cannot approve charges")
    if command.outcome == "PARTIAL" and not (selected and selected < charges):
        raise ValueError("partial approval requires a nonempty proper charge subset")


@dataclass(frozen=True, slots=True)
class QuoteDecisionLedger:
    history: QuoteHistory
    entries: tuple[QuoteDecisionEntry, ...] = ()

    def __post_init__(self) -> None:
        if type(self.history) is not QuoteHistory:
            raise ValueError("decision ledger requires a complete quote history")
        # Validate rather than silently repair a supplied history or proof/result pair.
        if QuoteHistory(self.history.revisions) != self.history:
            raise ValueError("invalid quote history")
        if not isinstance(self.entries, (list, tuple)):
            raise ValueError("decision entries must be a sequence")
        entries = tuple(self.entries)
        revisions = {quote.quote_id: quote for quote in self.history.revisions}
        latest: dict[str, QuoteDecisionEntry] = {}
        customer_times: dict[str, datetime] = {}
        ids: set[str] = set()
        previous_head_version = 0
        previous_recorded_at: datetime | None = None
        for index, entry in enumerate(entries):
            if type(entry) is not QuoteDecisionEntry:
                raise ValueError("decision entries must be typed")
            command = entry.command
            _scope(command, self.history)
            if command.decision_id in ids:
                raise ValueError("duplicate decision identity")
            ids.add(command.decision_id)
            if entry.sequence != index + 1 or command.expected_decision_sequence != index:
                raise ValueError("decision sequence or proof precondition mismatch")
            quote = revisions.get(command.quote_id)
            if quote is None or quote.version < previous_head_version:
                raise ValueError("observed history prefix missing or moved backward")
            if (
                previous_recorded_at is not None
                and entry.recording.recorded_at < previous_recorded_at
            ):
                raise ValueError("decision recording time cannot move backward")
            _admit(
                quote,
                command,
                entry.recording,
                latest.get(quote.quote_id),
                customer_times.get(quote.quote_id),
            )
            if entry.pricing != price_selection(quote, command.approved_line_ids) or (
                entry.line_decisions != _line_decisions(quote, command)
            ):
                raise ValueError("entry pricing or per-line decisions disagree with proof")
            latest[quote.quote_id] = entry
            if command.evidence is not None:
                customer_times[quote.quote_id] = command.evidence.decided_at
            previous_head_version = quote.version
            previous_recorded_at = entry.recording.recorded_at
        object.__setattr__(self, "entries", entries)

    @property
    def sequence(self) -> int:
        return len(self.entries)

    @property
    def projection(self) -> DecisionProjection:
        head = self.history.head
        latest = next(
            (entry for entry in reversed(self.entries) if entry.command.quote_id == head.quote_id),
            None,
        )
        if latest is None:
            return DecisionProjection(
                head.quote_id, head.version, None, "NO_CURRENT_DECISION", (), None
            )
        command = latest.command
        return DecisionProjection(
            head.quote_id,
            head.version,
            command.decision_id,
            command.outcome,
            command.approved_line_ids,
            latest.pricing,
        )

    def _check_head(self, head_id: str, version: int, sequence: int) -> None:
        _identifier(head_id, "expected_head_id")
        _integer(version, "expected_head_version", minimum=1)
        _integer(sequence, "expected_decision_sequence")
        if (head_id, version, sequence) != (
            self.history.head.quote_id,
            self.history.head.version,
            self.sequence,
        ):
            raise ValueError("stale quote head or decision sequence")

    def record(self, command: DecisionCommand, *, recorded_at: datetime) -> QuoteDecisionResult:
        if type(command) is not DecisionCommand:
            raise ValueError("typed decision command required")
        _scope(command, self.history)
        for entry in self.entries:
            if entry.command.decision_id == command.decision_id:
                if entry.command != command:
                    raise ValueError("decision ID reused with different command proof")
                return QuoteDecisionResult(self, entry, self.projection, None, True)
        self._check_head(
            command.expected_head_id,
            command.expected_head_version,
            command.expected_decision_sequence,
        )
        head = self.history.head
        if (command.quote_id, command.quote_version) != (head.quote_id, head.version):
            raise ValueError("new decisions and corrections require the current revision")
        recording = EntryRecording(command.recorded_by_actor_id, recorded_at, command.reason)
        entry = QuoteDecisionEntry(
            command,
            self.sequence + 1,
            recording,
            _line_decisions(head, command),
            price_selection(head, command.approved_line_ids),
        )
        updated = QuoteDecisionLedger(self.history, (*self.entries, entry))
        event = _event_for(entry)
        return QuoteDecisionResult(updated, entry, updated.projection, event, False)

    def revise(
        self,
        *,
        lines: Sequence[QuoteLine],
        expected_head_id: str,
        expected_head_version: int,
        expected_decision_sequence: int,
        quote_id: str | None = None,
        now: datetime,
    ) -> QuoteDecisionRevision:
        self._check_head(expected_head_id, expected_head_version, expected_decision_sequence)
        timestamp = _timestamp(now)
        if self.entries and timestamp < self.entries[-1].recording.recorded_at:
            raise ValueError("revision cannot precede latest decision recording")
        pair = self.history.head.revise(lines=lines, quote_id=quote_id, now=timestamp)
        history = QuoteHistory((*self.history.revisions[:-1], pair.predecessor, pair.successor))
        return QuoteDecisionRevision(QuoteDecisionLedger(history, self.entries), pair)


@dataclass(frozen=True, slots=True)
class QuoteDecisionResult:
    ledger: QuoteDecisionLedger
    entry: QuoteDecisionEntry
    projection: DecisionProjection
    event: QuoteDecisionRecorded | None
    replayed: bool

    def __post_init__(self) -> None:
        if (
            type(self.ledger) is not QuoteDecisionLedger
            or type(self.entry) is not QuoteDecisionEntry
        ):
            raise ValueError("result requires typed ledger and receipt")
        if type(self.projection) is not DecisionProjection or type(self.replayed) is not bool:
            raise ValueError("result requires typed projection and replay flag")
        if self.event is not None and type(self.event) is not QuoteDecisionRecorded:
            raise ValueError("result requires a typed event or none")


@dataclass(frozen=True, slots=True)
class QuoteDecisionRevision:
    ledger: QuoteDecisionLedger
    revision: QuoteRevision
    event: None = None


@dataclass(frozen=True, slots=True)
class InitialTransitionPlan:
    order_id: str
    expected_order_version: int
    lineage_id: str
    expected_head_id: str
    expected_head_version: int
    decision_id: str
    expected_decision_sequence: int
    action: str


def plan_initial_transition(
    ledger: QuoteDecisionLedger,
    order: ServiceOrder,
    result: QuoteDecisionResult,
) -> InitialTransitionPlan:
    """A snapshot-only plan; its future consumer must revalidate all preconditions."""
    if (
        type(ledger) is not QuoteDecisionLedger
        or type(order) is not ServiceOrder
        or (type(result) is not QuoteDecisionResult)
    ):
        raise ValueError("planner requires typed current snapshots and result")
    head = ledger.history.head
    if (order.organization_id, order.location_id, order.order_id) != (
        head.organization_id,
        head.location_id,
        head.order_id,
    ) or order.state != OrderState.DIAGNOSIS.value:
        raise ValueError("initial transition requires matching scope and DIAGNOSIS")
    _integer(order.version, "order version", minimum=1)
    entry = result.entry
    if (
        result.replayed is not False
        or result.event != _event_for(entry)
        or not ledger.entries
        or result.ledger != ledger
        or ledger.entries[-1] != entry
        or result.projection != ledger.projection
        or entry.command.mode != "initial"
        or entry.command.quote_id != head.quote_id
        or ledger.projection.decision_id != entry.command.decision_id
        or entry.command.outcome not in ("APPROVE", "PARTIAL", "REJECT")
    ):
        raise ValueError("initial transition requires fresh current applicable decision result")
    return InitialTransitionPlan(
        order.order_id,
        order.version,
        ledger.history.lineage_id,
        head.quote_id,
        head.version,
        entry.command.decision_id,
        ledger.sequence,
        "reject" if entry.command.outcome == "REJECT" else "authorize",
    )
