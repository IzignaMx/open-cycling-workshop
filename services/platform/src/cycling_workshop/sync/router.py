from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.context import build_context
from cycling_workshop.identity.cutover import WriteAdmission, commit_admitted, write_admission
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.identity.security import ValidatedSession
from cycling_workshop.sync.domain import MutationEnvelope, SyncApplicationContext, SyncConflict
from cycling_workshop.sync.models import MutationReceiptRecord
from cycling_workshop.sync.schemas import (
    ChangeItemResponse,
    ChangePageResponse,
    MutationResultResponse,
    PushMutationsRequest,
    PushMutationsResponse,
)
from cycling_workshop.sync.service import SyncService
from cycling_workshop.sync.writes import lock_writer

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/mutations", response_model=PushMutationsResponse)
def push_mutations(
    request: Request,
    admission: Annotated[WriteAdmission, Depends(write_admission)],
    payload: PushMutationsRequest,
    principal: Annotated[Principal, Depends(require_capability("sync.push"))],
    session: Annotated[Session, Depends(get_session)],
    _epoch: Annotated[str | None, Header(alias="X-OCWP-Authorization-Epoch")] = None,
) -> PushMutationsResponse:
    service = SyncService(session)
    results: list[MutationResultResponse] = []
    try:
        principal = lock_writer(session, principal, admission)
        authorize(principal, capability="sync.push", organization_id=principal.organization_id)
        if admission.protocol == 1:
            epochs = request.headers.getlist("x-ocwp-authorization-epoch")
            locations = {item.location_id for item in payload.mutations}
            if len(epochs) != 1 or len(locations) != 1:
                raise ApiError(
                    409, "authorization_context_changed", "authorization context changed"
                )
            assert admission.tokens is not None and principal.expires_at is not None
            context = build_context(
                session,
                admission.tokens,
                ValidatedSession(principal, principal.expires_at),
                principal,
                next(iter(locations)),
                cutover_enabled=admission.enabled,
            )
            if epochs[0] != context.authorization_epoch:
                raise ApiError(
                    409, "authorization_context_changed", "authorization context changed"
                )
        proofs = getattr(request.state, "sync_command_proofs", ())
        for item_index, item in enumerate(payload.mutations):
            authorize(
                principal,
                capability="sync.push",
                organization_id=item.organization_id,
                location_id=item.location_id,
            )
            if item.entity_type == "customer":
                authorize(
                    principal,
                    capability="customers.write",
                    organization_id=item.organization_id,
                    location_id=item.location_id,
                )
            elif item.entity_type == "bicycle":
                authorize(
                    principal,
                    capability="bicycles.write",
                    organization_id=item.organization_id,
                    location_id=item.location_id,
                )
            elif item.entity_type == "service_order":
                authorize(
                    principal,
                    capability="orders.write",
                    organization_id=item.organization_id,
                    location_id=item.location_id,
                )
            try:
                with session.begin_nested():
                    result = service.apply(
                        MutationEnvelope(
                            mutation_id=item.mutation_id,
                            entity_type=item.entity_type,
                            entity_id=item.entity_id,
                            operation=item.operation,
                            organization_id=item.organization_id,
                            location_id=item.location_id,
                            base_version=item.base_version,
                            occurred_at=item.occurred_at,
                            payload=item.payload,
                        ),
                        context=SyncApplicationContext(
                            actor_id=principal.user_id,
                            write_protocol=admission.protocol,
                            canonical_digest=proofs[item_index]
                            if item_index < len(proofs)
                            else None,
                            admitted_session_id=id(session),
                        ),
                    )
                results.append(
                    MutationResultResponse(
                        mutation_id=result.mutation_id,
                        status=result.status,
                        entity_id=result.entity_id,
                        entity_version=result.entity_version,
                    )
                )
            except IntegrityError:
                # A different organization may concurrently claim the global ID.
                # The item savepoint has rolled back its domain/history effects;
                # only classify a now-visible receipt collision, never arbitrary
                # constraint failures, and disclose none of the other receipt.
                exists = session.scalar(
                    select(MutationReceiptRecord.mutation_id).where(
                        MutationReceiptRecord.mutation_id == item.mutation_id
                    )
                )
                if exists is None:
                    raise
                results.append(
                    MutationResultResponse(
                        mutation_id=item.mutation_id,
                        status="conflict",
                        entity_id=item.entity_id,
                        entity_version=None,
                        error_code="sync_conflict",
                        error_message="mutation identifier is unavailable",
                    )
                )
            except SyncConflict as exc:
                results.append(
                    MutationResultResponse(
                        mutation_id=item.mutation_id,
                        status="conflict",
                        entity_id=item.entity_id,
                        entity_version=None,
                        error_code=exc.error_code,
                        error_message=str(exc),
                    )
                )
        commit_admitted(session, principal, admission)
    except PermissionError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return PushMutationsResponse(results=results)


@router.get("/changes", response_model=ChangePageResponse)
def pull_changes(
    principal: Annotated[Principal, Depends(require_capability("sync.pull"))],
    session: Annotated[Session, Depends(get_session)],
    cursor: Annotated[int, Query(ge=0)] = 0,
    location_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ChangePageResponse:
    # An omitted query parameter must never widen a location-bound session.
    effective_location = principal.location_id if location_id is None else location_id
    try:
        authorize(
            principal,
            capability="sync.pull",
            organization_id=principal.organization_id,
            location_id=effective_location,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    page = SyncService(session).pull_changes(
        organization_id=principal.organization_id,
        location_id=effective_location,
        capabilities=principal.capabilities,
        after_cursor=cursor,
        limit=limit,
    )
    return ChangePageResponse(
        items=[
            ChangeItemResponse(
                cursor=item.cursor,
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                operation=item.operation,
                organization_id=item.organization_id,
                location_id=item.location_id,
                entity_version=item.entity_version,
                occurred_at=item.occurred_at,
                payload=item.payload,
            )
            for item in page.items
        ],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )
