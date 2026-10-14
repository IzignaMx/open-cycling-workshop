"""Authenticated context prerequisite; never advertise an unavailable baseline."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta
from typing import Annotated, Final

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.admin_schemas import ScopeId
from cycling_workshop.identity.context_schemas import AccessContextResponse, ContextPrincipal
from cycling_workshop.identity.dependencies import _extract_bearer, effective_principal
from cycling_workshop.identity.repository import SqlAlchemyUserRepository
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
POLICY_REVISION: Final = "ocwp-access-baseline-1"
OFFLINE_LEASE = timedelta(hours=8)


@router.get("/context", response_model=AccessContextResponse)
def access_context(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    selected_location_id: Annotated[ScopeId | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AccessContextResponse:
    service: SessionTokenService = request.app.state.session_tokens
    try:
        validated = service.decode_session(_extract_bearer(authorization))
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=401, detail="invalid session") from exc
    original = validated.principal
    organization = session.scalar(
        select(OrganizationRecord)
        .where(OrganizationRecord.id == original.organization_id)
        .with_for_update()
    )
    account = SqlAlchemyUserRepository(session).get(
        user_id=original.user_id, organization_id=original.organization_id, for_update=True
    )
    try:
        if organization is None or validated.expires_at <= service.now():
            raise ValueError("invalid session")
        effective = effective_principal(original, account)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid session") from exc

    selected = selected_location_id if selected_location_id is not None else effective.location_id
    if selected is None:
        raise ApiError(422, "location_required", "a concrete location is required")
    if effective.location_id is not None and selected != effective.location_id:
        raise HTTPException(status_code=403, detail="location denied")
    location = session.scalar(
        select(LocationRecord.id).where(
            LocationRecord.id == selected,
            LocationRecord.organization_id == effective.organization_id,
        )
    )
    if location is None:
        # Do not distinguish nonexistent locations from another tenant's rows.
        raise HTTPException(status_code=403, detail="location denied")
    capabilities = sorted(
        CAPABILITIES if "*" in effective.capabilities else CAPABILITIES & effective.capabilities
    )
    epoch_input = [
        "ocwp-access-epoch-v1",
        None,
        effective.user_id,
        effective.organization_id,
        effective.location_id,
        capabilities,
        effective.session_version,
        POLICY_REVISION,
    ]
    epoch = (
        base64.urlsafe_b64encode(
            hashlib.sha256(
                json.dumps(epoch_input, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    verified_at = service.now()
    if validated.expires_at <= verified_at:
        raise HTTPException(status_code=401, detail="invalid session")
    return AccessContextResponse(
        protocol=1,
        principal=ContextPrincipal(
            api_realm=None, organization_id=effective.organization_id, user_id=effective.user_id
        ),
        account_location_id=effective.location_id,
        selected_location_id=selected,
        capabilities=capabilities,
        authorization_epoch=epoch,
        policy_revision=POLICY_REVISION,
        verified_at=verified_at,
        offline_until=min(validated.expires_at, verified_at + OFFLINE_LEASE),
        snapshot_protocol=None,
    )
