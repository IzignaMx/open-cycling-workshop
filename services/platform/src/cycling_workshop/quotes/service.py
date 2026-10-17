"""Unmounted synthetic quote application candidate, pending execution evidence.

No HTTP dependency, settings switch, grant adoption or ingress activation lives
here. Checkpoints are cooperative, not a proven total Python wall-time cutoff.
The caller must supply a dedicated Session and a deadline started at ingress.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from sqlalchemy import event, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.inventory.models import InventoryMovementRecord
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    QuoteRepositoryCommand,
    RecordQuoteDecisionCommand,
    command_from_proof,
    operation_proof,
)
from cycling_workshop.quotes.decisions import (
    QuoteDecisionLedger,
    QuoteDecisionResult,
    plan_initial_transition,
)
from cycling_workshop.quotes.domain import LaborLine, PartLine
from cycling_workshop.quotes.effects import QuoteOrderEffects
from cycling_workshop.quotes.reads import CurrentLineage, PricingSummary, QuoteReadError
from cycling_workshop.quotes.reconstruction import QuoteIntegrityError, QuoteSnapshot
from cycling_workshop.quotes.repository import (
    QuoteConflictError,
    QuoteRepository,
    QuoteRepositoryResult,
)
from cycling_workshop.quotes.responses import (
    CommandResponse,
    DecisionNow,
    OrderNow,
    OrderTransitionEffects,
    QuoteOnlyEffects,
    Receipt,
    encode_command_response,
)
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository
from cycling_workshop.sync.projections import order_payload
from cycling_workshop.sync.writes import append_change, lock_writer


class QuoteServiceError(Exception):
    """Closed internal category; outcome_unknown is never an exception message."""

    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.code = code
        self.outcome_unknown = outcome_unknown
        self.cleanup_unverified = False
        super().__init__(code)


class _DeadlineExpired(TimeoutError):
    """Distinct from reconstruction's integrity-normalization exceptions."""


class _QuoteDriverUnavailable(OSError):
    """A raw DBAPI hook failure, with no SQL/parameters/driver message."""


@dataclass(frozen=True, slots=True)
class QuoteDeadline:
    expires_at: float
    clock: Callable[[], float] = time.monotonic

    def __post_init__(self) -> None:
        if type(self.expires_at) is not float or not math.isfinite(self.expires_at):
            raise ValueError("invalid quote deadline")

    @classmethod
    def start(cls) -> QuoteDeadline:
        return cls(time.monotonic() + 8.0)

    def remaining_ms(self) -> int:
        now = self.clock()
        if type(now) is not float or not math.isfinite(now):
            raise _DeadlineExpired()
        remaining = self.expires_at - now
        if remaining < 0.001:
            raise _DeadlineExpired()
        # Never pass zero to PostgreSQL: zero disables the limit.
        return math.floor(min(8.0, remaining) * 1000)

    def check(self) -> None:
        self.remaining_ms()


def _set_cursor_budgets(cursor: Any, deadline: QuoteDeadline) -> None:
    try:
        remaining = deadline.remaining_ms()
        cursor.execute(f"SET LOCAL lock_timeout = '{min(2000, remaining)}ms'")
        # The first round trip consumes the same immutable deadline.
        remaining = deadline.remaining_ms()
        cursor.execute(f"SET LOCAL statement_timeout = '{min(5000, remaining)}ms'")
        deadline.check()
    except psycopg.Error:
        # SQLAlchemy's before_cursor_execute hook can expose raw DBAPI errors.
        # Do not accidentally normalize our independent deadline exception here.
        raise _QuoteDriverUnavailable() from None


class QuoteService:
    def __init__(
        self,
        session: Session,
        *,
        commands_enabled: bool = False,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if type(commands_enabled) is not bool:
            raise ValueError("quote availability must be boolean")
        self.session = session
        self.commands_enabled = commands_enabled
        self.now = now

    def execute(
        self,
        command: QuoteRepositoryCommand,
        *,
        principal: Principal,
        admission: WriteAdmission,
        deadline: QuoteDeadline,
    ) -> bytes:
        """Own the whole transaction, including projection and commit ambiguity.

        The internal service consumes canonical commands, not arbitrary HTTP
        payloads. A later adapter must start this same deadline before decoding.
        No application transaction may share this session with unrelated work.
        """
        if (
            self.session.in_transaction()
            or self.session.new
            or self.session.dirty
            or self.session.deleted
            or self.session.info.get("ocwp_quote_unusable") is True
        ):
            raise QuoteServiceError("quote_request_unavailable")
        commit_started = False
        connection: Connection | None = None
        budget_hook: Callable[..., None] | None = None
        failure: BaseException | None = None
        encoded: bytes | None = None
        cleanup_verified = True
        try:
            deadline.check()
            if admission.protocol != 1 or not admission.enabled:
                raise ApiError(409, "client_upgrade_required", "client upgrade required")
            # Normalize forged dataclass instances before inspecting their scope.
            command = command_from_proof(operation_proof(command))
            deadline.check()
            self._authorize(principal, command)
            connection = self.session.connection()
            if connection.dialect.name == "sqlite" and admission.fixture_only:
                # Explicit existing fixture authority; never from a route flag.
                pass
            elif (
                connection.dialect.name == "postgresql"
                and connection.dialect.driver == "psycopg"
                and connection.dialect.server_version_info
                and connection.dialect.server_version_info[0] == 18
            ):
                remaining = deadline.remaining_ms()
                connection.execute(text(f"SET LOCAL transaction_timeout = '{remaining}ms'"))

                def budgets(
                    _connection: Connection,
                    cursor: Any,
                    _statement: str,
                    _parameters: Any,
                    _context: Any,
                    _executemany: bool,
                ) -> None:
                    # Fixed integers only; direct DBAPI avoids recursive events.
                    _set_cursor_budgets(cursor, deadline)

                budget_hook = budgets
                event.listen(connection, "before_cursor_execute", budget_hook)
                observed = dict(
                    connection.execute(
                        text(
                            "SELECT name, setting FROM pg_settings "
                            "WHERE name IN ('transaction_timeout', 'lock_timeout', "
                            "'statement_timeout')"
                        )
                    ).tuples()
                )
                expected = {
                    "transaction_timeout": remaining,
                    "lock_timeout": min(2000, remaining),
                    "statement_timeout": min(5000, remaining),
                }
                if set(observed) != set(expected) or any(
                    not str(observed[name]).isascii()
                    or not str(observed[name]).isdigit()
                    or len(str(observed[name])) > 5
                    or not 1 <= int(observed[name]) <= upper
                    for name, upper in expected.items()
                ):
                    raise QuoteServiceError("quote_request_unavailable")
            else:
                raise QuoteServiceError("quote_request_unavailable")
            deadline.check()
            fresh = lock_writer(self.session, principal, admission)
            deadline.check()
            self._authorize(fresh, command)
            recorded_at = self.now()
            if type(recorded_at) is not datetime or recorded_at.utcoffset() is None:
                raise QuoteServiceError("quote_request_unavailable")
            recorded_at = recorded_at.astimezone(UTC)

            def admit_new(order: ServiceOrderRecord, snapshot: QuoteSnapshot | None) -> None:
                deadline.check()
                if not self.commands_enabled:
                    raise QuoteServiceError("quote_commands_unavailable")
                self._admit_new(command, order, snapshot)
                deadline.check()

            def apply_effects(
                order: ServiceOrderRecord,
                ledger: QuoteDecisionLedger,
                decision: QuoteDecisionResult | None,
            ) -> QuoteOrderEffects | None:
                deadline.check()
                if not isinstance(command, RecordQuoteDecisionCommand):
                    if decision is not None:
                        raise QuoteIntegrityError("unexpected revision decision result")
                    return None
                if decision is None:
                    raise QuoteIntegrityError("missing fresh decision result")
                orders = SqlAlchemyServiceOrderRepository(self.session)
                previous = orders._to_domain(order)
                plan = plan_initial_transition(ledger=ledger, order=previous, result=decision)
                if (
                    plan.order_id,
                    plan.expected_order_version,
                    plan.lineage_id,
                    plan.expected_head_id,
                    plan.expected_head_version,
                    plan.decision_id,
                    plan.expected_decision_sequence,
                ) != (
                    command.order_id,
                    command.expected_order_version,
                    command.lineage_id,
                    command.expected_head_id,
                    command.expected_head_version,
                    command.operation_id,
                    command.expected_decision_sequence + 1,
                ):
                    raise QuoteIntegrityError("initial plan differs from locked command")
                transition = previous.transition(
                    plan.action,
                    actor_id=fresh.user_id,
                    event_id=command.operation_id,
                    now=recorded_at,
                )
                deadline.check()
                orders.save(transition.order)
                orders.add_event(transition.event)
                change = append_change(
                    self.session,
                    organization_id=command.organization_id,
                    location_id=command.location_id,
                    entity_type="service_order",
                    entity_id=command.order_id,
                    operation="update",
                    entity_version=transition.order.version,
                    occurred_at=recorded_at,
                    payload=order_payload(transition.order),
                )
                deadline.check()
                return QuoteOrderEffects(
                    transition.event.event_id,
                    transition.order.version,
                    change.cursor,
                    change.outbox_event_id,
                )

            result = QuoteRepository(self.session)._apply_application(
                command,
                recorded_at=recorded_at,
                admit_new=admit_new,
                apply_effects=apply_effects,
                checkpoint=deadline.check,
            )
            deadline.check()
            encoded = encode_command_response(self._response(result))
            deadline.check()
            self.session.flush()
            admission.check_expiry(fresh)
            deadline.check()
            # Commit has no statement event in all drivers. The original PG
            # transaction deadline still applies; do not renew it here.
            commit_started = True
            self.session.commit()
            deadline.check()
        except BaseException as error:
            # No retry or business work in cleanup. A lost commit acknowledgment
            # cannot be represented as proven rollback, even if rollback returns.
            if isinstance(error, SQLAlchemyError | OSError) and not isinstance(
                error, _DeadlineExpired
            ):
                # Invalidate before a rollback could release a questionable
                # driver connection to the pool. No reconnect or retry follows.
                cleanup_verified = self._invalidate()
            else:
                cleanup_verified = self._rollback()
            failure = self._failure(error, commit_started)
        finally:
            try:
                self._release_hook(connection, budget_hook)
            except BaseException:
                cleanup_verified = False
                self._invalidate()
                if failure is None:
                    failure = QuoteServiceError(
                        "quote_request_unavailable", outcome_unknown=commit_started
                    )
            if not cleanup_verified:
                self.session.info["ocwp_quote_unusable"] = True
                if isinstance(failure, QuoteServiceError):
                    failure.cleanup_unverified = True
        if failure is not None:
            raise failure from None
        if encoded is None:
            raise QuoteServiceError("quote_internal_error")
        return encoded

    def _invalidate(self) -> bool:
        self.session.info["ocwp_quote_unusable"] = True
        try:
            self.session.invalidate()
        except BaseException:
            return False
        return True

    def _rollback(self) -> bool:
        try:
            self.session.rollback()
        except BaseException:
            self._invalidate()
            return False
        return True

    @staticmethod
    def _release_hook(connection: Connection | None, hook: Callable[..., None] | None) -> None:
        if connection is not None and hook is not None:
            event.remove(connection, "before_cursor_execute", hook)

    @staticmethod
    def _failure(error: BaseException, commit_started: bool) -> BaseException:
        if not isinstance(error, Exception):
            # Cancellation/SystemExit must still leave the owning execution.
            # The client sees no success and must resolve its original identity.
            return error
        if commit_started:
            return QuoteServiceError("quote_request_unavailable", outcome_unknown=True)
        if isinstance(error, QuoteServiceError | ApiError):
            return error
        if isinstance(error, PermissionError):
            return QuoteServiceError("quote_access_denied")
        if isinstance(error, _DeadlineExpired | SQLAlchemyError | OSError):
            return QuoteServiceError("quote_request_unavailable")
        if isinstance(error, QuoteIntegrityError | QuoteReadError):
            return QuoteServiceError("quote_integrity_failed")
        if isinstance(error, QuoteConflictError):
            return QuoteServiceError("quote_conflict")
        if isinstance(error, ValueError | TypeError):
            return QuoteServiceError("quote_integrity_failed")
        return QuoteServiceError("quote_internal_error")

    @staticmethod
    def _authorize(principal: Principal, command: QuoteRepositoryCommand) -> None:
        needed = {"orders.read", "orders.write", "quotes.read"}
        needed.add(
            "quotes.authorize"
            if isinstance(command, RecordQuoteDecisionCommand)
            else "quotes.write"
        )
        if (
            not needed <= principal.capabilities
            or principal.user_id != command.actor_id
            or principal.organization_id != command.organization_id
            or principal.location_id not in (None, command.location_id)
        ):
            raise QuoteServiceError("quote_access_denied")

    def _admit_new(
        self,
        command: QuoteRepositoryCommand,
        order: ServiceOrderRecord,
        snapshot: QuoteSnapshot | None,
    ) -> None:
        if order.state != "DIAGNOSIS" or (snapshot is not None and snapshot.ledger.entries):
            raise QuoteServiceError("quote_conflict")
        if isinstance(command, CreateQuoteCommand):
            stock = select(InventoryMovementRecord.movement_id).where(
                InventoryMovementRecord.organization_id == command.organization_id,
                InventoryMovementRecord.order_id == command.order_id,
            )
            progressed = {
                "AUTHORIZED",
                "REJECTED",
                "IN_PROGRESS",
                "WAITING_FOR_PARTS",
                "READY",
                "CLOSED",
                "CANCELLED",
            }
            history = select(ServiceOrderEventRecord.event_id).where(
                ServiceOrderEventRecord.organization_id == command.organization_id,
                ServiceOrderEventRecord.order_id == command.order_id,
                (
                    ServiceOrderEventRecord.from_state.in_(progressed)
                    | ServiceOrderEventRecord.to_state.in_(progressed)
                ),
            )
            if self.session.scalar(select(stock.exists())) or self.session.scalar(
                select(history.exists())
            ):
                raise QuoteServiceError("quote_conflict")
        if isinstance(command, RecordQuoteDecisionCommand):
            decision = command.command
            evidence = decision.evidence
            if (
                snapshot is None
                or decision.mode != "initial"
                or decision.supersedes_entry_id is not None
                or decision.reason is not None
                or evidence is None
                or evidence.party_kind != "customer"
                or evidence.party_id != order.customer_id
                or evidence.channel not in {"in_person", "phone", "email", "messaging", "written"}
            ):
                raise QuoteServiceError("quote_conflict")
            charges = {
                line.line_id
                for line in snapshot.ledger.history.head.lines
                if isinstance(line, LaborLine | PartLine)
            }
            selected = set(decision.approved_line_ids)
            if not (
                (decision.outcome == "APPROVE" and selected == charges)
                or (decision.outcome == "REJECT" and not selected)
                or (decision.outcome == "PARTIAL" and bool(selected) and selected < charges)
            ):
                raise QuoteServiceError("quote_conflict")

    @staticmethod
    def _response(result: QuoteRepositoryResult) -> CommandResponse:
        receipt = result.receipt
        command = receipt.command
        head = result.ledger.history.head
        decision = next(
            (
                entry
                for entry in result.ledger.entries
                if entry.command.decision_id == receipt.operation_id
            ),
            None,
        )
        historical_quote = next(
            quote for quote in result.ledger.history.revisions if quote.quote_id == receipt.quote_id
        )
        pricing = decision.pricing if decision is not None else historical_quote.totals
        effect = receipt.order_effects
        effects = (
            QuoteOnlyEffects(
                kind="quote_only",
                quote_outbox_id=receipt.quote_outbox_id,
                order_event_id=None,
                resulting_order_version=None,
                change_cursor=None,
                order_outbox_id=None,
            )
            if effect is None
            else OrderTransitionEffects(
                kind="order_transition",
                quote_outbox_id=receipt.quote_outbox_id,
                order_event_id=effect.order_event_id,
                resulting_order_version=effect.resulting_order_version,
                change_cursor=effect.change_cursor,
                order_outbox_id=effect.order_outbox_id,
            )
        )
        latest_id = result.ledger.projection.decision_id
        latest = next(
            (entry for entry in result.ledger.entries if entry.command.decision_id == latest_id),
            None,
        )
        return CommandResponse(
            delivery="replayed" if result.replayed else "applied",
            receipt=Receipt(
                operation_id=receipt.operation_id,
                kind="decision"
                if isinstance(command, RecordQuoteDecisionCommand)
                else "create"
                if isinstance(command, CreateQuoteCommand)
                else "revise",
                ordinal=receipt.ordinal,
                quote_id=receipt.quote_id,
                quote_version=receipt.quote_version,
                decision_id=receipt.operation_id if decision is not None else None,
                decision_sequence=receipt.decision_sequence,
                recorded_at=receipt.recorded_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                recorded_by_actor_id=command.actor_id,
                totals=PricingSummary(
                    subtotal_minor=pricing.subtotal_minor,
                    discount_minor=pricing.discount_minor,
                    tax_minor=pricing.tax_minor,
                    total_minor=pricing.total_minor,
                ),
                effects=effects,
            ),
            current=CurrentLineage(
                organization_id=head.organization_id,
                location_id=head.location_id,
                order_id=head.order_id,
                lineage_id=result.ledger.history.lineage_id,
                head_quote_id=head.quote_id,
                head_version=head.version,
                decision_sequence=result.ledger.sequence,
            ),
            current_decision=DecisionNow.model_validate(
                dict(
                    decision_id=latest.command.decision_id,
                    quote_id=latest.command.quote_id,
                    sequence=latest.sequence,
                    outcome=latest.command.outcome,
                ),
            )
            if latest is not None
            else None,
            order=OrderNow.model_validate(
                dict(
                    organization_id=result.order.organization_id,
                    location_id=result.order.location_id,
                    order_id=result.order.order_id,
                    state=result.order.state,
                    version=result.order.version,
                ),
            ),
        )
