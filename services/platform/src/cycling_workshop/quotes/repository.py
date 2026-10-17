"""Inert, caller-owned quote storage operations under existing writer admission.

This is not an authorization service: a future application boundary must check
explicit quote grants and activation policy before calling it. There are no HTTP
routes or sync mutations here. The existing writer barrier supplies org→actor
locks; this repository then locks order→lineage and never commits. PostgreSQL
READ COMMITTED is supported; SQLite proves functional behavior, not concurrency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from sqlite3 import Connection as SQLiteConnection
from typing import cast

from sqlalchemy import (
    BigInteger,
    DateTime,
    LargeBinary,
    Text,
    and_,
    case,
    func,
    literal_column,
    select,
    update,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from cycling_workshop.db.order_payload_size import require_order_payload_count_schema
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
from cycling_workshop.quotes.effects import (
    OrderEffectChange,
    OrderEffectEvent,
    OrderEffectOutbox,
    PreparedQuoteOrderEffect,
    QuoteOrderEffects,
    _order_effects,
    _utc,
    _validate_order_effects,
)
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
    _integer,
    _timestamp,
    canonical_bytes,
    encode_entry,
    encode_lines,
    encode_quote,
)
from cycling_workshop.service_orders.domain import OrderState, ServiceOrder
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.order_projection_integrity import (
    ORDER_RAW_MAX_BYTES,
    ORDER_SOURCE_MAX_BYTES,
    OrderProjectionLimitError,
    encode_order_projection,
)
from cycling_workshop.sync.projections import order_payload
from cycling_workshop.sync.writes import _validate_prepared_order_change


class QuoteConflictError(ValueError):
    """New operation cannot apply to the supplied current scope or cursor."""


@dataclass(frozen=True, slots=True)
class LockedQuoteOrder:
    id: str
    organization_id: str
    location_id: str
    customer_id: str
    bicycle_id: str | None
    state: str
    version: int
    created_at: datetime
    updated_at: datetime


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

    def _safe_time(self, column: InstrumentedAttribute[datetime]) -> ColumnElement[datetime | None]:
        bounded = and_(
            column >= datetime.min.replace(tzinfo=UTC),
            column <= datetime.max.replace(tzinfo=UTC),
        )
        if self.session.get_bind().dialect.name == "postgresql":
            bounded = and_(
                func.pg_catalog.isfinite(column),
                column.bool_op("OPERATOR(pg_catalog.>=)")(datetime.min.replace(tzinfo=UTC)),
                column.bool_op("OPERATOR(pg_catalog.<=)")(datetime.max.replace(tzinfo=UTC)),
            )
            value: ColumnElement[datetime] = func.pg_catalog.timezone(
                "UTC", column, type_=DateTime(timezone=False)
            )
        else:
            value = column.__clause_element__()
        return case((bounded, value), else_=None)

    def _order(self, organization_id: str, location_id: str, order_id: str) -> LockedQuoteOrder:
        for value in (organization_id, location_id, order_id):
            _id(value)
        row = self.session.execute(
            select(
                ServiceOrderRecord.id,
                ServiceOrderRecord.organization_id,
                ServiceOrderRecord.location_id,
                ServiceOrderRecord.customer_id,
                ServiceOrderRecord.bicycle_id,
                ServiceOrderRecord.state,
                ServiceOrderRecord.version,
                self._safe_time(ServiceOrderRecord.created_at).label("created_at"),
                self._safe_time(ServiceOrderRecord.updated_at).label("updated_at"),
            )
            .where(
                ServiceOrderRecord.id == order_id,
                ServiceOrderRecord.organization_id == organization_id,
                ServiceOrderRecord.location_id == location_id,
            )
            .with_for_update()
        ).one_or_none()
        if row is None:
            raise QuoteConflictError("scoped order not found")
        try:
            for value in (row.id, row.organization_id, row.location_id, row.customer_id):
                if "\x00" in _id(value):
                    raise ValueError("stored order identity cannot contain NUL")
            if row.bicycle_id is not None and "\x00" in _id(row.bicycle_id):
                raise ValueError("stored order identity cannot contain NUL")
            OrderState(row.state)
            _integer(row.version, 1, 2147483647)
            return LockedQuoteOrder(
                row.id,
                row.organization_id,
                row.location_id,
                row.customer_id,
                row.bicycle_id,
                row.state,
                row.version,
                _utc(row.created_at),
                _utc(row.updated_at),
            )
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error

    def _load_bounded_order(self, order: LockedQuoteOrder) -> ServiceOrder:
        try:
            require_order_payload_count_schema(self.session.connection())
        except ValueError as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error
        fields = (
            ServiceOrderRecord.reported_problem,
            ServiceOrderRecord.intake_condition,
            ServiceOrderRecord.accessories,
            ServiceOrderRecord.priority,
            ServiceOrderRecord.diagnosis,
        )
        postgres = self.session.get_bind().dialect.name == "postgresql"
        lengths = tuple(
            func.coalesce(
                sql_cast(
                    func.pg_catalog.octet_length(field)
                    if postgres
                    else func.length(sql_cast(field, LargeBinary)),
                    BigInteger,
                ),
                0,
            )
            for field in fields
        )
        if postgres:
            total: ColumnElement[int] = lengths[0]
            for length in lengths[1:]:
                total = total.op("OPERATOR(pg_catalog.+)")(length)
            allowed = and_(
                total.bool_op("OPERATOR(pg_catalog.>=)")(0),
                total.bool_op("OPERATOR(pg_catalog.<=)")(ORDER_SOURCE_MAX_BYTES),
            )
        else:
            total = lengths[0] + lengths[1] + lengths[2] + lengths[3] + lengths[4]
            allowed = and_(total >= 0, total <= ORDER_SOURCE_MAX_BYTES)
        scope = (
            ServiceOrderRecord.id == order.id,
            ServiceOrderRecord.organization_id == order.organization_id,
            ServiceOrderRecord.location_id == order.location_id,
            ServiceOrderRecord.version == order.version,
        )
        size = self.session.scalar(select(total).where(*scope))
        if type(size) is not int or not 0 <= size <= ORDER_SOURCE_MAX_BYTES:
            raise QuoteConflictError("order_effect_payload_limit")
        row = self.session.execute(
            select(
                allowed.label("admitted"),
                *(case((allowed, field), else_=None).label(field.key) for field in fields),
            ).where(*scope)
        ).one_or_none()
        if row is None or row.admitted is not True:
            raise QuoteConflictError("order_effect_payload_limit")
        values = [row._mapping[field.key] for field in fields]
        try:
            actual_bytes = sum(len(value.encode("utf-8")) for value in values if value is not None)
            if actual_bytes > ORDER_SOURCE_MAX_BYTES:
                raise OrderProjectionLimitError("source byte limit")
            result = ServiceOrder(
                order_id=order.id,
                customer_id=order.customer_id,
                bicycle_id=order.bicycle_id,
                organization_id=order.organization_id,
                location_id=order.location_id,
                state=order.state,
                reported_problem=values[0],
                intake_condition=values[1],
                accessories=values[2],
                priority=values[3],
                diagnosis=values[4],
                created_at=order.created_at,
                updated_at=order.updated_at,
                version=order.version,
            )
            # Shared full projection validation also checks every metadata/text
            # domain. No generic repository materialization or normalization.
            encode_order_projection(order_payload(result))
            return result
        except OrderProjectionLimitError as error:
            raise QuoteConflictError("order_effect_payload_limit") from error
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error

    def _admit_enrollment(self, order: LockedQuoteOrder) -> None:
        if order.version == 2147483647:
            raise QuoteConflictError("order version cannot advance")
        source = self._load_bounded_order(order)
        # The longest eligible target and allowed scalar spellings conservatively
        # reserve the full projection bound; they do not promise a future effect.
        hypothetical = replace(
            source,
            state="AUTHORIZED",
            version=2147483647,
            updated_at=datetime.max.replace(tzinfo=UTC),
        )
        try:
            encode_order_projection(order_payload(hypothetical))
        except OrderProjectionLimitError as error:
            raise QuoteConflictError("order_effect_payload_limit") from error

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
                .where(
                    QuoteOperationRecord.lineage_id == scope,
                    OutboxRecord.aggregate_type == "quote",
                    OutboxRecord.aggregate_id == scope,
                    OutboxRecord.organization_id == lineage.organization_id,
                    OutboxRecord.location_id == lineage.location_id,
                    OutboxRecord.event_type
                    == case(
                        (QuoteOperationRecord.kind == "create", "quote.created"),
                        (QuoteOperationRecord.kind == "revise", "quote.revised"),
                        (QuoteOperationRecord.kind == "decision", "quote.decision_recorded"),
                        else_=None,
                    ),
                )
                .limit(161)
                .execution_options(populate_existing=True)
            )
        )
        checkpoint()
        # Reject unsupported provenance/count before any generic source fetch.
        try:
            linked = [
                effect
                for operation in operations
                if (effect := _order_effects(operation)) is not None
            ]
            if len(linked) > 1:
                raise ValueError("a lineage may own only one initial order transition")
        except (ValueError, TypeError, AttributeError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error
        order_events: list[OrderEffectEvent] = []
        changes: list[OrderEffectChange] = []
        order_outboxes: list[OrderEffectOutbox] = []
        for effect in linked:
            checkpoint()
            event, change, outbox = self._load_order_effect_sources(
                effect,
                organization_id=lineage.organization_id,
                location_id=lineage.location_id,
                order_id=lineage.order_id,
            )
            order_events.append(event)
            changes.append(change)
            order_outboxes.append(outbox)
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

    def _load_order_effect_sources(
        self, effects: QuoteOrderEffects, *, organization_id: str, location_id: str, order_id: str
    ) -> tuple[OrderEffectEvent, OrderEffectChange, OrderEffectOutbox]:
        try:
            require_order_payload_count_schema(self.session.connection())
            if self.session.get_bind().dialect.name == "postgresql":
                both_bounded = and_(
                    ChangeRecord.order_payload_raw_octets.bool_op("OPERATOR(pg_catalog.>=)")(1),
                    ChangeRecord.order_payload_raw_octets.bool_op("OPERATOR(pg_catalog.<=)")(
                        ORDER_RAW_MAX_BYTES
                    ),
                    OutboxRecord.order_payload_raw_octets.bool_op("OPERATOR(pg_catalog.>=)")(1),
                    OutboxRecord.order_payload_raw_octets.bool_op("OPERATOR(pg_catalog.<=)")(
                        ORDER_RAW_MAX_BYTES
                    ),
                )
                change_raw: ColumnElement[str] = literal_column(
                    "CAST(sync_changes.payload AS pg_catalog.text)", type_=Text()
                )
                outbox_raw: ColumnElement[str] = literal_column(
                    "CAST(outbox_events.payload AS pg_catalog.text)", type_=Text()
                )
            else:
                both_bounded = and_(
                    ChangeRecord.order_payload_raw_octets.between(1, ORDER_RAW_MAX_BYTES),
                    OutboxRecord.order_payload_raw_octets.between(1, ORDER_RAW_MAX_BYTES),
                )
                change_raw = sql_cast(ChangeRecord.payload, Text)
                outbox_raw = sql_cast(OutboxRecord.payload, Text)
            # A single scoped statement snapshot. BOTH actual JSON-to-Text casts
            # share BOTH stored count guards; note Text is never selected.
            row = (
                self.session.execute(
                    select(
                        ServiceOrderEventRecord.event_id.label("event_id"),
                        ServiceOrderEventRecord.organization_id.label("event_org"),
                        ServiceOrderEventRecord.order_id.label("event_order"),
                        ServiceOrderEventRecord.from_state,
                        ServiceOrderEventRecord.to_state,
                        ServiceOrderEventRecord.action,
                        ServiceOrderEventRecord.actor_id,
                        ServiceOrderEventRecord.note.is_(None).label("note_is_null"),
                        self._safe_time(ServiceOrderEventRecord.occurred_at).label("event_time"),
                        ChangeRecord.cursor,
                        ChangeRecord.organization_id.label("change_org"),
                        ChangeRecord.location_id.label("change_location"),
                        ChangeRecord.entity_type,
                        ChangeRecord.entity_id,
                        ChangeRecord.operation,
                        ChangeRecord.entity_version,
                        self._safe_time(ChangeRecord.occurred_at).label("change_time"),
                        ChangeRecord.order_payload_raw_octets.label("change_octets"),
                        case((both_bounded, change_raw), else_=None).label("change_raw"),
                        OutboxRecord.event_id.label("outbox_id"),
                        OutboxRecord.event_type,
                        OutboxRecord.aggregate_type,
                        OutboxRecord.aggregate_id,
                        OutboxRecord.organization_id.label("outbox_org"),
                        OutboxRecord.location_id.label("outbox_location"),
                        self._safe_time(OutboxRecord.occurred_at).label("outbox_time"),
                        OutboxRecord.order_payload_raw_octets.label("outbox_octets"),
                        case((both_bounded, outbox_raw), else_=None).label("outbox_raw"),
                    )
                    .select_from(ServiceOrderEventRecord)
                    .join(ChangeRecord, ChangeRecord.cursor == effects.change_cursor)
                    .join(OutboxRecord, OutboxRecord.event_id == effects.order_outbox_id)
                    .where(
                        ServiceOrderEventRecord.event_id == effects.order_event_id,
                        ServiceOrderEventRecord.organization_id == organization_id,
                        ServiceOrderEventRecord.order_id == order_id,
                        ChangeRecord.organization_id == organization_id,
                        ChangeRecord.location_id == location_id,
                        ChangeRecord.entity_type == "service_order",
                        ChangeRecord.entity_id == order_id,
                        OutboxRecord.organization_id == organization_id,
                        OutboxRecord.location_id == location_id,
                        OutboxRecord.aggregate_type == "service_order",
                        OutboxRecord.aggregate_id == order_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ValueError("initial decision effect source row is missing")
            for prefix in ("change", "outbox"):
                raw, count = row[f"{prefix}_raw"], row[f"{prefix}_octets"]
                if (
                    type(raw) is not str
                    or type(count) is not int
                    or not 1 <= count <= ORDER_RAW_MAX_BYTES
                    or len(raw.encode("utf-8")) != count
                ):
                    raise ValueError("order effect raw count or bound is invalid")
            return self._source_values(row)
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError) as error:
            raise QuoteIntegrityError("stored quote history is invalid") from error

    @staticmethod
    def _source_values(
        row: RowMapping,
    ) -> tuple[OrderEffectEvent, OrderEffectChange, OrderEffectOutbox]:
        return (
            OrderEffectEvent(
                row["event_id"],
                row["event_org"],
                row["event_order"],
                row["from_state"],
                row["to_state"],
                row["action"],
                row["actor_id"],
                row["note_is_null"],
                _utc(row["event_time"]),
            ),
            OrderEffectChange(
                row["cursor"],
                row["change_org"],
                row["change_location"],
                row["entity_type"],
                row["entity_id"],
                row["operation"],
                row["entity_version"],
                _utc(row["change_time"]),
                row["change_raw"],
                row["change_octets"],
            ),
            OrderEffectOutbox(
                row["outbox_id"],
                row["event_type"],
                row["aggregate_type"],
                row["aggregate_id"],
                row["outbox_org"],
                row["outbox_location"],
                _utc(row["outbox_time"]),
                row["outbox_raw"],
                row["outbox_octets"],
            ),
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
        admit_new: Callable[[LockedQuoteOrder, QuoteSnapshot | None], None],
        prepare_effects: Callable[
            [ServiceOrder, QuoteDecisionLedger, QuoteDecisionResult], PreparedQuoteOrderEffect
        ],
        persist_effects: Callable[[PreparedQuoteOrderEffect], QuoteOrderEffects],
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
            prepare_effects=prepare_effects,
            persist_effects=persist_effects,
            checkpoint=checkpoint,
        )

    def _apply(
        self,
        command: QuoteRepositoryCommand,
        *,
        recorded_at: datetime,
        admit_new: Callable[[LockedQuoteOrder, QuoteSnapshot | None], None] | None = None,
        prepare_effects: Callable[
            [ServiceOrder, QuoteDecisionLedger, QuoteDecisionResult], PreparedQuoteOrderEffect
        ]
        | None = None,
        persist_effects: Callable[[PreparedQuoteOrderEffect], QuoteOrderEffects] | None = None,
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
            if prepare_effects is None:
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
        if isinstance(command, CreateQuoteCommand):
            self._admit_enrollment(order)
            checkpoint()
        prepared: PreparedQuoteOrderEffect | None = None
        if prepare_effects is not None and isinstance(command, RecordQuoteDecisionCommand):
            if fresh_decision is None or persist_effects is None:
                raise QuoteIntegrityError("missing fresh initial decision preparation")
            if order.version == 2147483647:
                raise QuoteConflictError("order version cannot advance")
            try:
                prepared = prepare_effects(self._load_bounded_order(order), ledger, fresh_decision)
                if type(prepared) is not PreparedQuoteOrderEffect:
                    raise QuoteConflictError("initial decision requires complete order effects")
                _validate_prepared_order_change(
                    organization_id=command.organization_id,
                    location_id=command.location_id,
                    entity_id=command.order_id,
                    entity_version=order.version + 1,
                    occurred_at=now,
                    projection=prepared.projection,
                )
                if dict(prepared.projection.payload) != order_payload(prepared.transition.order):
                    raise QuoteIntegrityError("prepared order differs from measured projection")
            except OrderProjectionLimitError as error:
                raise QuoteConflictError("order_effect_payload_limit") from error
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
                if prepared is not None and persist_effects is not None:
                    order_effects = persist_effects(prepared)
                    if type(order_effects) is not QuoteOrderEffects:
                        raise QuoteConflictError("initial decision requires complete order effects")
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
                    order = self._order(
                        command.organization_id, command.location_id, command.order_id
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
                        order_effect_version=1 if order_effects else None,
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
        order_event, change, order_outbox = self._load_order_effect_sources(
            effects,
            organization_id=command.organization_id,
            location_id=command.location_id,
            order_id=command.order_id,
        )
        checkpoint()
        try:
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
        order: LockedQuoteOrder,
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
