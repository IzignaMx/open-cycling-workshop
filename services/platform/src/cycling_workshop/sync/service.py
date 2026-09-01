from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.events.outbox import enqueue_outbox
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
    SyncConflict,
)
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _customer_payload(customer: Customer) -> dict[str, object]:
    return {
        "customer_id": customer.customer_id,
        "organization_id": customer.organization_id,
        "location_id": customer.location_id,
        "display_name": customer.display_name,
        "email": customer.email,
        "phone": customer.phone,
        "created_at": customer.created_at.isoformat(),
        "updated_at": customer.updated_at.isoformat(),
        "version": customer.version,
    }


@dataclass(frozen=True, slots=True)
class _Applied:
    """Uniform result of an entity-specific apply step."""

    entity_id: str
    location_id: str
    version: int
    payload: dict[str, object]


def _bicycle_payload(bicycle: Bicycle) -> dict[str, object]:
    return {
        "bicycle_id": bicycle.bicycle_id,
        "customer_id": bicycle.customer_id,
        "organization_id": bicycle.organization_id,
        "location_id": bicycle.location_id,
        "brand": bicycle.brand,
        "model": bicycle.model,
        "bicycle_type": bicycle.bicycle_type,
        "wheel_size": bicycle.wheel_size,
        "notes": bicycle.notes,
        "created_at": bicycle.created_at.isoformat(),
        "updated_at": bicycle.updated_at.isoformat(),
        "version": bicycle.version,
    }


def _order_payload(order: ServiceOrder) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "bicycle_id": order.bicycle_id,
        "organization_id": order.organization_id,
        "location_id": order.location_id,
        "state": order.state,
        "reported_problem": order.reported_problem,
        "intake_condition": order.intake_condition,
        "accessories": order.accessories,
        "priority": order.priority,
        "diagnosis": order.diagnosis,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "version": order.version,
    }


class SyncService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def apply(self, mutation: MutationEnvelope) -> MutationResult:
        existing_receipt = self._session.get(MutationReceiptRecord, mutation.mutation_id)
        if existing_receipt is not None:
            if existing_receipt.organization_id != mutation.organization_id:
                raise SyncConflict("mutation id already belongs to another organization")
            return MutationResult(
                mutation_id=existing_receipt.mutation_id,
                status="applied",
                entity_id=existing_receipt.entity_id,
                entity_version=existing_receipt.entity_version,
            )

        if mutation.entity_type == "customer":
            applied = self._apply_customer(mutation)
        elif mutation.entity_type == "bicycle":
            applied = self._apply_bicycle(mutation)
        elif mutation.entity_type == "service_order":
            applied = self._apply_service_order(mutation)
        else:
            raise SyncConflict(f"unsupported entity type: {mutation.entity_type}")

        self._session.flush()

        self._session.add(
            ChangeRecord(
                organization_id=mutation.organization_id,
                location_id=applied.location_id,
                entity_type=mutation.entity_type,
                entity_id=applied.entity_id,
                operation=mutation.operation,
                entity_version=applied.version,
                occurred_at=_as_utc(mutation.occurred_at),
                payload=applied.payload,
            )
        )
        self._session.flush()

        enqueue_outbox(
            self._session,
            event_type=(
                f"{mutation.entity_type}."
                f"{'created' if mutation.operation == 'create' else 'updated'}"
            ),
            aggregate_type=mutation.entity_type,
            aggregate_id=applied.entity_id,
            organization_id=mutation.organization_id,
            location_id=applied.location_id,
            payload=applied.payload,
            occurred_at=_as_utc(mutation.occurred_at),
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
                payload=_customer_payload(customer),
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
            payload=_customer_payload(updated),
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
                payload=_bicycle_payload(bicycle),
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
            payload=_bicycle_payload(updated),
        )

    def _apply_service_order(self, mutation: MutationEnvelope) -> _Applied:
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
                payload=_order_payload(order),
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
        actor_id = transition.get("actor_id")
        note = transition.get("note")
        if not isinstance(action, str) or not isinstance(actor_id, str):
            raise SyncConflict("transition requires action and actor_id")
        try:
            result = existing.transition(
                action,
                actor_id=actor_id,
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
            payload=_order_payload(result.order),
        )

    def pull_changes(
        self,
        *,
        organization_id: str,
        location_id: str | None,
        after_cursor: int,
        limit: int,
    ) -> ChangePage:
        safe_limit = max(1, min(limit, 500))
        statement = select(ChangeRecord).where(
            ChangeRecord.organization_id == organization_id,
            ChangeRecord.cursor > after_cursor,
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
