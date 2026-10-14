from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.service_orders.domain import (
    InvalidStateTransitionError,
    ServiceOrder,
    UnknownActionError,
)
from cycling_workshop.service_orders.repository import SqlAlchemyServiceOrderRepository
from cycling_workshop.sync.domain import (
    ChangeItem,
    ChangePage,
    MutationEnvelope,
    MutationResult,
    SyncApplicationContext,
    SyncConflict,
)
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.sync.projections import bicycle_payload, customer_payload, order_payload
from cycling_workshop.sync.proof import (
    PROOF_VERSION,
    InvalidCommandProof,
    envelope_digest,
    valid_actor,
    valid_digest,
)
from cycling_workshop.sync.writes import append_change, lock_organization


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class _Applied:
    """Uniform result of an entity-specific apply step."""

    entity_id: str
    location_id: str
    version: int
    payload: dict[str, object]


class SyncService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._fixture_only = False

    @classmethod
    def for_fixtures(cls, session: Session) -> SyncService:
        """Explicitly unadmitted test/seed orchestration; never selected by HTTP."""
        service = cls(session)
        service._fixture_only = True
        return service

    def _require_context(self, context: SyncApplicationContext | None) -> None:
        if not self._fixture_only and (
            context is None
            or context.admitted_session_id != id(self._session)
            or not self._session.in_transaction()
        ):
            raise RuntimeError("sync application requires transaction-owned admission")
        if context is not None and (
            not valid_actor(context.actor_id)
            or type(context.write_protocol) is not int
            or context.write_protocol not in (0, 1)
        ):
            raise RuntimeError("sync application context is invalid")

    @staticmethod
    def _incoming_digest(mutation: MutationEnvelope, context: SyncApplicationContext | None) -> str:
        if context is None or not valid_digest(context.canonical_digest):
            raise SyncConflict(
                "canonical command proof is unavailable", error_code="receipt_integrity_conflict"
            )
        try:
            actual = envelope_digest(mutation)
        except InvalidCommandProof as exc:
            raise SyncConflict(
                "canonical command proof is invalid", error_code="receipt_integrity_conflict"
            ) from exc
        if actual != context.canonical_digest:
            raise SyncConflict(
                "canonical command proof is inconsistent", error_code="receipt_integrity_conflict"
            )
        return actual

    def _replay(
        self,
        receipt: MutationReceiptRecord,
        mutation: MutationEnvelope,
        context: SyncApplicationContext | None,
    ) -> MutationResult:
        # Globally colliding IDs never disclose another organization's proof or actor.
        if receipt.organization_id != mutation.organization_id:
            raise SyncConflict("mutation id is unavailable for this envelope")
        proof = (receipt.actor_id, receipt.command_digest, receipt.proof_version)
        legacy = all(value is None for value in proof)
        if legacy:
            if context is not None and context.write_protocol == 1:
                raise SyncConflict(
                    "legacy receipt has no verified command proof",
                    error_code="legacy_receipt_unverified",
                )
        else:
            if (
                not valid_actor(receipt.actor_id)
                or not valid_digest(receipt.command_digest)
                or type(receipt.proof_version) is not int
                or receipt.proof_version != PROOF_VERSION
                or receipt.status != "applied"
                or type(receipt.entity_version) is not int
                or receipt.entity_version < 1
            ):
                raise SyncConflict(
                    "stored receipt proof is invalid", error_code="receipt_integrity_conflict"
                )
            if context is None or receipt.actor_id != context.actor_id:
                raise SyncConflict(
                    "receipt does not match this command", error_code="receipt_proof_conflict"
                )
            if self._incoming_digest(mutation, context) != receipt.command_digest:
                raise SyncConflict(
                    "receipt does not match this command", error_code="receipt_proof_conflict"
                )
        if (
            receipt.location_id,
            receipt.entity_type,
            receipt.entity_id,
            receipt.operation,
        ) != (
            mutation.location_id,
            mutation.entity_type,
            mutation.entity_id,
            mutation.operation,
        ):
            raise SyncConflict(
                "mutation id already belongs to another envelope",
                error_code="sync_conflict" if legacy else "receipt_proof_conflict",
            )
        return MutationResult(
            mutation_id=receipt.mutation_id,
            status="applied",
            entity_id=receipt.entity_id,
            entity_version=receipt.entity_version,
        )

    def apply(
        self, mutation: MutationEnvelope, *, context: SyncApplicationContext | None = None
    ) -> MutationResult:
        self._require_context(context)
        # Domain constructors may trim/collapse IDs. Reject ambiguous identity
        # strings before lookup or effects instead of storing a receipt that an
        # identical raw envelope cannot safely replay. Do not normalize aliases.
        identities = (
            mutation.mutation_id,
            mutation.organization_id,
            mutation.location_id,
            mutation.entity_id,
        )
        if any(
            not value or any(character.isspace() for character in value) for value in identities
        ):
            raise SyncConflict(
                "mutation identity fields must be nonblank and contain no whitespace"
            )
        lock_organization(self._session, mutation.organization_id)
        existing_receipt = self._session.get(MutationReceiptRecord, mutation.mutation_id)
        if existing_receipt is not None:
            return self._replay(existing_receipt, mutation, context)

        strict = context is not None and context.write_protocol == 1
        digest = self._incoming_digest(mutation, context) if strict else None

        if mutation.entity_type == "customer":
            applied = self._apply_customer(mutation)
        elif mutation.entity_type == "bicycle":
            applied = self._apply_bicycle(mutation)
        elif mutation.entity_type == "service_order":
            applied = self._apply_service_order(mutation, context=context)
        else:
            raise SyncConflict(f"unsupported entity type: {mutation.entity_type}")

        self._session.flush()

        append_change(
            self._session,
            organization_id=mutation.organization_id,
            location_id=applied.location_id,
            entity_type=mutation.entity_type,
            entity_id=applied.entity_id,
            operation=mutation.operation,
            entity_version=applied.version,
            occurred_at=_as_utc(mutation.occurred_at),
            payload=applied.payload,
        )

        receipt = MutationReceiptRecord(
            mutation_id=mutation.mutation_id,
            organization_id=mutation.organization_id,
            location_id=applied.location_id,
            entity_type=mutation.entity_type,
            entity_id=applied.entity_id,
            operation=mutation.operation,
            status="applied",
            entity_version=applied.version,
            applied_at=datetime.now(UTC),
            actor_id=context.actor_id if strict and context is not None else None,
            command_digest=digest,
            proof_version=PROOF_VERSION if strict else None,
        )
        self._session.add(receipt)
        self._session.flush()
        return MutationResult(
            mutation_id=mutation.mutation_id,
            status="applied",
            entity_id=applied.entity_id,
            entity_version=applied.version,
        )

    def _apply_customer(self, mutation: MutationEnvelope) -> _Applied:
        repository = SqlAlchemyCustomerRepository(self._session)
        if mutation.operation == "create":
            if mutation.base_version is not None:
                raise SyncConflict("create mutation cannot have a base version")
            if (
                repository.get(
                    customer_id=mutation.entity_id,
                    organization_id=mutation.organization_id,
                )
                is not None
            ):
                raise SyncConflict("customer already exists without matching mutation receipt")
            display_name = mutation.payload.get("display_name")
            if not isinstance(display_name, str):
                raise SyncConflict("customer create requires display_name")
            email = mutation.payload.get("email")
            phone = mutation.payload.get("phone")
            customer = Customer.create(
                customer_id=mutation.entity_id,
                organization_id=mutation.organization_id,
                location_id=mutation.location_id,
                display_name=display_name,
                email=email if isinstance(email, str) else None,
                phone=phone if isinstance(phone, str) else None,
                now=_as_utc(mutation.occurred_at),
            )
            repository.add(customer)
            return _Applied(
                entity_id=customer.customer_id,
                location_id=customer.location_id,
                version=customer.version,
                payload=customer_payload(customer),
            )

        existing = repository.get(
            customer_id=mutation.entity_id,
            organization_id=mutation.organization_id,
        )
        if existing is None:
            raise SyncConflict("customer does not exist")
        if existing.location_id != mutation.location_id:
            raise SyncConflict("customer location scope mismatch")
        if mutation.base_version != existing.version:
            raise SyncConflict(
                f"base version {mutation.base_version!r} does not match "
                f"current version {existing.version}"
            )

        allowed = {"display_name", "email", "phone"}
        unknown = set(mutation.payload) - allowed
        if unknown:
            raise SyncConflict(f"unsupported customer fields: {sorted(unknown)}")
        if not mutation.payload:
            raise SyncConflict("customer update payload is empty")

        kwargs: dict[str, object] = {"now": _as_utc(mutation.occurred_at)}
        for field in allowed:
            if field in mutation.payload:
                kwargs[field] = mutation.payload[field]
        try:
            updated = existing.update(**kwargs)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SyncConflict(str(exc)) from exc
        repository.save(updated)
        return _Applied(
            entity_id=updated.customer_id,
            location_id=updated.location_id,
            version=updated.version,
            payload=customer_payload(updated),
        )

    def _apply_bicycle(self, mutation: MutationEnvelope) -> _Applied:
        customers = SqlAlchemyCustomerRepository(self._session)
        repository = SqlAlchemyBicycleRepository(self._session)
        if mutation.operation == "create":
            if mutation.base_version is not None:
                raise SyncConflict("create mutation cannot have a base version")
            customer_id = mutation.payload.get("customer_id")
            if not isinstance(customer_id, str) or not customer_id.strip():
                raise SyncConflict("bicycle create requires customer_id")
            if (
                customers.get(customer_id=customer_id, organization_id=mutation.organization_id)
                is None
            ):
                raise SyncConflict("customer does not exist")
            if (
                repository.get(
                    bicycle_id=mutation.entity_id, organization_id=mutation.organization_id
                )
                is not None
            ):
                raise SyncConflict("bicycle already exists without matching mutation receipt")
            brand = mutation.payload.get("brand")
            if not isinstance(brand, str):
                raise SyncConflict("bicycle create requires brand")

            def optional(field: str) -> str | None:
                value = mutation.payload.get(field)
                return value if isinstance(value, str) else None

            bicycle = Bicycle.create(
                bicycle_id=mutation.entity_id,
                customer_id=customer_id,
                organization_id=mutation.organization_id,
                location_id=mutation.location_id,
                brand=brand,
                model=optional("model"),
                bicycle_type=optional("bicycle_type"),
                wheel_size=optional("wheel_size"),
                notes=optional("notes"),
                now=_as_utc(mutation.occurred_at),
            )
            repository.add(bicycle)
            return _Applied(
                entity_id=bicycle.bicycle_id,
                location_id=bicycle.location_id,
                version=bicycle.version,
                payload=bicycle_payload(bicycle),
            )

        existing = repository.get(
            bicycle_id=mutation.entity_id, organization_id=mutation.organization_id
        )
        if existing is None:
            raise SyncConflict("bicycle does not exist")
        if existing.location_id != mutation.location_id:
            raise SyncConflict("bicycle location scope mismatch")
        if mutation.base_version != existing.version:
            raise SyncConflict(
                f"base version {mutation.base_version!r} does not match "
                f"current version {existing.version}"
            )
        allowed = {"brand", "model", "bicycle_type", "wheel_size", "notes"}
        unknown = set(mutation.payload) - allowed
        if unknown:
            raise SyncConflict(f"unsupported bicycle fields: {sorted(unknown)}")
        if not mutation.payload:
            raise SyncConflict("bicycle update payload is empty")
        update_kwargs: dict[str, object] = {"now": _as_utc(mutation.occurred_at)}
        for field in allowed:
            if field in mutation.payload:
                update_kwargs[field] = mutation.payload[field]
        try:
            updated = existing.update(**update_kwargs)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SyncConflict(str(exc)) from exc
        repository.save(updated)
        return _Applied(
            entity_id=updated.bicycle_id,
            location_id=updated.location_id,
            version=updated.version,
            payload=bicycle_payload(updated),
        )

    def _apply_service_order(
        self, mutation: MutationEnvelope, *, context: SyncApplicationContext | None
    ) -> _Applied:
        customers = SqlAlchemyCustomerRepository(self._session)
        bicycles = SqlAlchemyBicycleRepository(self._session)
        repository = SqlAlchemyServiceOrderRepository(self._session)
        if mutation.operation == "create":
            if mutation.base_version is not None:
                raise SyncConflict("create mutation cannot have a base version")
            customer_id = mutation.payload.get("customer_id")
            if not isinstance(customer_id, str) or not customer_id.strip():
                raise SyncConflict("service order create requires customer_id")
            if (
                customers.get(customer_id=customer_id, organization_id=mutation.organization_id)
                is None
            ):
                raise SyncConflict("customer does not exist")
            bicycle_id = mutation.payload.get("bicycle_id")
            if bicycle_id is not None:
                if not isinstance(bicycle_id, str):
                    raise SyncConflict("bicycle_id must be a string")
                if (
                    bicycles.get(bicycle_id=bicycle_id, organization_id=mutation.organization_id)
                    is None
                ):
                    raise SyncConflict("bicycle does not exist")
            reported_problem = mutation.payload.get("reported_problem")
            if not isinstance(reported_problem, str):
                raise SyncConflict("service order create requires reported_problem")
            if (
                repository.get(
                    order_id=mutation.entity_id, organization_id=mutation.organization_id
                )
                is not None
            ):
                raise SyncConflict("service order already exists without matching mutation receipt")

            def optional(field: str) -> str | None:
                value = mutation.payload.get(field)
                return value if isinstance(value, str) else None

            priority = mutation.payload.get("priority")
            order = ServiceOrder.create(
                order_id=mutation.entity_id,
                customer_id=customer_id,
                organization_id=mutation.organization_id,
                location_id=mutation.location_id,
                reported_problem=reported_problem,
                bicycle_id=bicycle_id if isinstance(bicycle_id, str) else None,
                intake_condition=optional("intake_condition"),
                accessories=optional("accessories"),
                priority=priority if isinstance(priority, str) else "normal",
                now=_as_utc(mutation.occurred_at),
            )
            repository.add(order)
            return _Applied(
                entity_id=order.order_id,
                location_id=order.location_id,
                version=order.version,
                payload=order_payload(order),
            )

        existing = repository.get(
            order_id=mutation.entity_id, organization_id=mutation.organization_id
        )
        if existing is None:
            raise SyncConflict("service order does not exist")
        if existing.location_id != mutation.location_id:
            raise SyncConflict("service order location scope mismatch")
        if mutation.base_version != existing.version:
            raise SyncConflict(
                f"base version {mutation.base_version!r} does not match "
                f"current version {existing.version}"
            )
        if not mutation.payload:
            raise SyncConflict("unsupported order update: payload is empty")
        transition = mutation.payload.get("transition")
        if not isinstance(transition, dict):
            raise SyncConflict("unsupported order update: expected a transition payload")
        action = transition.get("action")
        note = transition.get("note")
        if not isinstance(action, str):
            raise SyncConflict("transition requires action")
        if context is None:
            raise SyncConflict("transition requires authenticated actor context")
        try:
            result = existing.transition(
                action,
                # Legacy transition.actor_id is accepted but is not authority.
                actor_id=context.actor_id,
                note=note if isinstance(note, str) else None,
                now=_as_utc(mutation.occurred_at),
            )
        except InvalidStateTransitionError as exc:
            raise SyncConflict(str(exc)) from exc
        except UnknownActionError as exc:
            raise SyncConflict(str(exc)) from exc
        except ValueError as exc:
            raise SyncConflict(str(exc)) from exc
        repository.save(result.order)
        repository.add_event(result.event)
        return _Applied(
            entity_id=result.order.order_id,
            location_id=result.order.location_id,
            version=result.order.version,
            payload=order_payload(result.order),
        )

    def pull_changes(
        self,
        *,
        organization_id: str,
        location_id: str | None,
        capabilities: frozenset[str],
        after_cursor: int,
        limit: int,
    ) -> ChangePage:
        # New feed entities must declare a read permission before they can be
        # exposed, including to wildcard users. Filter before LIMIT/lookahead so
        # denied rows cannot consume a page or advance its cursor.
        read_permissions = {
            "customer": "customers.read",
            "bicycle": "bicycles.read",
            "service_order": "orders.read",
        }
        readable_types = [
            entity_type
            for entity_type, capability in read_permissions.items()
            if capability in capabilities or "*" in capabilities
        ]
        safe_limit = max(1, min(limit, 500))
        statement = select(ChangeRecord).where(
            ChangeRecord.organization_id == organization_id,
            ChangeRecord.cursor > after_cursor,
            ChangeRecord.entity_type.in_(readable_types),
        )
        if location_id is not None:
            statement = statement.where(ChangeRecord.location_id == location_id)
        statement = statement.order_by(ChangeRecord.cursor).limit(safe_limit + 1)
        records = list(self._session.scalars(statement))
        has_more = len(records) > safe_limit
        page_records = records[:safe_limit]
        items = [
            ChangeItem(
                cursor=record.cursor,
                entity_type=record.entity_type,
                entity_id=record.entity_id,
                operation=record.operation,
                organization_id=record.organization_id,
                location_id=record.location_id,
                entity_version=record.entity_version,
                occurred_at=_as_utc(record.occurred_at),
                payload=dict(record.payload),
            )
            for record in page_records
        ]
        next_cursor = items[-1].cursor if items else after_cursor
        return ChangePage(items=items, next_cursor=next_cursor, has_more=has_more)
