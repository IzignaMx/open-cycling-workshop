from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


class JobRecord(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        Index("ix_background_jobs_claim", "state", "available_at", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
