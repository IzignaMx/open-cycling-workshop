"""Explicit local adoption for one established owner, never startup or migration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.db.order_payload_size import (
    OrderPayloadCountSchemaError,
    require_order_payload_count_schema,
)
from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.admin_schemas import ScopeId, Version
from cycling_workshop.identity.audit import append_audit, user_snapshot
from cycling_workshop.identity.cutover import admit_protocol, lock_compatibility
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import (
    CAPABILITIES,
    LEGACY_WILDCARD_CAPABILITIES,
    QUOTE_CAPABILITIES,
    concrete_capabilities,
)
from cycling_workshop.quotes.models import (
    QuoteDecisionRecord,
    QuoteLineageRecord,
    QuoteLineRecord,
    QuoteLineTargetRecord,
    QuoteOperationRecord,
    QuoteRevisionRecord,
)
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id


class _AdoptionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    organization_id: ScopeId
    owner_id: ScopeId
    expected_version: Version


def _require_quote_schema(session: Session) -> None:
    """Require the complete current chain; this neither migrates nor activates.

    Revision identity alone cannot establish the required physical columns or
    generated-count definitions. Probe mapped shapes without loading any history.
    This is not installation, corruption or old-writer rollout qualification.
    """
    if not inspect(session.connection()).has_table("alembic_version") or list(
        session.scalars(text("SELECT version_num FROM alembic_version"))
    ) != ["0013"]:
        raise ApiError(409, "quote_adoption_schema_required", "complete quote schema required")
    try:
        require_order_payload_count_schema(session.connection())
        for model in (
            QuoteLineageRecord,
            QuoteRevisionRecord,
            QuoteLineRecord,
            QuoteLineTargetRecord,
            QuoteDecisionRecord,
            QuoteOperationRecord,
        ):
            session.execute(select(model).limit(0))
    except OrderPayloadCountSchemaError:
        raise ApiError(
            409, "quote_adoption_schema_required", "complete quote schema required"
        ) from None


def adopt_quotes(
    settings: Settings, *, organization_id: str, owner_id: str, expected_version: int
) -> dict[str, object]:
    target = _AdoptionTarget(
        organization_id=organization_id, owner_id=owner_id, expected_version=expected_version
    )
    engine = build_engine(settings)
    correlation = request_id_var.set(f"cli-{new_id()}")
    try:
        with Session(engine) as session:
            _require_quote_schema(session)
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
                raise ApiError(403, "quotes_adoption_denied", "active established owner required")
            if owner.version != target.expected_version:
                raise ApiError(409, "stale_user_version", "user version has changed")
            missing = QUOTE_CAPABILITIES - set(owner.capabilities)
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
                    action="user.quotes_adopted",
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
