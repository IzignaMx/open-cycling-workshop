from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.admin_schemas import (
    CreateLocationRequest,
    CreateUserRequest,
    LocationPage,
    LocationResponse,
    PatchUserRequest,
    ResetPasswordRequest,
    RoleCatalogResponse,
    RoleResponse,
    ScopeId,
    UserPage,
    UserResponse,
    VersionRequest,
)
from cycling_workshop.identity.administration import AdministrationService, require, user_response
from cycling_workshop.identity.dependencies import principal_from_request
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES, ROLE_BUNDLES
from cycling_workshop.tenancy.models import LocationRecord

router = APIRouter(tags=["administration"])
Actor = Annotated[Principal, Depends(principal_from_request)]
Database = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=200)]
Cursor = Annotated[ScopeId | None, Query()]


@router.get("/api/v1/admin/roles", response_model=RoleCatalogResponse)
def roles(principal: Actor) -> RoleCatalogResponse:
    require(principal, "users.read")
    return RoleCatalogResponse(
        roles=[
            RoleResponse(name=name, capabilities=sorted(grants))
            for name, grants in ROLE_BUNDLES.items()
        ],
        capabilities=sorted(CAPABILITIES),
    )


@router.get("/api/v1/admin/users", response_model=UserPage)
def users(
    principal: Actor,
    session: Database,
    limit: Limit = 50,
    after_id: Cursor = None,
    active: bool | None = None,
) -> UserPage:
    require(principal, "users.read")
    query = select(UserRecord).where(UserRecord.organization_id == principal.organization_id)
    if principal.location_id is not None:
        query = query.where(UserRecord.location_id == principal.location_id)
    if active is not None:
        query = query.where(UserRecord.is_active == active)
    if after_id is not None:
        query = query.where(UserRecord.id > after_id)
    rows = list(session.scalars(query.order_by(UserRecord.id).limit(limit + 1)))
    items = rows[:limit]
    return UserPage(
        items=[user_response(user) for user in items],
        next_cursor=items[-1].id if len(rows) > limit else None,
    )


@router.post("/api/v1/admin/users", response_model=UserResponse, status_code=201)
def create_user(payload: CreateUserRequest, principal: Actor, session: Database) -> UserResponse:
    user = AdministrationService(session).create_user(principal, payload)
    session.commit()
    return user_response(user)


@router.get("/api/v1/locations", response_model=LocationPage)
def locations(
    principal: Actor, session: Database, limit: Limit = 50, after_id: Cursor = None
) -> LocationPage:
    require(principal, "locations.read")
    query = select(LocationRecord).where(
        LocationRecord.organization_id == principal.organization_id
    )
    if principal.location_id is not None:
        query = query.where(LocationRecord.id == principal.location_id)
    if after_id is not None:
        query = query.where(LocationRecord.id > after_id)
    rows = list(session.scalars(query.order_by(LocationRecord.id).limit(limit + 1)))
    items = rows[:limit]
    return LocationPage(
        items=[
            LocationResponse(
                location_id=location.id,
                organization_id=location.organization_id,
                name=location.name,
            )
            for location in items
        ],
        next_cursor=items[-1].id if len(rows) > limit else None,
    )


@router.patch("/api/v1/admin/users/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: ScopeId, payload: PatchUserRequest, principal: Actor, session: Database
) -> UserResponse:
    user = AdministrationService(session).patch_user(principal, user_id, payload)
    session.commit()
    return user_response(user)


@router.post("/api/v1/admin/users/{user_id}/revoke-sessions", response_model=UserResponse)
def revoke_sessions(
    user_id: ScopeId, payload: VersionRequest, principal: Actor, session: Database
) -> UserResponse:
    user = AdministrationService(session).revoke_sessions(
        principal, user_id, payload.expected_version
    )
    session.commit()
    return user_response(user)


@router.post("/api/v1/admin/users/{user_id}/reset-password", response_model=UserResponse)
def reset_password(
    user_id: ScopeId, payload: ResetPasswordRequest, principal: Actor, session: Database
) -> UserResponse:
    user = AdministrationService(session).revoke_sessions(
        principal,
        user_id,
        payload.expected_version,
        new_password=payload.new_password.get_secret_value(),
    )
    session.commit()
    return user_response(user)


@router.post("/api/v1/locations", response_model=LocationResponse, status_code=201)
def create_location(
    payload: CreateLocationRequest, principal: Actor, session: Database
) -> LocationResponse:
    location = AdministrationService(session).create_location(principal, payload.name)
    session.commit()
    return LocationResponse(
        location_id=location.id, organization_id=location.organization_id, name=location.name
    )
