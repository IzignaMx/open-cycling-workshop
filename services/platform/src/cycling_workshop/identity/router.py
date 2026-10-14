from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.admin_schemas import ChangePasswordRequest
from cycling_workshop.identity.administration import AdministrationService
from cycling_workshop.identity.cutover import (
    WriteAdmission,
    commit_admitted,
    lock_compatibility,
    validate_incarnation,
    write_admission,
)
from cycling_workshop.identity.dependencies import effective_principal, principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.repository import SqlAlchemyUserRepository
from cycling_workshop.identity.schemas import CurrentUserResponse, LoginRequest, LoginResponse
from cycling_workshop.identity.security import PasswordService, SessionTokenService
from cycling_workshop.tenancy.models import OrganizationRecord

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> LoginResponse:
    organization = lock_compatibility(session, payload.organization_id)
    account = SqlAlchemyUserRepository(session).get_by_username(
        organization_id=payload.organization_id,
        username=payload.username,
        for_update=True,
    )
    if (
        account is None
        or not account.is_active
        or not PasswordService().verify(account.password_hash, payload.password.get_secret_value())
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    token_service: SessionTokenService = request.app.state.session_tokens
    token = token_service.issue(
        Principal(
            user_id=account.user_id,
            organization_id=account.organization_id,
            location_id=account.location_id,
            capabilities=account.capabilities,
            session_version=account.session_version,
            dataset_incarnation=organization.dataset_incarnation,
        )
    )
    return LoginResponse(access_token=token)


@router.get("/me", response_model=CurrentUserResponse)
def current_user(
    request: Request,
    principal: Annotated[Principal, Depends(principal_from_request)],
    session: Annotated[Session, Depends(get_session)],
) -> CurrentUserResponse:
    # Serialize the current-state read with administration, using the same org
    # first lock order. The dependency's earlier session is not a fresh snapshot
    # after waiting behind a revocation or scope/grant change.
    organization = session.scalar(
        select(OrganizationRecord)
        .where(OrganizationRecord.id == principal.organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    account = SqlAlchemyUserRepository(session).get(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        for_update=True,
    )
    if organization is None or account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    try:
        validate_incarnation(organization, principal)
        if (
            principal.expires_at is None
            or principal.expires_at <= request.app.state.session_tokens.now()
        ):
            raise ValueError("invalid session")
        effective = effective_principal(principal, account)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session"
        ) from exc
    return CurrentUserResponse(
        user_id=effective.user_id,
        organization_id=effective.organization_id,
        location_id=effective.location_id,
        display_name=account.display_name,
        capabilities=sorted(effective.capabilities),
    )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    principal: Annotated[Principal, Depends(principal_from_request)],
    session: Annotated[Session, Depends(get_session)],
    admission: Annotated[WriteAdmission, Depends(write_admission)],
) -> Response:
    AdministrationService(session, admission).logout_all(principal)
    commit_admitted(session, principal, admission)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    principal: Annotated[Principal, Depends(principal_from_request)],
    session: Annotated[Session, Depends(get_session)],
    admission: Annotated[WriteAdmission, Depends(write_admission)],
) -> Response:
    AdministrationService(session, admission).change_password(
        principal,
        payload.current_password.get_secret_value(),
        payload.new_password.get_secret_value(),
    )
    commit_admitted(session, principal, admission)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
