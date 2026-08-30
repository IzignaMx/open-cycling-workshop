from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_validator


class CustomerCreateRequest(BaseModel):
    customer_id: str | None = None
    location_id: str = Field(min_length=1, max_length=36)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = uuid.UUID(value)
        if parsed.version != 7:
            raise ValueError("customer_id must be UUIDv7")
        return str(parsed)


class CustomerResponse(BaseModel):
    customer_id: str
    organization_id: str
    location_id: str
    display_name: str
    email: str | None
    phone: str | None
    created_at: datetime
    updated_at: datetime
    version: int
