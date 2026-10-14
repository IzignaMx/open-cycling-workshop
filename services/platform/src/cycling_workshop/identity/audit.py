"""Secret-free administration history. Migrations install append-only DB triggers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.shared.ids import new_id


class IdentityAuditRecord(Base):
    __tablename__ = "identity_audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["actor_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_identity_audit_actor_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_id", "organization_id"],
            ["users.id", "users.organization_id"],
            name="fk_identity_audit_target_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "target_type IN ('user', 'location')", name="ck_identity_audit_target_type"
        ),
        CheckConstraint(
            "target_type = 'user' OR target_id IS NULL", name="ck_identity_audit_target_reference"
        ),
        Index("ix_identity_audit_org_time", "organization_id", "occurred_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)


def user_snapshot(user: UserRecord) -> dict[str, Any]:
    # Intentionally excludes names, username and every credential-derived value.
    return {
        "location_id": user.location_id,
        "capabilities": sorted(user.capabilities),
        "is_active": user.is_active,
        "is_owner": user.is_owner,
        "version": user.version,
        "session_version": user.session_version,
    }


def append_audit(
    session: Session,
    *,
    organization_id: str,
    actor_id: str | None,
    target_id: str | None,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any],
    target_type: str = "user",
) -> None:
    # Request IDs are generated server-side; no untrusted header/request body enters audit.
    session.add(
        IdentityAuditRecord(
            id=new_id(),
            organization_id=organization_id,
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            before=before,
            after=after,
            occurred_at=datetime.now(UTC),
            request_id=request_id_var.get(),
            target_type=target_type,
        )
    )
    session.flush()
