"""Closed bounded-baseline DTOs, independent of REST write-size restrictions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.context_schemas import AccessContextResponse

RESPONSE_LIMIT = 1048576
CONTROL_LIMIT = 16384
PAGE_LIMIT = 100


def _protocol(value: object) -> object:
    if type(value) is not int or value != 1:
        raise ValueError("Unsupported protocol")
    return value


def _uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("Expected canonical UUID")
    return value


def _ascii(value: str) -> str:
    if not value.isascii():
        raise ValueError("Expected ASCII continuation")
    return value


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        # Reject date-only, numeric epoch and ISO variants outside RFC3339.
        import re

        if (
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
            )
            is None
        ):
            raise ValueError("Expected RFC3339 timestamp")
        parsed = datetime.fromisoformat(value)
    else:
        raise ValueError("Expected RFC3339 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Expected timezone-aware timestamp")
    return parsed.astimezone(UTC)


Protocol = Annotated[Literal[1], BeforeValidator(_protocol)]
Identifier = Annotated[StrictStr, Field(min_length=1, max_length=36)]
CanonicalUUID = Annotated[Identifier, AfterValidator(_uuid)]
Version = Annotated[StrictInt, Field(ge=1, le=2**53 - 1)]
Epoch = Annotated[StrictStr, Field(min_length=1, max_length=256)]
Continuation = Annotated[StrictStr, Field(min_length=1, max_length=512), AfterValidator(_ascii)]
Timestamp = Annotated[datetime, BeforeValidator(_timestamp)]
OrderState = Literal[
    "INTAKE",
    "DIAGNOSIS",
    "AUTHORIZED",
    "REJECTED",
    "IN_PROGRESS",
    "WAITING_FOR_PARTS",
    "READY",
    "CLOSED",
    "CANCELLED",
]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Projection(ClosedModel):
    organization_id: Identifier
    location_id: Identifier
    created_at: Timestamp
    updated_at: Timestamp
    version: Version


class CustomerPayload(Projection):
    customer_id: Identifier
    display_name: StrictStr
    email: StrictStr | None
    phone: StrictStr | None


class BicyclePayload(Projection):
    bicycle_id: Identifier
    customer_id: Identifier
    brand: StrictStr
    model: StrictStr | None
    bicycle_type: StrictStr | None
    wheel_size: StrictStr | None
    notes: StrictStr | None


class ServiceOrderPayload(Projection):
    order_id: Identifier
    customer_id: Identifier
    bicycle_id: Identifier | None
    state: OrderState
    reported_problem: StrictStr
    intake_condition: StrictStr | None
    accessories: StrictStr | None
    priority: StrictStr
    diagnosis: StrictStr | None


class Record(ClosedModel):
    payload: CustomerPayload | BicyclePayload | ServiceOrderPayload
    entity_type: str
    entity_id: Identifier
    entity_version: Version

    @model_validator(mode="after")
    def consistent_envelope(self) -> Self:
        payload = self.payload
        entity_type = self.entity_type
        key = "order_id" if entity_type == "service_order" else f"{entity_type}_id"
        if self.entity_id != getattr(payload, key) or self.entity_version != payload.version:
            raise ValueError("Projection envelope mismatch")
        return self


class CustomerRecord(Record):
    entity_type: Literal["customer"]
    payload: CustomerPayload


class BicycleRecord(Record):
    entity_type: Literal["bicycle"]
    payload: BicyclePayload


class ServiceOrderRecord(Record):
    entity_type: Literal["service_order"]
    payload: ServiceOrderPayload


SnapshotRecord = Annotated[
    CustomerRecord | BicycleRecord | ServiceOrderRecord, Field(discriminator="entity_type")
]
_RECORD: TypeAdapter[CustomerRecord | BicycleRecord | ServiceOrderRecord] = TypeAdapter(
    SnapshotRecord
)


def validate_record(value: object, organization_id: str, location_id: str) -> dict[str, object]:
    try:
        record = _RECORD.validate_python(value)
        if (
            record.payload.organization_id != organization_id
            or record.payload.location_id != location_id
        ):
            raise ValueError("Projection scope mismatch")
        return record.model_dump(mode="json")
    except (ValidationError, ValueError) as exc:
        raise ApiError(409, "dataset_changed", "Invalid stored projection") from exc


class StartRequest(ClosedModel):
    protocol: Protocol
    selected_location_id: Identifier
    authorization_epoch: Epoch
    request_id: CanonicalUUID


class StartResponse(ClosedModel):
    protocol: Protocol
    baseline_id: CanonicalUUID
    context: AccessContextResponse
    continuation: Continuation
    expires_at: Timestamp


class PageRequest(ClosedModel):
    protocol: Protocol
    continuation: Continuation


class ScanPage(ClosedModel):
    protocol: Protocol
    baseline_id: CanonicalUUID
    authorization_epoch: Epoch
    page_id: Identifier
    predecessor: Continuation
    records: Annotated[list[SnapshotRecord], Field(max_length=PAGE_LIMIT)]
    phase: Literal["scan", "scan_complete"]
    continuation: Continuation


class FinalizeResponse(ClosedModel):
    protocol: Protocol
    baseline_id: CanonicalUUID
    authorization_epoch: Epoch
    predecessor: Continuation
    continuation: Continuation


class Completion(ClosedModel):
    baseline_id: CanonicalUUID | None
    authorization_epoch: Epoch
    checkpoint: Continuation


class DeltaPage(ClosedModel):
    protocol: Protocol
    baseline_id: CanonicalUUID | None
    authorization_epoch: Epoch
    page_id: Identifier
    predecessor: Continuation
    records: Annotated[list[SnapshotRecord], Field(max_length=PAGE_LIMIT)]
    phase: Literal["catching_up", "complete"]
    continuation: Continuation
    completion: Completion | None

    @model_validator(mode="after")
    def consistent_completion(self) -> Self:
        if self.phase == "catching_up":
            if self.completion is not None:
                raise ValueError("Unexpected completion")
        elif (
            self.completion is None
            or self.completion.checkpoint != self.continuation
            or self.completion.baseline_id != self.baseline_id
            or self.completion.authorization_epoch != self.authorization_epoch
        ):
            raise ValueError("Completion mismatch")
        return self


class ActivationRequest(ClosedModel):
    protocol: Protocol
    checkpoint: Continuation


class ActivationResponse(ClosedModel):
    protocol: Protocol
    baseline_id: CanonicalUUID
    authorization_epoch: Epoch
    checkpoint: Continuation
    context: AccessContextResponse
