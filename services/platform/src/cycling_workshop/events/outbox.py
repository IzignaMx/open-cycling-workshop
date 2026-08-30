from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.shared.ids import new_id


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
    event_id = new_id()
    session.add(
        OutboxRecord(
            event_id=event_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            organization_id=organization_id,
            location_id=location_id,
            payload=payload,
            occurred_at=occurred_at,
            published_at=None,
            attempts=0,
        )
    )
    return event_id
