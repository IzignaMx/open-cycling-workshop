from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.shared.ids import new_id


def _outbox_metadata(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    organization_id: str,
    location_id: str | None,
    occurred_at: datetime,
) -> tuple[str, dict[str, object]]:
    """Allocate the existing delivery identity and ordinary routing defaults."""
    event_id = new_id()
    return event_id, dict(
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        organization_id=organization_id,
        location_id=location_id,
        occurred_at=occurred_at,
        published_at=None,
        attempts=0,
    )


def enqueue_outbox(
    session: Session,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    organization_id: str,
    location_id: str | None,
    payload: dict[str, object],
    occurred_at: datetime,
) -> str:
    event_id, metadata = _outbox_metadata(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        organization_id=organization_id,
        location_id=location_id,
        occurred_at=occurred_at,
    )
    session.add(OutboxRecord(payload=payload, **metadata))
    return event_id
