"""Tenant-scoped administration serialized at the organization boundary."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.admin_schemas import (
    CreateUserRequest,
    PatchUserRequest,
    UserResponse,
)
from cycling_workshop.identity.audit import append_audit, user_snapshot
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.repository import normalize_username
from cycling_workshop.identity.roles import CAPABILITIES, concrete_capabilities
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def denied() -> ApiError:
    return ApiError(403, "administration_denied", "administration scope or capability denied")


def require(principal: Principal, *capabilities: str) -> None:
    if not set(capabilities) <= concrete_capabilities(principal.capabilities):
        raise denied()


def user_response(user: UserRecord) -> UserResponse:
    return UserResponse(
        user_id=user.id,
        organization_id=user.organization_id,
        location_id=user.location_id,
        username=user.username,
        display_name=user.display_name,
        capabilities=sorted(user.capabilities),
        is_active=user.is_active,
        is_owner=user.is_owner,
        version=user.version,
    )


class AdministrationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_actor(self, principal: Principal) -> tuple[UserRecord, Principal]:
        """Lock org BEFORE reading actor/target, then reauthorize the current session.

        The request dependency deliberately uses a separate session. Its snapshot
        is insufficient after waiting behind another administration transaction.
        All admin writers and local first-owner setup use this lock order.
        """
        organization = self.session.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == principal.organization_id)
            .with_for_update()
        )
        if organization is None:
            raise ApiError(401, "invalid_session", "invalid session")
        actor = self.session.scalar(
            select(UserRecord)
            .where(
                UserRecord.id == principal.user_id,
                UserRecord.organization_id == principal.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            actor is None
            or not actor.is_active
            or actor.session_version != principal.session_version
            or (
                actor.location_id is not None
                and principal.location_id is not None
                and actor.location_id != principal.location_id
            )
        ):
            raise ApiError(401, "invalid_session", "invalid session")
        effective = Principal(
            user_id=actor.id,
            organization_id=actor.organization_id,
            location_id=actor.location_id or principal.location_id,
            capabilities=concrete_capabilities(actor.capabilities).intersection(
                concrete_capabilities(principal.capabilities)
            ),
            session_version=actor.session_version,
        )
        return actor, effective

    def check_location(self, principal: Principal, location_id: str | None) -> None:
        if principal.location_id is not None and location_id != principal.location_id:
            raise denied()
        if (
            location_id is not None
            and self.session.scalar(
                select(LocationRecord.id).where(
                    LocationRecord.id == location_id,
                    LocationRecord.organization_id == principal.organization_id,
                )
            )
            is None
        ):
            raise denied()

    def check_grants(self, principal: Principal, grants: frozenset[str]) -> None:
        if not grants <= concrete_capabilities(principal.capabilities):
            raise denied()

    def create_user(self, principal: Principal, payload: CreateUserRequest) -> UserRecord:
        actor, principal = self.lock_actor(principal)
        require(principal, "users.write", "users.grants.write")
        self.check_location(principal, payload.location_id)
        grants = payload.resolved_grants()
        self.check_grants(principal, grants)
        if payload.is_owner and not actor.is_owner:
            raise denied()
        if payload.is_owner and (payload.location_id is not None or grants != CAPABILITIES):
            raise ApiError(
                422, "invalid_owner", "owners require organization scope and all capabilities"
            )
        username = normalize_username(payload.username)
        if (
            self.session.scalar(
                select(UserRecord.id).where(
                    UserRecord.organization_id == principal.organization_id,
                    UserRecord.username == username,
                )
            )
            is not None
        ):
            raise ApiError(409, "username_conflict", "username already exists")
        user = UserRecord(
            id=new_id(),
            organization_id=principal.organization_id,
            location_id=payload.location_id,
            username=username,
            display_name=payload.display_name,
            password_hash=PasswordService().hash(payload.password.get_secret_value()),
            capabilities=sorted(grants),
            is_active=True,
            is_owner=payload.is_owner,
            version=1,
            session_version=1,
        )
        self.session.add(user)
        try:
            self.session.flush()
        except IntegrityError as exc:
            raise ApiError(409, "account_conflict", "account could not be created") from exc
        append_audit(
            self.session,
            organization_id=principal.organization_id,
            actor_id=actor.id,
            target_id=user.id,
            action="user.created",
            before=None,
            after=user_snapshot(user),
        )
        return user

    def target(
        self, actor: UserRecord, principal: Principal, user_id: str, expected_version: int
    ) -> UserRecord:
        user = self.session.scalar(
            select(UserRecord)
            .where(
                UserRecord.id == user_id,
                UserRecord.organization_id == principal.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise ApiError(404, "user_not_found", "user not found")
        self.check_location(principal, user.location_id)
        self.check_grants(principal, concrete_capabilities(user.capabilities))
        if user.is_owner and not actor.is_owner:
            raise denied()
        if user.version != expected_version:
            raise ApiError(409, "stale_user_version", "user version has changed")
        return user

    def patch_user(
        self, principal: Principal, user_id: str, payload: PatchUserRequest
    ) -> UserRecord:
        actor, principal = self.lock_actor(principal)
        require(principal, "users.write")
        changes = payload.model_fields_set
        if changes & {"role", "capabilities", "location_id", "is_owner"}:
            require(principal, "users.grants.write")
        user = self.target(actor, principal, user_id, payload.expected_version)
        before = user_snapshot(user)
        if "is_owner" in changes and payload.is_owner != user.is_owner and not actor.is_owner:
            raise denied()
        location = payload.location_id if "location_id" in changes else user.location_id
        grants = (
            payload.resolved_grants()
            if changes & {"role", "capabilities"}
            else frozenset(user.capabilities)
        )
        owner = payload.is_owner if "is_owner" in changes else user.is_owner
        active = payload.is_active if "is_active" in changes else user.is_active
        self.check_location(principal, location)
        self.check_grants(principal, concrete_capabilities(grants))
        if owner and (location is not None or grants != CAPABILITIES):
            raise ApiError(
                422, "invalid_owner", "owners require organization scope and all capabilities"
            )
        if user.is_owner and user.is_active and not (owner and active):
            other_owner = self.session.scalar(
                select(UserRecord.id)
                .where(
                    UserRecord.organization_id == principal.organization_id,
                    UserRecord.id != user.id,
                    UserRecord.is_owner.is_(True),
                    UserRecord.is_active.is_(True),
                )
                .limit(1)
            )
            if other_owner is None:
                raise ApiError(409, "last_owner", "the last active owner must remain")
        # No mutation before every authority/invariant/version check has passed.
        if payload.display_name is not None:
            user.display_name = payload.display_name
        user.location_id = location
        user.capabilities = sorted(grants)
        assert owner is not None and active is not None  # schema rejects explicit nulls
        user.is_owner, user.is_active = owner, active
        if any(
            before[field] != user_snapshot(user)[field]
            for field in (
                "location_id",
                "capabilities",
                "is_owner",
                "is_active",
            )
        ):
            user.session_version += 1
        user.version += 1
        self.session.flush()
        append_audit(
            self.session,
            organization_id=principal.organization_id,
            actor_id=actor.id,
            target_id=user.id,
            action="user.updated",
            before=before,
            after=user_snapshot(user),
        )
        return user

    def revoke_sessions(
        self,
        principal: Principal,
        user_id: str,
        expected_version: int,
        *,
        new_password: str | None = None,
    ) -> UserRecord:
        actor, principal = self.lock_actor(principal)
        capability = (
            "users.credentials.reset" if new_password is not None else "users.sessions.revoke"
        )
        require(principal, capability)
        user = self.target(actor, principal, user_id, expected_version)
        return self._revoke(actor, user, new_password=new_password)

    def _revoke(
        self,
        actor: UserRecord,
        user: UserRecord,
        *,
        new_password: str | None = None,
        action: str | None = None,
    ) -> UserRecord:
        before = user_snapshot(user)
        if new_password is not None:
            user.password_hash = PasswordService().hash(new_password)
        user.session_version += 1
        user.version += 1
        self.session.flush()
        append_audit(
            self.session,
            organization_id=user.organization_id,
            actor_id=actor.id,
            target_id=user.id,
            action=action
            or ("user.password_reset" if new_password is not None else "user.sessions_revoked"),
            before=before,
            after=user_snapshot(user),
        )
        return user

    def logout_all(self, principal: Principal) -> None:
        actor, _ = self.lock_actor(principal)
        self._revoke(actor, actor)

    def change_password(
        self, principal: Principal, current_password: str, new_password: str
    ) -> None:
        actor, _ = self.lock_actor(principal)
        if not PasswordService().verify(actor.password_hash, current_password):
            raise ApiError(401, "invalid_credentials", "invalid credentials")
        self._revoke(actor, actor, new_password=new_password, action="user.password_changed")

    def create_location(self, principal: Principal, name: str) -> LocationRecord:
        actor, principal = self.lock_actor(principal)
        require(principal, "locations.create")
        if principal.location_id is not None:
            raise denied()
        location = LocationRecord(id=new_id(), organization_id=principal.organization_id, name=name)
        self.session.add(location)
        self.session.flush()
        append_audit(
            self.session,
            organization_id=principal.organization_id,
            actor_id=actor.id,
            target_id=None,
            action="location.created",
            before=None,
            after={"location_id": location.id},
            target_type="location",
        )
        return location
