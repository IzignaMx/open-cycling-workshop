from __future__ import annotations

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from cycling_workshop.inventory.domain import MovementKind


class InventoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def reject_nul_text(cls, value: object) -> object:
        # PostgreSQL text cannot store NUL; reject at the public boundary so
        # malformed text cannot become an internal database error.
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("text must not contain NUL")
        return value


class ProductCreateRequest(InventoryRequest):
    product_id: str | None = None
    location_id: str = Field(min_length=1, max_length=36)
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(default="pieza", min_length=1, max_length=30)

    @field_validator("sku", mode="before")
    @classmethod
    def normalize_sku(cls, value: object) -> object:
        # Validate the storage limit after Unicode case expansion, not before.
        return "-".join(value.split()).upper() if isinstance(value, str) else value

    @field_validator("product_id")
    @classmethod
    def product_uuid7(cls, value: str | None) -> str | None:
        if value is not None:
            return _uuid7(value)
        return None


def _uuid7(value: str) -> str:
    parsed = uuid.UUID(value)
    if parsed.version != 7:
        raise ValueError("identifier must be UUIDv7")
    return str(parsed)


class MovementCreateRequest(InventoryRequest):
    movement_id: str
    product_id: str = Field(min_length=1, max_length=36)
    kind: MovementKind
    quantity: StrictInt = Field(ge=-2147483647, le=2147483647)
    order_id: str | None = Field(default=None, min_length=1, max_length=36)
    reference_movement_id: str | None = Field(default=None, min_length=1, max_length=36)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("movement_id")
    @classmethod
    def movement_uuid7(cls, value: str) -> str:
        return _uuid7(value)

    @model_validator(mode="after")
    def valid_command_shape(self) -> Self:
        if self.quantity == 0 or (self.kind != MovementKind.ADJUST and self.quantity < 0):
            raise ValueError("quantity must be nonzero; only ADJUST accepts negative quantities")
        if self.kind != MovementKind.ADJUST and self.order_id is None:
            raise ValueError("reservation commands require an order")
        if self.kind in (MovementKind.RELEASE, MovementKind.CONSUME):
            if self.reference_movement_id is None:
                raise ValueError("finalization requires a reference reservation")
        elif self.reference_movement_id is not None:
            raise ValueError("only finalization commands accept a reference reservation")
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    organization_id: str
    location_id: str
    sku: str
    name: str
    unit: str
    created_at: datetime
    updated_at: datetime
    version: int


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movement_id: str
    product_id: str
    organization_id: str
    location_id: str
    kind: MovementKind
    quantity: int
    order_id: str | None
    reference_movement_id: str | None
    actor_id: str
    note: str | None
    occurred_at: datetime


class StockResponse(BaseModel):
    product_id: str
    organization_id: str
    location_id: str
    available_quantity: int


class InventoryMovementReadResponse(BaseModel):
    """Privacy allowlist for reads; the historical POST response is unchanged."""

    model_config = ConfigDict(extra="forbid")

    movement_id: str
    product_id: str
    organization_id: str
    location_id: str
    kind: MovementKind
    quantity: int
    occurred_at: str

    @field_validator("movement_id", "product_id", "organization_id", "location_id")
    @classmethod
    def valid_identifier(cls, value: str) -> str:
        from cycling_workshop.inventory.cursor import valid_read_id

        if not valid_read_id(value):
            raise ValueError("invalid inventory identifier")
        return value

    @field_validator("occurred_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        from cycling_workshop.inventory.cursor import parse_timestamp

        parse_timestamp(value)
        return value


class InventoryMovementPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[InventoryMovementReadResponse]
    next_cursor: str | None
