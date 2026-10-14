"""Transaction-owned compatibility admission, never a grant or credential."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.tenancy.models import OrganizationRecord


def canonical_incarnation(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def validate_compatibility(organization: OrganizationRecord | None) -> OrganizationRecord:
    if (
        organization is None
        or type(organization.minimum_write_protocol) is not int
        or organization.minimum_write_protocol not in (0, 1)
        or not canonical_incarnation(organization.dataset_incarnation)
    ):
        raise ApiError(503, "compatibility_state_invalid", "compatibility state unavailable")
    return organization


def lock_compatibility(session: Session, organization_id: str) -> OrganizationRecord:
    organization = session.scalar(
        select(OrganizationRecord)
        .where(OrganizationRecord.id == organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return validate_compatibility(organization)


def validate_incarnation(organization: OrganizationRecord, principal: Principal) -> None:
    validate_compatibility(organization)
    claim = principal.dataset_incarnation
    if (claim is None and organization.minimum_write_protocol == 1) or (
        claim is not None
        and (not canonical_incarnation(claim) or claim != organization.dataset_incarnation)
    ):
        raise ApiError(401, "invalid_session", "invalid session")


def admit_protocol(organization: OrganizationRecord, protocol: int, enabled: bool) -> None:
    validate_compatibility(organization)
    if (
        type(protocol) is not int
        or protocol not in (0, 1)
        or protocol < organization.minimum_write_protocol
        or (protocol == 1 and not enabled)
    ):
        raise ApiError(409, "client_upgrade_required", "client upgrade required")


@dataclass(frozen=True, slots=True)
class WriteAdmission:
    protocol: int
    enabled: bool
    tokens: SessionTokenService | None
    fixture_only: bool = False

    @classmethod
    def for_fixtures(cls, protocol: int = 0, *, enabled: bool = False) -> WriteAdmission:
        """Explicit test-only internal caller; never constructed from HTTP flags."""
        return cls(protocol, enabled, None, fixture_only=True)

    def check_expiry(self, principal: Principal) -> None:
        if self.fixture_only and principal.expires_at is None:
            return
        now = self.tokens.now() if self.tokens is not None else datetime.now(UTC)
        if principal.expires_at is None or principal.expires_at <= now:
            raise ApiError(401, "invalid_session", "invalid session")


def write_admission(
    request: Request,
    _protocol: Annotated[str | None, Header(alias="X-OCWP-Write-Protocol")] = None,
) -> WriteAdmission:
    values = request.headers.getlist("x-ocwp-write-protocol")
    if len(values) > 1 or (values and values[0] not in ("0", "1")):
        raise ApiError(409, "client_upgrade_required", "client upgrade required")
    return WriteAdmission(
        protocol=int(values[0]) if values else 0,
        enabled=request.app.state.settings.cutover_enabled,
        tokens=request.app.state.session_tokens,
    )


def commit_admitted(session: Session, principal: Principal, admission: WriteAdmission) -> None:
    session.flush()
    admission.check_expiry(principal)
    session.commit()
