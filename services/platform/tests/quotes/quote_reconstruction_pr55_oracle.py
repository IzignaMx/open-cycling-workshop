"""Strict bounded reconstruction of the six quote tables and their outbox receipts.

Financial snapshots are checked against their immutable semantic commands, in
contiguous operation order. Current inventory prices and customer data are never
substituted into history. Operational order-effect tuples are reserved for the
separately reviewed activation slice and fail closed in this repository version.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    QuoteRepositoryCommand,
    RecordQuoteDecisionCommand,
    ReviseQuoteCommand,
    command_from_proof,
    operation_proof,
)
from cycling_workshop.quotes.decisions import (
    EntryRecording,
    QuoteDecisionEntry,
    QuoteDecisionLedger,
    _admit,
    _line_decisions,
    price_selection,
)
from cycling_workshop.quotes.domain import Quote
from cycling_workshop.quotes.history import QuoteHistory
from cycling_workshop.quotes.models import (
    QuoteDecisionRecord,
    QuoteLineageRecord,
    QuoteLineRecord,
    QuoteLineTargetRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.quotes.storage import (
    Document,
    JsonValue,
    _document,
    _history_byte_count,
    _id,
    _integer,
    _record,
    canonical_bytes,
    decode_entry,
    decode_quote,
    encode_entry,
    encode_quote,
    validate_storage_ledger,
)


class QuoteIntegrityError(ValueError):
    """Stored quote evidence is incomplete, inconsistent, or unsupported."""


@dataclass(frozen=True, slots=True)
class QuoteReceipt:
    command: QuoteRepositoryCommand
    quote_id: str
    quote_version: int
    decision_sequence: int
    ordinal: int
    recorded_at: datetime
    quote_outbox_id: str

    @property
    def operation_id(self) -> str:
        return self.command.operation_id


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    ledger: QuoteDecisionLedger
    receipts: tuple[QuoteReceipt, ...]


def utc(value: datetime) -> datetime:
    # SQLite drops timezone information from DateTime(timezone=True). All writes
    # have already been normalized to UTC; PostgreSQL returns aware timestamps.
    if type(value) is not datetime:
        raise ValueError("stored datetime required")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def advance(
    ledger: QuoteDecisionLedger | None, command: QuoteRepositoryCommand, now: datetime
) -> QuoteDecisionLedger:
    if isinstance(command, CreateQuoteCommand):
        if ledger is not None:
            raise ValueError("order already has a quote lineage")
        quote = Quote.for_order(
            quote_id=command.quote_id,
            organization_id=command.organization_id,
            location_id=command.location_id,
            order_id=command.order_id,
            currency=command.currency,
            lines=command.lines,
            now=now,
        )
        result = QuoteDecisionLedger(QuoteHistory((quote,)))
    else:
        if ledger is None:
            raise ValueError("quote lineage missing")
        head = ledger.history.head
        if (command.organization_id, command.location_id, command.order_id, command.lineage_id) != (
            head.organization_id,
            head.location_id,
            head.order_id,
            ledger.history.lineage_id,
        ):
            raise ValueError("command quote scope mismatch")
        if isinstance(command, ReviseQuoteCommand):
            result = ledger.revise(
                lines=command.lines,
                expected_head_id=command.expected_head_id,
                expected_head_version=command.expected_head_version,
                expected_decision_sequence=command.expected_decision_sequence,
                quote_id=command.quote_id,
                now=now,
            ).ledger
        else:
            decision = ledger.record(command.command, recorded_at=now)
            if decision.replayed:
                raise ValueError("duplicate decision in operation history")
            result = decision.ledger
    validate_storage_ledger(result)
    return result


def event_payload(
    command: QuoteRepositoryCommand, ledger: QuoteDecisionLedger
) -> dict[str, object]:
    """Privacy-minimized identity/timeline metadata, never customer evidence."""
    entry = ledger.entries[-1] if isinstance(command, RecordQuoteDecisionCommand) else None
    return _event_payload(
        command, ledger.history.head, ledger.history.lineage_id, ledger.sequence, entry
    )


def _event_payload(
    command: QuoteRepositoryCommand,
    head: Quote,
    lineage_id: str,
    sequence: int,
    entry: QuoteDecisionEntry | None,
) -> dict[str, object]:
    if isinstance(command, RecordQuoteDecisionCommand) != (entry is not None):
        raise ValueError("quote event result kind mismatch")
    result: dict[str, object] = dict(
        operation_id=command.operation_id,
        organization_id=head.organization_id,
        location_id=head.location_id,
        kind="decision"
        if isinstance(command, RecordQuoteDecisionCommand)
        else "create"
        if isinstance(command, CreateQuoteCommand)
        else "revise",
        lineage_id=lineage_id,
        order_id=head.order_id,
        quote_id=head.quote_id,
        quote_version=head.version,
        decision_sequence=sequence,
        ordinal=head.version + sequence,
    )
    pricing = entry.pricing if entry is not None else head.totals
    result["pricing"] = dict(
        currency=head.currency,
        subtotal_minor=pricing.subtotal_minor,
        discount_minor=pricing.discount_minor,
        tax_minor=pricing.tax_minor,
        total_minor=pricing.total_minor,
    )
    if isinstance(command, RecordQuoteDecisionCommand) and entry is not None:
        result.update(
            decision_id=command.operation_id,
            domain_event_id=command.operation_id,
            approved_line_ids=list(command.command.approved_line_ids),
            declined_line_ids=[line.line_id for line in entry.line_decisions if not line.approved],
            mode=command.command.mode,
            outcome=command.command.outcome,
            evidence_entry_id=command.operation_id,
            supersedes_entry_id=command.command.supersedes_entry_id,
        )
    return result


def event_type(command: QuoteRepositoryCommand) -> str:
    return (
        "quote.decision_recorded"
        if isinstance(command, RecordQuoteDecisionCommand)
        else "quote.created"
        if isinstance(command, CreateQuoteCommand)
        else "quote.revised"
    )


def logical_record(command: QuoteRepositoryCommand, ledger: QuoteDecisionLedger) -> Document:
    entry = ledger.entries[-1] if isinstance(command, RecordQuoteDecisionCommand) else None
    return _logical_record(command, ledger.history.head, entry)


def _logical_record(
    command: QuoteRepositoryCommand,
    head: Quote,
    entry: QuoteDecisionEntry | None,
) -> Document:
    if isinstance(command, RecordQuoteDecisionCommand) != (entry is not None):
        raise ValueError("quote logical result kind mismatch")
    if entry is not None:
        result = encode_entry(entry)
        del result["command"]  # Exactly one canonical inner proof, not two copies.
    else:
        result = encode_quote(head)
    return _record({"proof": operation_proof(command), "result": result})


def _revision_document(
    row: QuoteRevisionRecord,
    lineage: QuoteLineageRecord,
    lines: list[QuoteLineRecord],
    targets: list[QuoteLineTargetRecord],
    successor: QuoteRevisionRecord | None,
) -> Document:
    line_documents: list[JsonValue] = []
    fields = (
        "product_id",
        "minutes",
        "hourly_rate_minor",
        "quantity",
        "unit_price_minor",
        "rate_bps",
        "amount_minor",
    )
    used = {
        "labor": ("minutes", "hourly_rate_minor"),
        "part": ("product_id", "quantity", "unit_price_minor"),
        "tax": ("rate_bps",),
        "discount": ("amount_minor",),
    }
    for position, line in enumerate(sorted(lines, key=lambda item: item.position)):
        if (
            line.position != position
            or type(line.position) is not int
            or (line.organization_id, line.lineage_id, line.revision_id)
            != (lineage.organization_id, lineage.lineage_id, row.quote_id)
        ):
            raise ValueError("invalid quote line position or scope")
        names = used.get(line.kind)
        if names is None or any(
            getattr(line, name) is not None for name in fields if name not in names
        ):
            raise ValueError("invalid stored line discriminator")
        doc: Document = {
            "kind": line.kind,
            "line_id": line.line_id,
            "description": line.description,
        }
        doc.update({name: getattr(line, name) for name in names})
        edges = sorted(
            edge.target_line_id for edge in targets if edge.source_line_id == line.line_id
        )
        if line.kind in ("tax", "discount"):
            doc["base_line_ids" if line.kind == "tax" else "scope_line_ids"] = list(edges)
        elif edges:
            raise ValueError("charge line cannot have pricing targets")
        line_documents.append(doc)
    line_ids = {line.line_id for line in lines}
    if any(
        edge.revision_id != row.quote_id
        or edge.source_line_id not in line_ids
        or edge.target_line_id not in line_ids
        for edge in targets
    ):
        raise ValueError("orphaned pricing target")
    document: dict[str, object] = dict(
        quote_id=row.quote_id,
        organization_id=lineage.organization_id,
        location_id=lineage.location_id,
        order_id=lineage.order_id,
        lines=line_documents,
        currency=lineage.currency,
        version=row.version,
        created_at=_document(utc(row.created_at)),
        revises_quote_id=row.predecessor_id,
        superseded_at=_document(utc(successor.created_at)) if successor else None,
        superseded_by=successor.quote_id if successor else None,
        totals=dict(
            subtotal_minor=row.subtotal_minor,
            discount_minor=row.discount_minor,
            tax_minor=row.tax_minor,
            total_minor=row.total_minor,
            line_amounts=row.line_amounts,
        ),
    )
    return _record(document)


def reconstruct(
    lineage: QuoteLineageRecord,
    revisions: list[QuoteRevisionRecord],
    lines: list[QuoteLineRecord],
    targets: list[QuoteLineTargetRecord],
    decisions: list[QuoteDecisionRecord],
    operations: list[QuoteOperationRecord],
    outboxes: list[OutboxRecord],
) -> QuoteSnapshot:
    return _reconstruct_with_bytes(
        lineage, revisions, lines, targets, decisions, operations, outboxes
    )[0]


def _reconstruct_with_bytes(
    lineage: QuoteLineageRecord,
    revisions: list[QuoteRevisionRecord],
    lines: list[QuoteLineRecord],
    targets: list[QuoteLineTargetRecord],
    decisions: list[QuoteDecisionRecord],
    operations: list[QuoteOperationRecord],
    outboxes: list[OutboxRecord],
) -> tuple[QuoteSnapshot, int]:
    try:
        return _reconstruct(lineage, revisions, lines, targets, decisions, operations, outboxes)
    except (ValueError, TypeError, AttributeError, KeyError, OverflowError) as error:
        raise QuoteIntegrityError("stored quote history is invalid") from error


def _reconstruct(
    lineage: QuoteLineageRecord,
    revisions: list[QuoteRevisionRecord],
    lines: list[QuoteLineRecord],
    targets: list[QuoteLineTargetRecord],
    decisions: list[QuoteDecisionRecord],
    operations: list[QuoteOperationRecord],
    outboxes: list[OutboxRecord],
) -> tuple[QuoteSnapshot, int]:
    _id(lineage.lineage_id, generated=True)
    if (
        lineage.root_quote_id != lineage.lineage_id
        or not revisions
        or len(revisions) > 32
        or len(decisions) > 128
    ):
        raise ValueError("invalid lineage root or history bounds")
    if len(operations) != len(revisions) + len(decisions) or len(outboxes) != len(operations):
        raise ValueError("every result requires one operation and quote outbox")
    revision_map = {row.quote_id: row for row in revisions}
    decision_map = {row.decision_id: row for row in decisions}
    outbox_map = {row.event_id: row for row in outboxes}
    if (
        len(revision_map) != len(revisions)
        or len(decision_map) != len(decisions)
        or len(outbox_map) != len(outboxes)
    ):
        raise ValueError("duplicate stored identities")
    if any(line.revision_id not in revision_map for line in lines) or any(
        edge.revision_id not in revision_map for edge in targets
    ):
        raise ValueError("orphaned quote lines or targets")
    stored_quotes = []
    for index, row in enumerate(revisions):
        if (row.organization_id, row.lineage_id, row.version) != (
            lineage.organization_id,
            lineage.lineage_id,
            index + 1,
        ):
            raise ValueError("revision scope or sequence mismatch")
        doc = _revision_document(
            row,
            lineage,
            [line for line in lines if line.revision_id == row.quote_id],
            [edge for edge in targets if edge.revision_id == row.quote_id],
            revisions[index + 1] if index + 1 < len(revisions) else None,
        )
        stored_quotes.append(decode_quote(doc))
    stored_history = QuoteHistory(tuple(stored_quotes))
    head: Quote | None = None
    predecessors: list[Quote] = []
    entries: list[QuoteDecisionEntry] = []
    latest: dict[str, QuoteDecisionEntry] = {}
    customer_times: dict[str, datetime] = {}
    receipts: list[QuoteReceipt] = []
    logical: list[Document] = []
    for ordinal, operation in enumerate(operations, 1):
        for value in (
            operation.proof_version,
            operation.ordinal,
            operation.quote_version,
            operation.resulting_decision_sequence,
        ):
            _integer(value)
        command = command_from_proof(operation.proof)
        now = utc(operation.recorded_at)
        _id(operation.quote_outbox_id, generated=True)
        if (
            operation.organization_id,
            operation.lineage_id,
            operation.operation_id,
            operation.actor_id,
            operation.proof_version,
            operation.ordinal,
        ) != (
            lineage.organization_id,
            lineage.lineage_id,
            command.operation_id,
            command.actor_id,
            1,
            ordinal,
        ):
            raise ValueError("operation scope, actor, version or ordinal mismatch")
        if any(
            value is not None
            for value in (
                operation.order_event_id,
                operation.resulting_order_version,
                operation.change_cursor,
                operation.order_outbox_id,
            )
        ):
            raise ValueError("operational quote effects are not supported before activation")
        entry: QuoteDecisionEntry | None = None
        sequence = len(entries)
        if (command.organization_id, command.location_id, command.order_id, command.lineage_id) != (
            lineage.organization_id,
            lineage.location_id,
            lineage.order_id,
            lineage.lineage_id,
        ):
            raise ValueError("command quote scope mismatch")
        if isinstance(command, CreateQuoteCommand):
            if head is not None:
                raise ValueError("order already has a quote lineage")
            head = Quote.for_order(
                quote_id=command.quote_id,
                organization_id=command.organization_id,
                location_id=command.location_id,
                order_id=command.order_id,
                currency=command.currency,
                lines=command.lines,
                now=now,
            )
        else:
            if head is None:
                raise ValueError("quote lineage missing")
            if (
                command.expected_head_id,
                command.expected_head_version,
                command.expected_decision_sequence,
            ) != (head.quote_id, head.version, sequence):
                raise ValueError("stale quote head or decision sequence")
            if isinstance(command, ReviseQuoteCommand):
                if entries and now < entries[-1].recording.recorded_at:
                    raise ValueError("revision cannot precede latest decision recording")
                if not 1 <= head.version <= len(stored_quotes):
                    raise ValueError("observed quote prefix is outside stored history")
                pair = head.revise(lines=command.lines, quote_id=command.quote_id, now=now)
                if pair.predecessor != stored_quotes[head.version - 1]:
                    raise ValueError("generated predecessor differs from stored history")
                encode_quote(pair.predecessor)
                predecessors.append(pair.predecessor)
                head = pair.successor
            else:
                proof = command.command
                if (proof.quote_id, proof.quote_version) != (head.quote_id, head.version):
                    raise ValueError("new decisions require the current revision")
                recording = EntryRecording(proof.recorded_by_actor_id, now, proof.reason)
                if entries and now < entries[-1].recording.recorded_at:
                    raise ValueError("decision recording time cannot move backward")
                _admit(
                    head,
                    proof,
                    recording,
                    latest.get(head.quote_id),
                    customer_times.get(head.quote_id),
                )
                entry = QuoteDecisionEntry(
                    proof,
                    sequence + 1,
                    recording,
                    _line_decisions(head, proof),
                    price_selection(head, proof.approved_line_ids),
                )
                encode_entry(entry)
                entries.append(entry)
                latest[head.quote_id] = entry
                if proof.evidence is not None:
                    customer_times[head.quote_id] = proof.evidence.decided_at
                sequence += 1
        if not isinstance(command, RecordQuoteDecisionCommand):
            if head.version > len(stored_quotes) or head != replace(
                stored_quotes[head.version - 1], superseded_at=None, superseded_by=None
            ):
                raise ValueError("generated quote differs from stored history")
            encode_quote(head)
        if (operation.quote_id, operation.quote_version, operation.resulting_decision_sequence) != (
            head.quote_id,
            head.version,
            sequence,
        ):
            raise ValueError("receipt result disagrees with operation proof")
        if isinstance(command, RecordQuoteDecisionCommand):
            decision_row = decision_map.pop(command.operation_id)
            _integer(decision_row.quote_version, 1)
            if (
                operation.kind != "decision"
                or operation.decision_id != command.operation_id
                or (
                    decision_row.lineage_id,
                    decision_row.organization_id,
                    decision_row.quote_id,
                    decision_row.quote_version,
                    decision_row.supersedes_entry_id,
                )
                != (
                    lineage.lineage_id,
                    lineage.organization_id,
                    head.quote_id,
                    head.version,
                    command.command.supersedes_entry_id,
                )
            ):
                raise ValueError("decision result association mismatch")
            actual = decode_entry(
                dict(
                    command=operation_proof(command)["command"],
                    sequence=decision_row.sequence,
                    recording=dict(
                        recorded_by_actor_id=decision_row.actor_id,
                        recorded_at=_document(utc(decision_row.recorded_at)),
                        reason=decision_row.reason,
                    ),
                    line_decisions=decision_row.line_decisions,
                    pricing=decision_row.pricing,
                )
            )
            if actual != entry:
                raise ValueError("decision evidence result differs from proof")
        else:
            row_revision = revision_map.pop(command.quote_id)
            if (
                operation.kind
                != ("create" if isinstance(command, CreateQuoteCommand) else "revise")
                or operation.decision_id is not None
                or row_revision.actor_id != command.actor_id
                or utc(row_revision.created_at) != now
            ):
                raise ValueError("revision receipt association mismatch")
        outbox = outbox_map.pop(operation.quote_outbox_id)
        if (
            outbox.event_type,
            outbox.aggregate_type,
            outbox.aggregate_id,
            outbox.organization_id,
            outbox.location_id,
            utc(outbox.occurred_at),
        ) != (
            event_type(command),
            "quote",
            lineage.lineage_id,
            lineage.organization_id,
            lineage.location_id,
            now,
        ) or canonical_bytes(outbox.payload) != canonical_bytes(
            _event_payload(command, head, lineage.lineage_id, sequence, entry)
        ):
            raise ValueError("quote outbox disagrees with receipt")
        logical.append(_logical_record(command, head, entry))
        receipts.append(
            QuoteReceipt(
                command,
                head.quote_id,
                head.version,
                sequence,
                ordinal,
                now,
                operation.quote_outbox_id,
            )
        )
    if (
        head is None
        or revision_map
        or decision_map
        or outbox_map
        or (*predecessors, head) != stored_history.revisions
    ):
        raise ValueError("incomplete quote operation history")
    ledger = QuoteDecisionLedger(stored_history, tuple(entries))
    validate_storage_ledger(ledger)
    if (lineage.head_quote_id, lineage.head_version, lineage.decision_sequence) != (
        ledger.history.head.quote_id,
        ledger.history.head.version,
        ledger.sequence,
    ):
        raise ValueError("lineage cursor disagrees with history")
    for value in (lineage.head_version, lineage.decision_sequence):
        _integer(value)
    size = _history_byte_count(logical)
    return QuoteSnapshot(ledger, tuple(receipts)), size
