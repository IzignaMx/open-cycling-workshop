from datetime import UTC, datetime

from cycling_workshop.db.base import Base
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.events.outbox import enqueue_outbox
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_enqueue_outbox_persists_an_unpublished_event_in_same_session() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 7, tzinfo=UTC)

    with Session(engine) as session:
        event_id = enqueue_outbox(
            session,
            event_type="customer.created",
            aggregate_type="customer",
            aggregate_id="018f0000-0000-7000-8000-000000000001",
            organization_id="org-1",
            location_id="loc-1",
            payload={"display_name": "Ana"},
            occurred_at=now,
        )
        session.flush()
        record = session.scalar(select(OutboxRecord).where(OutboxRecord.event_id == event_id))

    assert record is not None
    assert record.event_type == "customer.created"
    assert record.published_at is None
    assert record.attempts == 0
    assert record.payload == {"display_name": "Ana"}
