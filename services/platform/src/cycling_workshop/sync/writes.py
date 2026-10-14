"""Transaction-owned supported projection writes; never commits independently."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.events.outbox import enqueue_outbox
from cycling_workshop.identity.administration import AdministrationService
from cycling_workshop.identity.domain import Principal
from cycling_workshop.sync.models import ChangeRecord
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


def lock_writer(session: Session, principal: Principal) -> Principal:
    """Reuse audited org→actor lock and refresh effective grants after waiting.

    Administration already uses this same organization row, so revocation cannot
    commit between this refresh and the writer's transaction completion.
    """
    _, effective = AdministrationService(session).lock_actor(principal)
    return effective


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
) -> None:
    """Append exactly one projection and outbox event under the caller's lock."""
    session.add(
        ChangeRecord(
            organization_id=organization_id,
            location_id=location_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=operation,
            entity_version=entity_version,
            occurred_at=occurred_at,
            payload=payload,
        )
    )
    session.flush()
    enqueue_outbox(
        session,
        event_type=f"{entity_type}.{'created' if operation == 'create' else 'updated'}",
        aggregate_type=entity_type,
        aggregate_id=entity_id,
        organization_id=organization_id,
        location_id=location_id,
        payload=payload,
        occurred_at=occurred_at,
    )
