from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from cycling_workshop.jobs.models import JobRecord
from cycling_workshop.shared.ids import new_id


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job_id: str
    job_type: str
    payload: dict[str, object]
    state: str
    attempts: int
    lease_until: datetime


class PostgresJobQueue:
    """Durable queue using row locking. PostgreSQL applies SKIP LOCKED in production."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        job_type: str,
        payload: dict[str, object],
        available_at: datetime,
    ) -> str:
        job_id = new_id()
        now = datetime.now(UTC)
        self._session.add(
            JobRecord(
                job_id=job_id,
                job_type=job_type,
                payload=payload,
                state="queued",
                attempts=0,
                available_at=available_at,
                lease_until=None,
                created_at=now,
                completed_at=None,
                last_error=None,
            )
        )
        return job_id

    def claim_next(
        self,
        *,
        now: datetime,
        lease_for: timedelta = timedelta(minutes=5),
    ) -> ClaimedJob | None:
        statement = (
            select(JobRecord)
            .where(
                JobRecord.available_at <= now,
                or_(
                    JobRecord.state == "queued",
                    (JobRecord.state == "running") & (JobRecord.lease_until < now),
                ),
            )
            .order_by(JobRecord.available_at, JobRecord.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        record = self._session.scalar(statement)
        if record is None:
            return None
        record.state = "running"
        record.attempts += 1
        record.lease_until = now + lease_for
        self._session.flush()
        lease_until = _as_utc(record.lease_until)
        assert lease_until is not None
        return ClaimedJob(
            job_id=record.job_id,
            job_type=record.job_type,
            payload=dict(record.payload),
            state=record.state,
            attempts=record.attempts,
            lease_until=lease_until,
        )

    def complete(self, job_id: str, *, completed_at: datetime) -> None:
        record = self._session.get(JobRecord, job_id)
        if record is None:
            raise LookupError(f"job not found: {job_id}")
        if record.state != "running":
            raise RuntimeError(f"job is not running: {job_id}")
        record.state = "completed"
        record.completed_at = completed_at
        record.lease_until = None
        record.last_error = None
        self._session.flush()

    def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry_at: datetime,
    ) -> None:
        record = self._session.get(JobRecord, job_id)
        if record is None:
            raise LookupError(f"job not found: {job_id}")
        record.state = "queued"
        record.available_at = retry_at
        record.lease_until = None
        record.last_error = error[:4000]
        self._session.flush()
