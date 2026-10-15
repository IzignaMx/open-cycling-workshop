"""One bounded transaction owns inventory read authorization and materialization.

This deliberately does not use the legacy separate-auth-session dependency or
writer admission. Organization then actor locks serialize with administration;
all settings are transaction-local and all successful reads end with rollback.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.cutover import lock_compatibility, validate_incarnation
from cycling_workshop.identity.dependencies import _extract_bearer, effective_principal
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.repository import SqlAlchemyUserRepository
from cycling_workshop.identity.roles import concrete_capabilities
from cycling_workshop.identity.security import SessionTokenService

TRANSACTION_SECONDS = 8


@dataclass(frozen=True, slots=True)
class InventoryRead:
    session: Session
    principal: Principal


def unavailable() -> ApiError:
    return ApiError(503, "inventory_read_unavailable", "inventory read unavailable")


def set_read_budgets(session: Session) -> None:
    connection = session.connection()
    if connection.dialect.name == "sqlite":
        # Functional surrogate only; never claim timeout or lock-wait proof.
        return
    if (
        connection.dialect.name != "postgresql"
        or not connection.dialect.server_version_info
        or connection.dialect.server_version_info[0] != 18
    ):
        raise unavailable()
    # Total budget is installed first. No organization/actor/business SQL is
    # issued before all three settings succeed. Missing settings fail closed.
    session.execute(text("SET LOCAL transaction_timeout = '8s'"))
    session.execute(text("SET LOCAL lock_timeout = '2s'"))
    session.execute(text("SET LOCAL statement_timeout = '5s'"))


def _cleanup(session: Session, *, invalidated: bool) -> None:
    if invalidated:
        session.invalidate()
        return
    try:
        session.rollback()
    except SQLAlchemyError:
        # A transaction-timeout FATAL may terminate the socket. Never return
        # an aborted or driver-invalid connection to the reusable pool.
        session.invalidate()
        raise unavailable() from None


@contextmanager
def inventory_read(request: Request, authorization: str | None) -> Iterator[InventoryRead]:
    service: SessionTokenService = request.app.state.session_tokens
    try:
        validated = service.decode_session(_extract_bearer(authorization))
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise HTTPException(status_code=401, detail="invalid session") from None
    factory = request.app.state.session_factory
    if factory is None:
        raise unavailable()
    started = time.monotonic()
    with factory() as session:
        invalidated = False
        try:
            set_read_budgets(session)
            original = validated.principal
            try:
                organization = lock_compatibility(session, original.organization_id)
                validate_incarnation(organization, original)
            except ApiError:
                # The old GET auth boundary refused incompatible/quarantined
                # or stale-incarnation sessions as 401. Preserve that contract.
                raise HTTPException(status_code=401, detail="invalid session") from None
            account = SqlAlchemyUserRepository(session).get(
                user_id=original.user_id,
                organization_id=original.organization_id,
                for_update=True,
            )
            try:
                if validated.expires_at <= service.now():
                    raise ValueError("expired")
                principal = effective_principal(original, account)
            except ValueError:
                raise HTTPException(status_code=401, detail="invalid session") from None
            if "inventory.read" not in concrete_capabilities(principal.capabilities):
                raise HTTPException(status_code=403, detail="capability denied")
            yield InventoryRead(session, principal)
            # Run after the response's complete projection/materialization, not
            # just before its first SELECT, and keep the barrier until rollback.
            if validated.expires_at <= service.now():
                raise HTTPException(status_code=401, detail="invalid session")
            if time.monotonic() - started >= TRANSACTION_SECONDS:
                raise unavailable()
        except SQLAlchemyError as exc:
            invalidated = isinstance(exc, DBAPIError) and exc.connection_invalidated
            raise unavailable() from None
        finally:
            _cleanup(session, invalidated=invalidated)


def inventory_read_dependency(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> Iterator[InventoryRead]:
    # Use Depends(scope="function"): authorization keeps its legacy precedence
    # over parameter validation, and cleanup finishes before any response bytes.
    with inventory_read(request, authorization) as read:
        yield read
