from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.branding.assets import BrandingAssetStore
from cycling_workshop.branding.schemas import BrandingProfileResponse, BrandingPutRequest
from cycling_workshop.branding.service import BrandingService, decode_logo
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.admin_schemas import ScopeId
from cycling_workshop.identity.cutover import WriteAdmission, commit_admitted, write_admission
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize

router = APIRouter(prefix="/api/v1/locations", tags=["branding"])
Database = Annotated[Session, Depends(get_session)]
Admission = Annotated[WriteAdmission, Depends(write_admission)]
Reader = Annotated[Principal, Depends(require_capability("branding.read"))]
Writer = Annotated[Principal, Depends(require_capability("branding.write"))]


def _preflight(
    principal: Principal, location_id: str, admission: WriteAdmission, capability: str
) -> None:
    if admission.protocol != 1 or not admission.enabled:
        raise ApiError(409, "client_upgrade_required", "client upgrade required")
    admission.check_expiry(principal)
    try:
        authorize(
            principal,
            capability=capability,
            organization_id=principal.organization_id,
            location_id=location_id,
        )
    except PermissionError as exc:
        raise ApiError(403, "branding_denied", "branding scope or capability denied") from exc


def _service(request: Request, session: Session, admission: WriteAdmission) -> BrandingService:
    return BrandingService(
        session, admission, BrandingAssetStore(Path(request.app.state.settings.branding_asset_root))
    )


@router.get("/{location_id}/branding", response_model=BrandingProfileResponse)
def read_branding(
    location_id: ScopeId,
    request: Request,
    principal: Reader,
    session: Database,
    admission: Admission,
) -> BrandingProfileResponse:
    _preflight(principal, location_id, admission, "branding.read")
    return _service(request, session, admission).read(principal, location_id)


@router.put("/{location_id}/branding", response_model=BrandingProfileResponse)
def put_branding(
    location_id: ScopeId,
    payload: BrandingPutRequest,
    request: Request,
    principal: Writer,
    session: Database,
    admission: Admission,
) -> BrandingProfileResponse:
    _preflight(principal, location_id, admission, "branding.write")
    # The bounded subprocess runs before opening the write transaction/locks.
    logo = decode_logo(payload)
    response = _service(request, session, admission).put(principal, location_id, payload, logo)
    commit_admitted(session, principal, admission)
    return response
