from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MutationRequest(BaseModel):
    mutation_id: str = Field(min_length=36, max_length=36)
    entity_type: Literal["customer"]
    entity_id: str = Field(min_length=36, max_length=36)
    operation: Literal["create", "update"]
    organization_id: str = Field(min_length=1, max_length=36)
    location_id: str = Field(min_length=1, max_length=36)
    base_version: int | None = Field(default=None, ge=0)
    occurred_at: datetime
    payload: dict[str, object]


class PushMutationsRequest(BaseModel):
    mutations: list[MutationRequest] = Field(min_length=1, max_length=100)


class MutationResultResponse(BaseModel):
    mutation_id: str
    status: Literal["applied", "conflict"]
    entity_id: str
    entity_version: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class PushMutationsResponse(BaseModel):
    results: list[MutationResultResponse]


class ChangeItemResponse(BaseModel):
    cursor: int
    entity_type: str
    entity_id: str
    operation: str
    organization_id: str
    location_id: str
    entity_version: int
    occurred_at: datetime
    payload: dict[str, object]


class ChangePageResponse(BaseModel):
    items: list[ChangeItemResponse]
    next_cursor: int
    has_more: bool
