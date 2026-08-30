from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from cycling_workshop.db.base import Base
from cycling_workshop.jobs.models import JobRecord
from cycling_workshop.jobs.queue import PostgresJobQueue
from cycling_workshop.worker import run_once


def test_worker_run_once_dispatches_and_completes_job() -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    now = datetime(2026, 8, 7, tzinfo=UTC)
    observed: list[dict[str, object]] = []

    with Session(engine) as session:
        job_id = PostgresJobQueue(session).enqueue(
            job_type='demo.handle',
            payload={'customer_id': 'customer-1'},
            available_at=now,
        )
        session.commit()

        handled = run_once(
            session,
            handlers={'demo.handle': observed.append},
            now=now,
        )
        session.commit()
        record = session.scalar(select(JobRecord).where(JobRecord.job_id == job_id))

    assert handled is True
    assert observed == [{'customer_id': 'customer-1'}]
    assert record is not None
    assert record.state == 'completed'
    assert record.completed_at is not None
