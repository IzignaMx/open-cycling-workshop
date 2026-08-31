from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.repository import SqlAlchemyUserRepository
from cycling_workshop.identity.schemas import CurrentUserResponse, LoginRequest, LoginResponse
from cycling_workshop.identity.security import PasswordService, SessionTokenService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> LoginResponse:
    account = SqlAlchemyUserRepository(session).get_by_username(
        organization_id=payload.organization_id,
        username=payload.username,
    )
    if (
        account is None
        or not account.is_active
        or not PasswordService().verify(account.password_hash, payload.password)
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
        )
    )
    return LoginResponse(access_token=token)


@router.get("/me", response_model=CurrentUserResponse)
def current_user(
    principal: Annotated[Principal, Depends(principal_from_request)],
    session: Annotated[Session, Depends(get_session)],
) -> CurrentUserResponse:
    account = SqlAlchemyUserRepository(session).get(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
    )
    if account is None or not account.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    return CurrentUserResponse(
        user_id=account.user_id,
        organization_id=account.organization_id,
        location_id=account.location_id,
        display_name=account.display_name,
        capabilities=sorted(account.capabilities),
    )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    principal: Annotated[Principal, Depends(principal_from_request)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    repository = SqlAlchemyUserRepository(session)
    try:
        repository.increment_session_version(
            user_id=principal.user_id,
            organization_id=principal.organization_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session"
        ) from exc
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
