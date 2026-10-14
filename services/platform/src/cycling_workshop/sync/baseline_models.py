"""Bounded durable pagination metadata, never authentication or business history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.functions import FunctionElement

from cycling_workshop.db.base import Base


class utf8_bytes(FunctionElement[int]):
    type = Integer()
    inherit_cache = True


@compiles(utf8_bytes)
def _default_bytes(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return f"octet_length({compiler.process(element.clauses, **kw)})"


@compiles(utf8_bytes, "sqlite")
def _sqlite_bytes(element, compiler, **kw):  # type: ignore[no-untyped-def]
    return f"length(CAST({compiler.process(element.clauses, **kw)} AS BLOB))"


class BaselineFamily(Base):
    __tablename__ = "sync_baseline_families"

    reference_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    baseline_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    epoch: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    family_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    phase: Mapped[str] = mapped_column(String(24), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start_json: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    predecessor_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_baseline_user_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_baseline_location_tenant",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_baseline_start",
            "organization_id",
            "user_id",
            "location_id",
            "epoch",
            "request_id",
            unique=True,
        ),
        Index(
            "ix_baseline_org_user_location", "organization_id", "user_id", "location_id", "phase"
        ),
        Index("ix_baseline_org_retention", "organization_id", "retention_until"),
        Index("ix_baseline_user", "user_id"),
        CheckConstraint(sequence >= 0, name="ck_baseline_sequence_positive"),
        CheckConstraint(sequence <= 9007199254740991, name="ck_baseline_sequence_safe"),
        CheckConstraint(utf8_bytes(start_json) <= 16384, name="ck_baseline_start_bytes"),
        CheckConstraint(utf8_bytes(state_json) <= 16384, name="ck_baseline_state_bytes"),
        CheckConstraint(utf8_bytes(response_json) <= 1048576, name="ck_baseline_response_bytes"),
    )
