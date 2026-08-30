from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.dependencies import require_capability
from cycling_workshop.identity.domain import Principal, authorize
from cycling_workshop.sync.domain import MutationEnvelope, SyncConflict
from cycling_workshop.sync.schemas import (
    ChangeItemResponse,
    ChangePageResponse,
    MutationResultResponse,
    PushMutationsRequest,
    PushMutationsResponse,
)
from cycling_workshop.sync.service import SyncService

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.post("/mutations", response_model=PushMutationsResponse)
def push_mutations(
    payload: PushMutationsRequest,
    principal: Annotated[Principal, Depends(require_capability("sync.push"))],
    session: Annotated[Session, Depends(get_session)],
) -> PushMutationsResponse:
    service = SyncService(session)
    results: list[MutationResultResponse] = []
    try:
        for item in payload.mutations:
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
                        )
                    )
                results.append(
                    MutationResultResponse(
                        mutation_id=result.mutation_id,
                        status=result.status,
                        entity_id=result.entity_id,
                        entity_version=result.entity_version,
                    )
                )
            except SyncConflict as exc:
                results.append(
                    MutationResultResponse(
                        mutation_id=item.mutation_id,
                        status="conflict",
                        entity_id=item.entity_id,
                        entity_version=None,
                        error_code="sync_conflict",
                        error_message=str(exc),
                    )
                )
        session.commit()
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
    try:
        authorize(
            principal,
            capability="sync.pull",
            organization_id=principal.organization_id,
            location_id=location_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    page = SyncService(session).pull_changes(
        organization_id=principal.organization_id,
        location_id=location_id,
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
