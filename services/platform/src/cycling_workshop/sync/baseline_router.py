"""Bounded server protocol, independent of production client activation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.sync.baseline_schemas import (
    ActivationRequest,
    ActivationResponse,
    DeltaPage,
    FinalizeResponse,
    PageRequest,
    ScanPage,
    StartRequest,
    StartResponse,
)
from cycling_workshop.sync.baseline_service import BaselineService

router = APIRouter(prefix="/api/v1/sync", tags=["baselines"])


def service(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> BaselineService:
    try:
        return BaselineService(
            session,
            request.app.state.session_tokens,
            request.app.state.baseline_codec,
            authorization,
        )
    except SQLAlchemyError as exc:
        session.rollback()
        raise ApiError(
            503,
            "temporary_unavailable",
            "pagination temporarily unavailable",
            {"retry_after_seconds": 2},
        ) from exc


def invoke(baseline: BaselineService, action: str, value: StartRequest | str) -> Response:
    try:
        if action == "start":
            assert isinstance(value, StartRequest)
            result = baseline.start(value)
        else:
            assert isinstance(value, str)
            if action == "page":
                result = baseline.page(value)
            elif action == "finalize":
                result = baseline.finalize(value)
            elif action == "delta":
                result = baseline.delta(value)
            else:
                result = baseline.activate(value)
        return Response(
            result, media_type="application/json", headers={"Cache-Control": "no-store"}
        )
    except SQLAlchemyError as exc:
        baseline.session.rollback()
        raise ApiError(
            503,
            "temporary_unavailable",
            "pagination temporarily unavailable",
            {"retry_after_seconds": 2},
        ) from exc


@router.post("/baselines/start", response_model=StartResponse)
def start(body: StartRequest, baseline: Annotated[BaselineService, Depends(service)]) -> Response:
    return invoke(baseline, "start", body)


@router.post("/baselines/page", response_model=ScanPage)
def page(body: PageRequest, baseline: Annotated[BaselineService, Depends(service)]) -> Response:
    return invoke(baseline, "page", body.continuation)


@router.post("/baselines/finalize", response_model=FinalizeResponse)
def finalize(body: PageRequest, baseline: Annotated[BaselineService, Depends(service)]) -> Response:
    return invoke(baseline, "finalize", body.continuation)


@router.post("/deltas/page", response_model=DeltaPage)
def delta(body: PageRequest, baseline: Annotated[BaselineService, Depends(service)]) -> Response:
    return invoke(baseline, "delta", body.continuation)


@router.post("/baselines/validate-activation", response_model=ActivationResponse)
def activate(
    body: ActivationRequest, baseline: Annotated[BaselineService, Depends(service)]
) -> Response:
    return invoke(baseline, "activate", body.checkpoint)
