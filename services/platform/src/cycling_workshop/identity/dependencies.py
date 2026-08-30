from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.repository import SqlAlchemyUserRepository
from cycling_workshop.identity.security import SessionTokenService


def _extract_bearer(authorization: str | None) -> str:
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
    return token


def principal_from_request(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    token = _extract_bearer(authorization)
    service: SessionTokenService = request.app.state.session_tokens
    try:
        token_principal = service.decode(token)
        factory = request.app.state.session_factory
        if factory is None:
            return token_principal
        with factory() as session:
            account = SqlAlchemyUserRepository(session).get(
                user_id=token_principal.user_id,
                organization_id=token_principal.organization_id,
            )
        if account is None or not account.is_active or account.session_version != token_principal.session_version:
            raise ValueError("session no longer valid")
        if token_principal.location_id is not None and account.location_id is not None and token_principal.location_id != account.location_id:
            raise ValueError("session scope changed")
        effective_location = token_principal.location_id if token_principal.location_id is not None else account.location_id
        return Principal(
            user_id=account.user_id,
            organization_id=account.organization_id,
            location_id=effective_location,
            capabilities=account.capabilities.intersection(token_principal.capabilities),
            session_version=account.session_version,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session") from exc


def require_capability(capability: str) -> Callable[..., Principal]:
    def dependency(principal: Annotated[Principal, Depends(principal_from_request)]) -> Principal:
        if capability not in principal.capabilities and "*" not in principal.capabilities:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="capability denied")
        return principal

    return dependency
