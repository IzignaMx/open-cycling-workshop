from datetime import UTC, datetime, timedelta

from cycling_workshop.db.base import Base
from cycling_workshop.jobs.queue import PostgresJobQueue
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_claim_next_marks_job_running_and_leases_it() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 7, tzinfo=UTC)

    with Session(engine) as session:
        queue = PostgresJobQueue(session)
        job_id = queue.enqueue(
            job_type="communication.send",
            payload={"message_id": "msg-1"},
            available_at=now,
        )
        session.commit()

    with Session(engine) as session:
        claimed = PostgresJobQueue(session).claim_next(now=now, lease_for=timedelta(minutes=2))
        session.commit()

    assert claimed is not None
    assert claimed.job_id == job_id
    assert claimed.state == "running"
    assert claimed.attempts == 1
    assert claimed.lease_until == now + timedelta(minutes=2)


def test_claim_next_ignores_jobs_not_yet_available() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 7, tzinfo=UTC)

    with Session(engine) as session:
        queue = PostgresJobQueue(session)
        queue.enqueue(job_type="future", payload={}, available_at=now + timedelta(hours=1))
        session.commit()

    with Session(engine) as session:
        assert PostgresJobQueue(session).claim_next(now=now) is None
