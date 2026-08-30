from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cycling_workshop.db.base import Base


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "username", name="uq_users_org_username"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_user_location_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_users_org_active", "organization_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    username: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
