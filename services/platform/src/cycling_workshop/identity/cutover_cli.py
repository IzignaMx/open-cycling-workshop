"""Explicit local cutover maintenance using the installation's configured DB.

No HTTP toggle, floor lowering, session-counter increment or implicit recovery.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.audit import IdentityAuditRecord, append_audit
from cycling_workshop.identity.cutover import lock_compatibility
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord


def _state(organization: OrganizationRecord) -> dict[str, object]:
    return {
        "organization_id": organization.id,
        "minimum_write_protocol": organization.minimum_write_protocol,
        "dataset_incarnation": organization.dataset_incarnation,
    }


def cutover_status(settings: Settings, *, organization_id: str) -> dict[str, object]:
    engine = build_engine(settings)
    try:
        with Session(engine) as session:
            organization = lock_compatibility(session, organization_id)
            audit = session.scalar(
                select(IdentityAuditRecord)
                .where(
                    IdentityAuditRecord.organization_id == organization_id,
                    IdentityAuditRecord.target_type == "organization",
                    IdentityAuditRecord.action.in_(
                        ["organization.cutover_activated", "organization.dataset_recovered"]
                    ),
                )
                .order_by(IdentityAuditRecord.occurred_at.desc(), IdentityAuditRecord.id.desc())
                .limit(1)
            )
            return _state(organization) | {
                "cutover_enabled": settings.cutover_enabled,
                "latest_maintenance_audit": None
                if audit is None
                else {
                    "id": audit.id,
                    "action": audit.action,
                    "before": audit.before,
                    "after": audit.after,
                    "occurred_at": audit.occurred_at.isoformat(),
                    "request_id": audit.request_id,
                },
            }
    finally:
        engine.dispose()


def _change(
    settings: Settings, *, organization_id: str, expected_incarnation: str | None
) -> dict[str, object]:
    if expected_incarnation is None and not settings.cutover_enabled:
        raise ApiError(
            409, "cutover_composition_disabled", "qualified cutover composition required"
        )
    if expected_incarnation is not None:
        try:
            if str(UUID(expected_incarnation)) != expected_incarnation:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ApiError(
                422, "invalid_incarnation", "canonical expected incarnation required"
            ) from None
    engine = build_engine(settings)
    correlation = request_id_var.set(f"cli-{new_id()}")
    try:
        with Session(engine) as session:
            if engine.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            organization = lock_compatibility(session, organization_id)
            before = _state(organization)
            if expected_incarnation is None:
                if organization.minimum_write_protocol == 1:
                    return before | {"changed": False}
                organization.minimum_write_protocol = 1
                action = "organization.cutover_activated"
            else:
                if organization.minimum_write_protocol != 1:
                    raise ApiError(409, "cutover_not_active", "recovery requires active cutover")
                if organization.dataset_incarnation != expected_incarnation:
                    raise ApiError(
                        409,
                        "incarnation_precondition_failed",
                        "inspect current state and audit before recovery",
                    )
                incarnation = str(uuid4())
                if incarnation == organization.dataset_incarnation:
                    raise ApiError(
                        409, "incarnation_collision", "fresh recovery incarnation required"
                    )
                organization.dataset_incarnation = incarnation
                action = "organization.dataset_recovered"
            after = _state(organization)
            append_audit(
                session,
                organization_id=organization.id,
                actor_id=None,
                target_id=None,
                action=action,
                before=before,
                after=after,
                target_type="organization",
            )
            session.commit()
            return after | {"changed": True}
    finally:
        request_id_var.reset(correlation)
        engine.dispose()


def activate_cutover(settings: Settings, *, organization_id: str) -> dict[str, object]:
    return _change(settings, organization_id=organization_id, expected_incarnation=None)


def recover_cutover(
    settings: Settings, *, organization_id: str, expected_incarnation: str
) -> dict[str, object]:
    if not isinstance(expected_incarnation, str):
        raise ApiError(422, "invalid_incarnation", "canonical expected incarnation required")
    return _change(
        settings, organization_id=organization_id, expected_incarnation=expected_incarnation
    )
