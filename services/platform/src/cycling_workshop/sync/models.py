from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


def _hex_only(expression: str) -> str:
    for character in "0123456789abcdef":
        expression = f"replace({expression}, '{character}', '')"
    return f"{expression} = ''"


class MutationReceiptRecord(Base):
    __tablename__ = "sync_mutation_receipts"
    __table_args__ = (
        Index("ix_sync_receipts_org_entity", "organization_id", "entity_type", "entity_id"),
        CheckConstraint(
            "(actor_id IS NULL AND command_digest IS NULL AND proof_version IS NULL) OR "
            "(actor_id IS NOT NULL AND command_digest IS NOT NULL AND proof_version IS NOT NULL)",
            name="ck_sync_receipt_proof_complete",
        ),
        CheckConstraint(
            "proof_version IS NULL OR proof_version = 1", name="ck_sync_receipt_proof_version"
        ),
        CheckConstraint(
            "command_digest IS NULL OR (length(command_digest) = 64 AND "
            + _hex_only("command_digest")
            + ")",
            name="ck_sync_receipt_proof_digest",
        ),
    )

    mutation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    command_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proof_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ChangeRecord(Base):
    __tablename__ = "sync_changes"
    __table_args__ = (
        Index(
            "ix_sync_changes_org_location_type_cursor",
            "organization_id",
            "location_id",
            "entity_type",
            "cursor",
        ),
        Index("ix_sync_changes_org_cursor", "organization_id", "cursor"),
        Index("ix_sync_changes_org_location_cursor", "organization_id", "location_id", "cursor"),
    )

    cursor: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False)
    location_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
