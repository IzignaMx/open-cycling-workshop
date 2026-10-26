"""Transaction-owned supported projection writes; never commits independently."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy import Text, bindparam, select, text
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.events.outbox import _outbox_metadata, enqueue_outbox
from cycling_workshop.identity.administration import AdministrationService
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.sync.models import ChangeRecord
from cycling_workshop.sync.order_projection_integrity import (
    OrderProjectionIntegrityError,
    PreparedOrderProjection,
    decode_order_projection,
)
from cycling_workshop.tenancy.models import OrganizationRecord


def lock_organization(session: Session, organization_id: str) -> None:
    """Serialize allocation through commit, using the administration lock order.

    Call before domain/receipt reads or writes. PostgreSQL READ COMMITTED is the
    supported runtime. SQLite ignores FOR UPDATE and proves no concurrency claim.
    """
    organization = session.scalar(
        select(OrganizationRecord).where(OrganizationRecord.id == organization_id).with_for_update()
    )
    if organization is None:
        raise ApiError(401, "invalid_session", "invalid session")


def lock_writer(session: Session, principal: Principal, admission: WriteAdmission) -> Principal:
    """Reuse audited org→actor lock and refresh effective grants after waiting.

    Administration already uses this same organization row, so revocation cannot
    commit between this refresh and the writer's transaction completion.
    """
    if session.in_nested_transaction():
        raise RuntimeError("writer admission must precede item savepoints")
    actor, effective = AdministrationService(session, admission).lock_actor(principal)
    # Administration expands wildcard grants for its own policy. Operational
    # HTTP authentication uses literal intersection; preserve that policy again
    # after waiting, without restoring authority absent from the incoming snapshot.
    admitted = replace(
        effective,
        capabilities=frozenset(actor.capabilities).intersection(principal.capabilities),
    )
    # The identity and transaction object are issued by this actual barrier.
    # A bare Session ID or active transaction is not admission evidence.
    session.info["ocwp_write_admission"] = (session.get_transaction(), admitted, admission)
    return admitted


@dataclass(frozen=True, slots=True)
class ChangeAppendResult:
    cursor: int
    outbox_event_id: str


def _validate_prepared_order_change(
    *,
    organization_id: str,
    location_id: str,
    entity_id: str,
    entity_version: int,
    occurred_at: datetime,
    projection: PreparedOrderProjection,
) -> None:
    """Recheck the private prepared boundary without session access or writes.

    A frozen dataclass alone cannot prove that its constructor or fields were
    not bypassed. Preparation and persistence use this same identity check.
    """
    if type(projection) is not PreparedOrderProjection:
        raise OrderProjectionIntegrityError("invalid prepared order projection")
    validated = decode_order_projection(projection.raw_json, stored_octets=projection.raw_octets)
    if (
        type(projection.payload) is not type(validated.payload)
        or type(projection.canonical_utf8) is not bytes
        or projection.canonical_utf8 != validated.canonical_utf8
        or projection.payload.keys() != validated.payload.keys()
        or any(type(key) is not str for key in projection.payload)
        or any(
            type(value) is not type(validated.payload[key]) or value != validated.payload[key]
            for key, value in projection.payload.items()
        )
    ):
        raise OrderProjectionIntegrityError("invalid prepared order projection")
    if (
        any(
            type(value) is not str or value != validated.payload[key]
            for key, value in (
                ("organization_id", organization_id),
                ("location_id", location_id),
                ("order_id", entity_id),
            )
        )
        or type(entity_version) is not int
        or entity_version != validated.payload["version"]
        or type(occurred_at) is not datetime
        or occurred_at.utcoffset() is None
        or occurred_at.astimezone(UTC).isoformat() != validated.payload["updated_at"]
    ):
        raise OrderProjectionIntegrityError("prepared order metadata mismatch")


def _append_prepared_order_change(
    session: Session,
    *,
    organization_id: str,
    location_id: str,
    entity_id: str,
    entity_version: int,
    occurred_at: datetime,
    projection: PreparedOrderProjection,
) -> ChangeAppendResult:
    """Persist measured quote-linked update bytes in the owning transaction.

    PostgreSQL receives Text cast to JSON, never the ORM JSON serializer. SQLite
    receives bare Text because its JSON cast does not preserve JSON documents.
    """
    _validate_prepared_order_change(
        organization_id=organization_id,
        location_id=location_id,
        entity_id=entity_id,
        entity_version=entity_version,
        occurred_at=occurred_at,
        projection=projection,
    )
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("prepared order writes require PostgreSQL or SQLite")

    raw_bind = bindparam("prepared_order_payload", projection.raw_json, type_=Text())
    payload = (
        text("CAST(:prepared_order_payload AS pg_catalog.json)").bindparams(raw_bind)
        if dialect == "postgresql"
        else raw_bind
    )
    change_table = ChangeRecord.metadata.tables[ChangeRecord.__tablename__]
    cursor = session.execute(
        change_table.insert()
        .values(
            organization_id=organization_id,
            location_id=location_id,
            entity_type="service_order",
            entity_id=entity_id,
            operation="update",
            entity_version=entity_version,
            occurred_at=occurred_at,
            payload=payload,
        )
        .returning(change_table.c.cursor)
    ).scalar_one()
    outbox_event_id, metadata = _outbox_metadata(
        event_type="service_order.updated",
        aggregate_type="service_order",
        aggregate_id=entity_id,
        organization_id=organization_id,
        location_id=location_id,
        occurred_at=occurred_at,
    )
    outbox_table = OutboxRecord.metadata.tables[OutboxRecord.__tablename__]
    session.execute(outbox_table.insert().values(payload=payload, **metadata))
    return ChangeAppendResult(cursor, outbox_event_id)


def append_change(
    session: Session,
    *,
    organization_id: str,
    location_id: str,
    entity_type: str,
    entity_id: str,
    operation: str,
    entity_version: int,
    occurred_at: datetime,
    payload: dict[str, object],
) -> ChangeAppendResult:
    """Append exactly one projection and outbox event under the caller's lock."""
    change = ChangeRecord(
        organization_id=organization_id,
        location_id=location_id,
        entity_type=entity_type,
        entity_id=entity_id,
        operation=operation,
        entity_version=entity_version,
        occurred_at=occurred_at,
        payload=payload,
    )
    session.add(change)
    session.flush()
    outbox_event_id = enqueue_outbox(
        session,
        event_type=f"{entity_type}.{'created' if operation == 'create' else 'updated'}",
        aggregate_type=entity_type,
        aggregate_id=entity_id,
        organization_id=organization_id,
        location_id=location_id,
        payload=payload,
        occurred_at=occurred_at,
    )
    return ChangeAppendResult(change.cursor, outbox_event_id)
