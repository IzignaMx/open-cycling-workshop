"""Explicit local first-owner establishment; never called by migration/bootstrap."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.db.session import build_engine
from cycling_workshop.identity.admin_schemas import CreateUserRequest
from cycling_workshop.identity.audit import append_audit, user_snapshot
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.repository import normalize_username
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord


def create_first_owner(
    settings: Settings,
    *,
    organization_id: str,
    username: str,
    display_name: str,
    password_file: Path,
) -> dict[str, object]:
    # Bound secret reads, including one normal trailing newline; never accept
    # plaintext passwords in argv or include them in errors, output or audit.
    with password_file.open(encoding="utf-8") as stream:
        contents = stream.read(1027)
    if len(contents) > 1026:
        raise ApiError(422, "invalid_password_file", "password file is too large")
    password = contents.rstrip("\r\n")
    payload = CreateUserRequest(
        username=username,
        display_name=display_name,
        location_id=None,
        password=SecretStr(password),
        role="Owner",
        is_owner=True,
    )
    engine = build_engine(settings)
    correlation = request_id_var.set(f"cli-{new_id()}")
    try:
        with Session(engine) as session:
            organization = session.scalar(
                select(OrganizationRecord)
                .where(OrganizationRecord.id == organization_id)
                .with_for_update()
            )
            if organization is None:
                raise ApiError(404, "organization_not_found", "organization not found")
            if (
                session.scalar(
                    select(UserRecord.id)
                    .where(
                        UserRecord.organization_id == organization_id,
                        UserRecord.is_owner.is_(True),
                    )
                    .limit(1)
                )
                is not None
            ):
                raise ApiError(409, "owner_already_established", "an owner is already established")
            normalized = normalize_username(payload.username)
            if (
                session.scalar(
                    select(UserRecord.id).where(
                        UserRecord.organization_id == organization_id,
                        UserRecord.username == normalized,
                    )
                )
                is not None
            ):
                raise ApiError(409, "username_conflict", "username already exists")
            owner = UserRecord(
                id=new_id(),
                organization_id=organization_id,
                location_id=None,
                username=normalized,
                display_name=payload.display_name,
                password_hash=PasswordService().hash(payload.password.get_secret_value()),
                capabilities=sorted(CAPABILITIES),
                is_active=True,
                is_owner=True,
                version=1,
                session_version=1,
            )
            session.add(owner)
            session.flush()
            append_audit(
                session,
                organization_id=organization_id,
                actor_id=None,
                target_id=owner.id,
                action="user.first_owner_created",
                before=None,
                after=user_snapshot(owner),
            )
            session.commit()
            return {
                "created": True,
                "organization_id": organization_id,
                "location_id": None,
                "user_id": owner.id,
                "username": owner.username,
            }
    finally:
        request_id_var.reset(correlation)
        engine.dispose()
