from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.repository import SqlAlchemyCustomerRepository
from cycling_workshop.events.outbox import enqueue_outbox
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

        if mutation.entity_type != "customer":
            raise SyncConflict(f"unsupported entity type: {mutation.entity_type}")

        customer = self._apply_customer(mutation)
        self._session.flush()

        change = ChangeRecord(
            organization_id=mutation.organization_id,
            location_id=customer.location_id,
            entity_type="customer",
            entity_id=customer.customer_id,
            operation=mutation.operation,
            entity_version=customer.version,
            occurred_at=_as_utc(mutation.occurred_at),
            payload=_customer_payload(customer),
        )
        self._session.add(change)
        self._session.flush()

        enqueue_outbox(
            self._session,
            event_type=f"customer.{'created' if mutation.operation == 'create' else 'updated'}",
            aggregate_type="customer",
            aggregate_id=customer.customer_id,
            organization_id=mutation.organization_id,
            location_id=customer.location_id,
            payload=_customer_payload(customer),
            occurred_at=_as_utc(mutation.occurred_at),
        )

        receipt = MutationReceiptRecord(
            mutation_id=mutation.mutation_id,
            organization_id=mutation.organization_id,
            location_id=customer.location_id,
            entity_type="customer",
            entity_id=customer.customer_id,
            operation=mutation.operation,
            status="applied",
            entity_version=customer.version,
            applied_at=datetime.now(UTC),
        )
        self._session.add(receipt)
        self._session.flush()
        return MutationResult(
            mutation_id=mutation.mutation_id,
            status="applied",
            entity_id=customer.customer_id,
            entity_version=customer.version,
        )

    def _apply_customer(self, mutation: MutationEnvelope) -> Customer:
        repository = SqlAlchemyCustomerRepository(self._session)
        if mutation.operation == "create":
            if mutation.base_version is not None:
                raise SyncConflict("create mutation cannot have a base version")
            if repository.get(
                customer_id=mutation.entity_id,
                organization_id=mutation.organization_id,
            ) is not None:
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
            return customer

        customer = repository.get(
            customer_id=mutation.entity_id,
            organization_id=mutation.organization_id,
        )
        if customer is None:
            raise SyncConflict("customer does not exist")
        if customer.location_id != mutation.location_id:
            raise SyncConflict("customer location scope mismatch")
        if mutation.base_version != customer.version:
            raise SyncConflict(
                f"base version {mutation.base_version!r} does not match current version {customer.version}"
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
            updated = customer.update(**kwargs)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SyncConflict(str(exc)) from exc
        repository.save(updated)
        return updated

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
