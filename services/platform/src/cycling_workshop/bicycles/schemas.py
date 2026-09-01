from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BicycleCreateRequest(BaseModel):
    bicycle_id: str | None = None
    customer_id: str = Field(min_length=1, max_length=36)
    location_id: str = Field(min_length=1, max_length=36)
    brand: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    bicycle_type: str | None = Field(default=None, max_length=60)
    wheel_size: str | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("bicycle_id")
    @classmethod
    def validate_bicycle_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = uuid.UUID(value)
        if parsed.version != 7:
            raise ValueError("bicycle_id must be UUIDv7")
        return str(parsed)


class BicycleResponse(BaseModel):
    bicycle_id: str
    customer_id: str
    organization_id: str
    location_id: str
    brand: str
    model: str | None
    bicycle_type: str | None
    wheel_size: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    version: int
