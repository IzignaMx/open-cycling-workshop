"""Disposable lab metadata, deliberately separate from Core Base and Alembic."""

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class LabBase(DeclarativeBase):
    pass


class Installation(LabBase):
    __tablename__ = "m2_lab_installations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String)
    location_id: Mapped[str] = mapped_column(String)
    incarnation: Mapped[str] = mapped_column(String)
    run_id: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean)
    catalogue_read: Mapped[bool] = mapped_column(Boolean)


class Machine(LabBase):
    __tablename__ = "m2_lab_machines"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    installation_id: Mapped[str] = mapped_column(String)
    organization_id: Mapped[str] = mapped_column(String)
    location_id: Mapped[str] = mapped_column(String)
    incarnation: Mapped[str] = mapped_column(String)
    run_id: Mapped[str] = mapped_column(String)
    generation: Mapped[int] = mapped_column(Integer)
    verifier: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean)
    catalogue_read: Mapped[bool] = mapped_column(Boolean)
    revoked: Mapped[bool] = mapped_column(Boolean)
    issued_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)


class Audit(LabBase):
    __tablename__ = "m2_lab_audit"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    request_id: Mapped[str] = mapped_column(String, unique=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    organization_id: Mapped[str] = mapped_column(String)
    installation_id: Mapped[str] = mapped_column(String)
    machine_id: Mapped[str] = mapped_column(String)
    generation: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[float] = mapped_column(Float)
    policy: Mapped[str] = mapped_column(String)
