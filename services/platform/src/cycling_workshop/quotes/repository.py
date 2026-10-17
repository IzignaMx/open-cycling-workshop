"""Inert, caller-owned quote storage operations under existing writer admission.

This is not an authorization service: a future application boundary must check
explicit quote grants and activation policy before calling it. There are no HTTP
routes or sync mutations here. The existing writer barrier supplies org→actor
locks; this repository then locks order→lineage and never commits. PostgreSQL
READ COMMITTED is supported; SQLite proves functional behavior, not concurrency.
"""

from __future__ import annotations

from collections.abc import Callable
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
from cycling_workshop.quotes.decisions import QuoteDecisionLedger, QuoteDecisionResult
from cycling_workshop.quotes.domain import PartLine, Quote
from cycling_workshop.quotes.effects import QuoteOrderEffects, _validate_order_effects
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
    _advance_with_result,
    _noop,
    _reconstruct_with_bytes,
    advance,
    event_payload,
    event_type,
    logical_record,
)
from cycling_workshop.quotes.storage import (
    _check_history_byte_count,
    _document,
    _id,
    _timestamp,
    canonical_bytes,
    encode_entry,
    encode_lines,
    encode_quote,
)
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord


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
        return self._load_with_bytes(lineage)[0]

    def _load_with_bytes(
        self, lineage: QuoteLineageRecord, *, checkpoint: Callable[[], None] = _noop
    ) -> tuple[QuoteSnapshot, int]:
        scope = lineage.lineage_id

        def rows[
            T: (QuoteRevisionRecord, QuoteLineRecord, QuoteDecisionRecord, QuoteOperationRecord)
        ](model: type[T], maximum: int, order: InstrumentedAttribute[int]) -> list[T]:
            checkpoint()
            result = list(
                self.session.scalars(
                    select(model)
                    .where(model.lineage_id == scope)
                    .order_by(order)
                    .limit(maximum + 1)
                    .execution_options(populate_existing=True)
                )
            )
            checkpoint()
            return result

        revisions = rows(QuoteRevisionRecord, 32, QuoteRevisionRecord.version)
        lines = rows(QuoteLineRecord, 3200, QuoteLineRecord.position)
        decisions = rows(QuoteDecisionRecord, 128, QuoteDecisionRecord.sequence)
        operations = rows(QuoteOperationRecord, 160, QuoteOperationRecord.ordinal)
        checkpoint()
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
        checkpoint()
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
        checkpoint()
        # Each source is selected by its retained identity through this scoped
        # lineage. In particular, change cursors are global, not tenant-local.
        order_events = list(
            self.session.scalars(
                select(ServiceOrderEventRecord)
                .join(
                    QuoteOperationRecord,
                    QuoteOperationRecord.order_event_id == ServiceOrderEventRecord.event_id,
                )
                .where(
                    QuoteOperationRecord.lineage_id == scope,
                    ServiceOrderEventRecord.organization_id == lineage.organization_id,
                    ServiceOrderEventRecord.order_id == lineage.order_id,
                )
                .limit(129)
                .execution_options(populate_existing=True)
            )
        )
        checkpoint()
        changes = list(
            self.session.scalars(
                select(ChangeRecord)
                .join(
                    QuoteOperationRecord,
                    QuoteOperationRecord.change_cursor == ChangeRecord.cursor,
                )
                .where(
                    QuoteOperationRecord.lineage_id == scope,
                    ChangeRecord.organization_id == lineage.organization_id,
                    ChangeRecord.location_id == lineage.location_id,
                    ChangeRecord.entity_type == "service_order",
                    ChangeRecord.entity_id == lineage.order_id,
                )
                .limit(129)
                .execution_options(populate_existing=True)
            )
        )
        checkpoint()
        order_outboxes = list(
            self.session.scalars(
                select(OutboxRecord)
                .join(
                    QuoteOperationRecord,
                    QuoteOperationRecord.order_outbox_id == OutboxRecord.event_id,
                )
                .where(
                    QuoteOperationRecord.lineage_id == scope,
                    OutboxRecord.organization_id == lineage.organization_id,
                    OutboxRecord.location_id == lineage.location_id,
                    OutboxRecord.aggregate_type == "service_order",
                    OutboxRecord.aggregate_id == lineage.order_id,
                )
                .limit(129)
                .execution_options(populate_existing=True)
            )
        )
        checkpoint()
        return _reconstruct_with_bytes(
            lineage,
            revisions,
            lines,
            targets,
            decisions,
            operations,
            outboxes,
            order_events=order_events,
            changes=changes,
            order_outboxes=order_outboxes,
            checkpoint=checkpoint,
        )

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
        """Historical repository append; never creates operational order effects."""
        return self._apply(command, recorded_at=recorded_at)

    def _apply_application(
        self,
        command: QuoteRepositoryCommand,
        *,
        recorded_at: datetime,
        admit_new: Callable[[ServiceOrderRecord, QuoteSnapshot | None], None],
        apply_effects: Callable[
            [ServiceOrderRecord, QuoteDecisionLedger, QuoteDecisionResult | None],
            QuoteOrderEffects | None,
        ],
        checkpoint: Callable[[], None] = _noop,
    ) -> QuoteRepositoryResult:
        """Private fixed service composition; accepts no prepared ledger or plan.

        The service owns a clean session, admission, final materialization and
        commit/rollback. Callbacks never escape their owning locked transaction.
        They are not request data or an extension/command-dispatch API.
        """
        return self._apply(
            command,
            recorded_at=recorded_at,
            admit_new=admit_new,
            apply_effects=apply_effects,
            checkpoint=checkpoint,
        )

    def _apply(
        self,
        command: QuoteRepositoryCommand,
        *,
        recorded_at: datetime,
        admit_new: Callable[[ServiceOrderRecord, QuoteSnapshot | None], None] | None = None,
        apply_effects: Callable[
            [ServiceOrderRecord, QuoteDecisionLedger, QuoteDecisionResult | None],
            QuoteOrderEffects | None,
        ]
        | None = None,
        checkpoint: Callable[[], None] = _noop,
    ) -> QuoteRepositoryResult:
        checkpoint()
        # Reconstruct the immutable proof before examining storage; reject forged
        # dataclass internals just like malformed commands from future adapters.
        proof = operation_proof(command)
        command = command_from_proof(proof)
        checkpoint()
        now = _timestamp(_document(recorded_at))
        self._admitted(command.organization_id, command.location_id, command.actor_id)
        checkpoint()
        order = self._order(command.organization_id, command.location_id, command.order_id)
        checkpoint()
        lineage = self._lineage(command.organization_id, command.order_id)
        checkpoint()
        snapshot, history_bytes = (
            self._load_with_bytes(lineage, checkpoint=checkpoint)
            if lineage is not None
            else (None, 2)
        )
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
        checkpoint()
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
            checkpoint()
            return self._result(receipt, snapshot.ledger, order, True)
        # Availability and other new-command policy never suppress a scoped
        # exact replay, and run before stale CAS, domain validation or writes.
        if admit_new is not None:
            admit_new(order, snapshot)
            checkpoint()
        if type(order.version) is not int or order.version != command.expected_order_version:
            raise QuoteConflictError("stale order version")
        try:
            fresh_decision: QuoteDecisionResult | None = None
            if apply_effects is None:
                ledger = advance(snapshot.ledger if snapshot else None, command, now)
            else:
                ledger, fresh_decision = _advance_with_result(
                    snapshot.ledger if snapshot else None, command, now
                )
        except ValueError as error:
            raise QuoteConflictError(str(error)) from error
        checkpoint()
        if not isinstance(command, RecordQuoteDecisionCommand):
            for line in ledger.history.head.lines:
                checkpoint()
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
        checkpoint()
        # Reuse only the byte count from this same locked, fully validated load.
        # Canonical arrays add one comma when appending to a nonempty history.
        # Keep the original history-array JSON depth validation for the candidate.
        candidate_bytes = len(canonical_bytes([logical_record(command, ledger)])) - 2
        _check_history_byte_count(history_bytes + int(snapshot is not None) + candidate_bytes)
        checkpoint()
        # A local savepoint rolls back this operation on any late serialization,
        # constraint or admission failure. The caller still owns outer commit.
        connection = self.session.connection()
        driver = connection.connection.driver_connection
        if isinstance(driver, SQLiteConnection) and not driver.in_transaction:
            # sqlite3 legacy SELECT does not begin a real transaction; otherwise
            # RELEASE of the first SAVEPOINT would commit behind the caller.
            connection.exec_driver_sql("BEGIN")
        checkpoint()
        try:
            with self.session.begin_nested():
                checkpoint()
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
                    checkpoint()
                    self.session.flush()
                    checkpoint()
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
                    checkpoint()
                    self.session.flush()
                    checkpoint()
                else:
                    self._insert_revision(
                        ledger.history.head,
                        command.actor_id,
                        command.lineage_id,
                        checkpoint=checkpoint,
                    )
                head = ledger.history.head
                if not isinstance(command, CreateQuoteCommand):
                    checkpoint()
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
                checkpoint()
                order_effects = None
                if apply_effects is not None:
                    order_effects = apply_effects(order, ledger, fresh_decision)
                    if isinstance(command, RecordQuoteDecisionCommand):
                        if type(order_effects) is not QuoteOrderEffects:
                            raise QuoteConflictError(
                                "initial decision requires complete order effects"
                            )
                    elif order_effects is not None:
                        raise QuoteConflictError("quote revision cannot create order effects")
                    checkpoint()
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
                checkpoint()
                self.session.flush()
                checkpoint()
                if order_effects is not None:
                    self._validate_inserted_effects(
                        order_effects, command, now, outbox_id, checkpoint=checkpoint
                    )
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
                        order_event_id=order_effects.order_event_id if order_effects else None,
                        resulting_order_version=(
                            order_effects.resulting_order_version if order_effects else None
                        ),
                        change_cursor=order_effects.change_cursor if order_effects else None,
                        order_outbox_id=order_effects.order_outbox_id if order_effects else None,
                    )
                )
                checkpoint()
                self.session.flush()
                checkpoint()
                self._admitted(command.organization_id, command.location_id, command.actor_id)
                receipt = QuoteReceipt(
                    command,
                    head.quote_id,
                    head.version,
                    ledger.sequence,
                    ordinal,
                    now,
                    outbox_id,
                    order_effects,
                )
                result = self._result(receipt, ledger, order, False)
                checkpoint()
        except IntegrityError:
            raise QuoteConflictError(
                "quote operation conflicts with stored identity or scope"
            ) from None
        return result

    def _validate_inserted_effects(
        self,
        effects: QuoteOrderEffects,
        command: QuoteRepositoryCommand,
        recorded_at: datetime,
        quote_outbox_id: str,
        *,
        checkpoint: Callable[[], None],
    ) -> None:
        checkpoint()
        order_event = self.session.scalar(
            select(ServiceOrderEventRecord)
            .where(
                ServiceOrderEventRecord.event_id == effects.order_event_id,
                ServiceOrderEventRecord.organization_id == command.organization_id,
                ServiceOrderEventRecord.order_id == command.order_id,
            )
            .execution_options(populate_existing=True)
        )
        checkpoint()
        change = self.session.scalar(
            select(ChangeRecord)
            .where(
                ChangeRecord.cursor == effects.change_cursor,
                ChangeRecord.organization_id == command.organization_id,
                ChangeRecord.location_id == command.location_id,
                ChangeRecord.entity_type == "service_order",
                ChangeRecord.entity_id == command.order_id,
            )
            .execution_options(populate_existing=True)
        )
        checkpoint()
        order_outbox = self.session.scalar(
            select(OutboxRecord)
            .where(
                OutboxRecord.event_id == effects.order_outbox_id,
                OutboxRecord.organization_id == command.organization_id,
                OutboxRecord.location_id == command.location_id,
                OutboxRecord.aggregate_type == "service_order",
                OutboxRecord.aggregate_id == command.order_id,
            )
            .execution_options(populate_existing=True)
        )
        checkpoint()
        try:
            if order_event is None or change is None or order_outbox is None:
                raise ValueError("initial decision effect source row is missing")
            _validate_order_effects(
                effects, command, recorded_at, quote_outbox_id, order_event, change, order_outbox
            )
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error
        checkpoint()

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

    def _insert_revision(
        self,
        quote: Quote,
        actor_id: str,
        lineage_id: str,
        *,
        checkpoint: Callable[[], None] = _noop,
    ) -> None:
        checkpoint()
        document = encode_quote(quote)
        checkpoint()
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
        checkpoint()
        self.session.flush()
        checkpoint()
        edges: list[QuoteLineTargetRecord] = []
        for position, value in enumerate(encode_lines(quote.lines)):
            checkpoint()
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
        checkpoint()
        self.session.flush()
        checkpoint()
        self.session.add_all(edges)
        checkpoint()
        self.session.flush()
        checkpoint()
