from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from cycling_workshop.db.session import build_engine, build_session_factory
from cycling_workshop.jobs.queue import PostgresJobQueue
from cycling_workshop.settings import Settings

JobHandler = Callable[[dict[str, object]], None]


def run_once(
    session: Session,
    *,
    handlers: Mapping[str, JobHandler],
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(UTC)
    queue = PostgresJobQueue(session)
    job = queue.claim_next(now=now)
    if job is None:
        return False
    handler = handlers.get(job.job_type)
    if handler is None:
        queue.fail(
            job.job_id,
            error=f"no handler registered for {job.job_type}",
            retry_at=now + timedelta(minutes=5),
        )
        return True
    try:
        handler(job.payload)
    except Exception as exc:
        retry_delay = min(60, 2 ** min(job.attempts, 6))
        queue.fail(
            job.job_id,
            error=f"{type(exc).__name__}: {exc}",
            retry_at=now + timedelta(minutes=retry_delay),
        )
        return True
    queue.complete(job.job_id, completed_at=now)
    return True


def main() -> int:
    settings = Settings.from_env()
    engine = build_engine(settings)
    factory = build_session_factory(engine)
    handlers: dict[str, JobHandler] = {}
    try:
        while True:
            with factory() as session:
                handled = run_once(session, handlers=handlers)
                session.commit()
            if not handled:
                time.sleep(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        engine.dispose()
