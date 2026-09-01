from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TransitionAction = Literal[
    "start_diagnosis",
    "authorize",
    "reject",
    "start_work",
    "request_parts",
    "resume_work",
    "mark_ready",
    "close",
    "cancel",
]


class ServiceOrderCreateRequest(BaseModel):
    order_id: str | None = None
    customer_id: str = Field(min_length=1, max_length=36)
    bicycle_id: str | None = Field(default=None, max_length=36)
    location_id: str = Field(min_length=1, max_length=36)
    reported_problem: str = Field(min_length=1, max_length=4000)
    intake_condition: str | None = Field(default=None, max_length=4000)
    accessories: str | None = Field(default=None, max_length=2000)
    priority: str = Field(default="normal", max_length=30)

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = uuid.UUID(value)
        if parsed.version != 7:
            raise ValueError("order_id must be UUIDv7")
        return str(parsed)


class ServiceOrderResponse(BaseModel):
    order_id: str
    customer_id: str
    bicycle_id: str | None
    organization_id: str
    location_id: str
    state: str
    reported_problem: str
    intake_condition: str | None
    accessories: str | None
    priority: str
    diagnosis: str | None
    created_at: datetime
    updated_at: datetime
    version: int


class OrderTransitionRequest(BaseModel):
    action: TransitionAction
    note: str | None = Field(default=None, max_length=2000)


class ServiceOrderEventResponse(BaseModel):
    event_id: str
    order_id: str
    from_state: str
    to_state: str
    action: str
    actor_id: str
    note: str | None
    occurred_at: datetime
