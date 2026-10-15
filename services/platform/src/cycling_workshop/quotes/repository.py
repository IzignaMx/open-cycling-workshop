"""Inert, caller-owned quote storage operations under existing writer admission.

This is not an authorization service: a future application boundary must check
explicit quote grants and activation policy before calling it. There are no HTTP
routes or sync mutations here. The existing writer barrier supplies org→actor
locks; this repository then locks order→lineage and never commits. PostgreSQL
READ COMMITTED is supported; SQLite proves functional behavior, not concurrency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlite3 import Connection as SQLiteConnection
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session

from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.events.outbox import enqueue_outbox
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.inventory.models import ProductRecord
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    QuoteRepositoryCommand,
    RecordQuoteDecisionCommand,
    command_from_proof,
    operation_proof,
)
from cycling_workshop.quotes.decisions import QuoteDecisionLedger
from cycling_workshop.quotes.domain import PartLine, Quote
from cycling_workshop.quotes.models import (
    QuoteDecisionRecord,
    QuoteLineageRecord,
    QuoteLineRecord,
    QuoteLineTargetRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.quotes.reconstruction import (
    QuoteIntegrityError as QuoteIntegrityError,
)
from cycling_workshop.quotes.reconstruction import (
    QuoteReceipt,
    QuoteSnapshot,
    advance,
    event_payload,
    event_type,
    logical_record,
    reconstruct,
)
from cycling_workshop.quotes.storage import (
    _document,
    _id,
    _timestamp,
    canonical_bytes,
    encode_entry,
    encode_lines,
    encode_quote,
    validate_history_bytes,
)
from cycling_workshop.service_orders.models import ServiceOrderRecord


class QuoteConflictError(ValueError):
    """New operation cannot apply to the supplied current scope or cursor."""


@dataclass(frozen=True, slots=True)
class QuoteOrderProjection:
    order_id: str
    organization_id: str
    location_id: str
    state: str
    version: int


@dataclass(frozen=True, slots=True)
class QuoteRepositoryResult:
    receipt: QuoteReceipt
    ledger: QuoteDecisionLedger
    order: QuoteOrderProjection
    replayed: bool


class QuoteRepository:
    def __init__(self, session: Session):
        self.session = session

    def _admitted(
        self, organization_id: str, location_id: str, actor_id: str | None = None
    ) -> None:
        marker = self.session.info.get("ocwp_write_admission")
        if not isinstance(marker, tuple) or len(marker) != 3:
            raise PermissionError("quote storage requires current writer admission")
        transaction, principal, admission = marker
        if (
            transaction is None
            or transaction is not self.session.get_transaction()
            or not isinstance(principal, Principal)
            or not isinstance(admission, WriteAdmission)
        ):
            raise PermissionError("quote storage admission belongs to another transaction")
        if (
            principal.organization_id != organization_id
            or principal.location_id not in (None, location_id)
            or (actor_id is not None and principal.user_id != actor_id)
        ):
            raise PermissionError("quote storage caller scope denied")
        admission.check_expiry(principal)

    def _order(self, organization_id: str, location_id: str, order_id: str) -> ServiceOrderRecord:
        for value in (organization_id, location_id, order_id):
            _id(value)
        row = self.session.scalar(
            select(ServiceOrderRecord)
            .where(
                ServiceOrderRecord.id == order_id,
                ServiceOrderRecord.organization_id == organization_id,
                ServiceOrderRecord.location_id == location_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise QuoteConflictError("scoped order not found")
        return row

    def _lineage(self, organization_id: str, order_id: str) -> QuoteLineageRecord | None:
        return self.session.scalar(
            select(QuoteLineageRecord)
            .where(
                QuoteLineageRecord.organization_id == organization_id,
                QuoteLineageRecord.order_id == order_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _load(self, lineage: QuoteLineageRecord) -> QuoteSnapshot:
        scope = lineage.lineage_id

        def rows[
            T: (QuoteRevisionRecord, QuoteLineRecord, QuoteDecisionRecord, QuoteOperationRecord)
        ](model: type[T], maximum: int, order: InstrumentedAttribute[int]) -> list[T]:
            return list(
                self.session.scalars(
                    select(model)
                    .where(model.lineage_id == scope)
                    .order_by(order)
                    .limit(maximum + 1)
                    .execution_options(populate_existing=True)
                )
            )

        revisions = rows(QuoteRevisionRecord, 32, QuoteRevisionRecord.version)
        lines = rows(QuoteLineRecord, 3200, QuoteLineRecord.position)
        decisions = rows(QuoteDecisionRecord, 128, QuoteDecisionRecord.sequence)
        operations = rows(QuoteOperationRecord, 160, QuoteOperationRecord.ordinal)
        targets = list(
            self.session.scalars(
                select(QuoteLineTargetRecord)
                .join(
                    QuoteRevisionRecord,
                    QuoteRevisionRecord.quote_id == QuoteLineTargetRecord.revision_id,
                )
                .where(QuoteRevisionRecord.lineage_id == scope)
                .limit(32001)
            )
        )
        outboxes = list(
            self.session.scalars(
                select(OutboxRecord)
                .join(
                    QuoteOperationRecord,
                    QuoteOperationRecord.quote_outbox_id == OutboxRecord.event_id,
                )
                .where(QuoteOperationRecord.lineage_id == scope)
                .limit(161)
                .execution_options(populate_existing=True)
            )
        )
        return reconstruct(lineage, revisions, lines, targets, decisions, operations, outboxes)

    def load(self, organization_id: str, location_id: str, order_id: str) -> QuoteSnapshot | None:
        """Read a complete locked history; callers still own grant authorization."""
        self._admitted(organization_id, location_id)
        self._order(organization_id, location_id, order_id)
        lineage = self._lineage(organization_id, order_id)
        snapshot = self._load(lineage) if lineage is not None else None
        self._admitted(organization_id, location_id)
        return snapshot

    def apply(
        self, command: QuoteRepositoryCommand, *, recorded_at: datetime
    ) -> QuoteRepositoryResult:
        # Reconstruct the immutable proof before examining storage; reject forged
        # dataclass internals just like malformed commands from future adapters.
        proof = operation_proof(command)
        command = command_from_proof(proof)
        now = _timestamp(_document(recorded_at))
        self._admitted(command.organization_id, command.location_id, command.actor_id)
        order = self._order(command.organization_id, command.location_id, command.order_id)
        lineage = self._lineage(command.organization_id, command.order_id)
        snapshot = self._load(lineage) if lineage is not None else None
        # Never fetch a foreign order/location proof merely because its operation
        # ID collides with this request. Org-wide uniqueness is handled below with
        # the same non-disclosing constraint conflict as other scoped identities.
        prior = self.session.scalar(
            select(QuoteOperationRecord)
            .join(
                QuoteLineageRecord, QuoteLineageRecord.lineage_id == QuoteOperationRecord.lineage_id
            )
            .where(
                QuoteOperationRecord.organization_id == command.organization_id,
                QuoteOperationRecord.operation_id == command.operation_id,
                QuoteLineageRecord.organization_id == command.organization_id,
                QuoteLineageRecord.location_id == command.location_id,
                QuoteLineageRecord.order_id == command.order_id,
            )
            .execution_options(populate_existing=True)
        )
        if prior is not None:
            if canonical_bytes(prior.proof) != canonical_bytes(proof) or snapshot is None:
                raise QuoteConflictError("operation identity reused with different semantic proof")
            receipt = next(
                (item for item in snapshot.receipts if item.operation_id == command.operation_id),
                None,
            )
            if receipt is None:
                raise QuoteIntegrityError("receipt is outside its recorded lineage")
            self._admitted(command.organization_id, command.location_id, command.actor_id)
            return self._result(receipt, snapshot.ledger, order, True)
        if type(order.version) is not int or order.version != command.expected_order_version:
            raise QuoteConflictError("stale order version")
        try:
            ledger = advance(snapshot.ledger if snapshot else None, command, now)
        except ValueError as error:
            raise QuoteConflictError(str(error)) from error
        if not isinstance(command, RecordQuoteDecisionCommand):
            for line in ledger.history.head.lines:
                if (
                    isinstance(line, PartLine)
                    and self.session.scalar(
                        select(ProductRecord.id).where(
                            ProductRecord.id == line.product_id,
                            ProductRecord.organization_id == command.organization_id,
                            ProductRecord.location_id == command.location_id,
                        )
                    )
                    is None
                ):
                    raise QuoteConflictError("new quote part reference is outside order scope")
        # One joined proof/result per logical operation, including the candidate.
        logical = []
        prefix: QuoteDecisionLedger | None = None
        for receipt in snapshot.receipts if snapshot else ():
            prefix = advance(prefix, receipt.command, receipt.recorded_at)
            logical.append(logical_record(receipt.command, prefix))
        logical.append(logical_record(command, ledger))
        validate_history_bytes(logical)
        # A local savepoint rolls back this operation on any late serialization,
        # constraint or admission failure. The caller still owns outer commit.
        connection = self.session.connection()
        driver = connection.connection.driver_connection
        if isinstance(driver, SQLiteConnection) and not driver.in_transaction:
            # sqlite3 legacy SELECT does not begin a real transaction; otherwise
            # RELEASE of the first SAVEPOINT would commit behind the caller.
            connection.exec_driver_sql("BEGIN")
        try:
            with self.session.begin_nested():
                if isinstance(command, CreateQuoteCommand):
                    lineage = QuoteLineageRecord(
                        lineage_id=command.lineage_id,
                        organization_id=command.organization_id,
                        location_id=command.location_id,
                        order_id=command.order_id,
                        currency=command.currency,
                        root_quote_id=command.quote_id,
                        head_quote_id=command.quote_id,
                        head_version=1,
                        decision_sequence=0,
                    )
                    self.session.add(lineage)
                    self.session.flush()
                if isinstance(command, RecordQuoteDecisionCommand):
                    entry = ledger.entries[-1]
                    document = encode_entry(entry)
                    self.session.add(
                        QuoteDecisionRecord(
                            decision_id=command.operation_id,
                            lineage_id=command.lineage_id,
                            organization_id=command.organization_id,
                            quote_id=command.quote_id,
                            quote_version=command.command.quote_version,
                            sequence=entry.sequence,
                            actor_id=command.actor_id,
                            recorded_at=now,
                            reason=command.command.reason,
                            supersedes_entry_id=command.command.supersedes_entry_id,
                            line_decisions=cast(list[object], document["line_decisions"]),
                            pricing=cast(dict[str, object], document["pricing"]),
                        )
                    )
                    self.session.flush()
                else:
                    self._insert_revision(ledger.history.head, command.actor_id, command.lineage_id)
                head = ledger.history.head
                if not isinstance(command, CreateQuoteCommand):
                    updated = self.session.execute(
                        update(QuoteLineageRecord)
                        .where(
                            QuoteLineageRecord.lineage_id == command.lineage_id,
                            QuoteLineageRecord.organization_id == command.organization_id,
                            QuoteLineageRecord.head_quote_id == command.expected_head_id,
                            QuoteLineageRecord.head_version == command.expected_head_version,
                            QuoteLineageRecord.decision_sequence
                            == command.expected_decision_sequence,
                        )
                        .values(
                            head_quote_id=head.quote_id,
                            head_version=head.version,
                            decision_sequence=ledger.sequence,
                        )
                        .returning(QuoteLineageRecord.lineage_id)
                    )
                    if updated.scalar_one_or_none() != command.lineage_id:
                        raise QuoteConflictError("quote cursor changed before append")
                outbox_id = enqueue_outbox(
                    self.session,
                    event_type=event_type(command),
                    aggregate_type="quote",
                    aggregate_id=command.lineage_id,
                    organization_id=command.organization_id,
                    location_id=command.location_id,
                    payload=event_payload(command, ledger),
                    occurred_at=now,
                )
                self.session.flush()
                ordinal = head.version + ledger.sequence
                self.session.add(
                    QuoteOperationRecord(
                        organization_id=command.organization_id,
                        operation_id=command.operation_id,
                        lineage_id=command.lineage_id,
                        kind=cast(str, proof["kind"]),
                        quote_id=head.quote_id,
                        quote_version=head.version,
                        resulting_decision_sequence=ledger.sequence,
                        ordinal=ordinal,
                        decision_id=command.operation_id
                        if isinstance(command, RecordQuoteDecisionCommand)
                        else None,
                        proof_version=1,
                        proof=cast(dict[str, object], proof),
                        actor_id=command.actor_id,
                        recorded_at=now,
                        quote_outbox_id=outbox_id,
                    )
                )
                self.session.flush()
                self._admitted(command.organization_id, command.location_id, command.actor_id)
                receipt = QuoteReceipt(
                    command, head.quote_id, head.version, ledger.sequence, ordinal, now, outbox_id
                )
                result = self._result(receipt, ledger, order, False)
        except IntegrityError:
            raise QuoteConflictError(
                "quote operation conflicts with stored identity or scope"
            ) from None
        return result

    @staticmethod
    def _result(
        receipt: QuoteReceipt,
        ledger: QuoteDecisionLedger,
        order: ServiceOrderRecord,
        replayed: bool,
    ) -> QuoteRepositoryResult:
        return QuoteRepositoryResult(
            receipt,
            ledger,
            QuoteOrderProjection(
                order.id, order.organization_id, order.location_id, order.state, order.version
            ),
            replayed,
        )

    def _insert_revision(self, quote: Quote, actor_id: str, lineage_id: str) -> None:
        document = encode_quote(quote)
        totals = quote.totals
        self.session.add(
            QuoteRevisionRecord(
                quote_id=quote.quote_id,
                lineage_id=lineage_id,
                organization_id=quote.organization_id,
                version=quote.version,
                predecessor_id=quote.revises_quote_id,
                created_at=quote.created_at,
                actor_id=actor_id,
                subtotal_minor=totals.subtotal_minor,
                discount_minor=totals.discount_minor,
                tax_minor=totals.tax_minor,
                total_minor=totals.total_minor,
                line_amounts=cast(
                    list[object], cast(dict[str, object], document["totals"])["line_amounts"]
                ),
            )
        )
        self.session.flush()
        edges: list[QuoteLineTargetRecord] = []
        for position, value in enumerate(encode_lines(quote.lines)):
            row = cast(dict[str, object], value).copy()
            targets = cast(list[str], row.pop("base_line_ids", row.pop("scope_line_ids", [])))
            self.session.add(
                QuoteLineRecord(
                    revision_id=quote.quote_id,
                    lineage_id=lineage_id,
                    organization_id=quote.organization_id,
                    position=position,
                    **row,
                )
            )
            edges.extend(
                QuoteLineTargetRecord(
                    revision_id=quote.quote_id,
                    source_line_id=cast(str, row["line_id"]),
                    target_line_id=target,
                )
                for target in targets
            )
        self.session.flush()
        self.session.add_all(edges)
        self.session.flush()
