"""Explicit local adoption for one established owner, never startup or migration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.admin_schemas import ScopeId, Version
from cycling_workshop.identity.audit import append_audit, user_snapshot
from cycling_workshop.identity.cutover import admit_protocol, lock_compatibility
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import (
    BRANDING_CAPABILITIES,
    CAPABILITIES,
    LEGACY_WILDCARD_CAPABILITIES,
    concrete_capabilities,
)
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id


class _AdoptionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    organization_id: ScopeId
    owner_id: ScopeId
    expected_version: Version


def adopt_branding(
    settings: Settings, *, organization_id: str, owner_id: str, expected_version: int
) -> dict[str, object]:
    target = _AdoptionTarget(
        organization_id=organization_id, owner_id=owner_id, expected_version=expected_version
    )
    engine = build_engine(settings)
    correlation = request_id_var.set(f"cli-{new_id()}")
    try:
        with Session(engine) as session:
            organization = lock_compatibility(session, target.organization_id)
            admit_protocol(organization, 1, True)
            owner = session.scalar(
                select(UserRecord)
                .where(
                    UserRecord.id == target.owner_id,
                    UserRecord.organization_id == target.organization_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                owner is None
                or not owner.is_active
                or not owner.is_owner
                or owner.location_id is not None
                or not set(owner.capabilities) <= CAPABILITIES | {"*"}
                or not concrete_capabilities(owner.capabilities) >= LEGACY_WILDCARD_CAPABILITIES
            ):
                raise ApiError(403, "branding_adoption_denied", "active established owner required")
            if owner.version != target.expected_version:
                raise ApiError(409, "stale_user_version", "user version has changed")
            missing = BRANDING_CAPABILITIES - set(owner.capabilities)
            if missing:
                before = user_snapshot(owner)
                # Preserve existing order, duplicates, wildcard, scope and every
                # unrelated attribute. Adoption only appends absent literals.
                owner.capabilities = [*owner.capabilities, *sorted(missing)]
                owner.version += 1
                owner.session_version += 1
                session.flush()
                append_audit(
                    session,
                    organization_id=owner.organization_id,
                    actor_id=None,
                    target_id=owner.id,
                    action="user.branding_adopted",
                    before=before,
                    after=user_snapshot(owner),
                )
                session.commit()
            return {
                "changed": bool(missing),
                "organization_id": owner.organization_id,
                "user_id": owner.id,
                "version": owner.version,
            }
    finally:
        request_id_var.reset(correlation)
        engine.dispose()
