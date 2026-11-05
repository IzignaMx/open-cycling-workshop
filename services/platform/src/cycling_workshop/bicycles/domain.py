from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from cycling_workshop.shared.text import validate_storage_text

_UNSET = object()


def _now() -> datetime:
    return datetime.now(UTC)


def _required(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} must not be blank")
    return validate_storage_text(value).strip()


def _text(value: object, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string" + ("" if required else " or null"))
    normalized = " ".join(validate_storage_text(value).split())
    if required and not normalized:
        raise ValueError(f"{field} must not be blank")
    if len(normalized) > limit:
        raise ValueError(f"{field} exceeds maximum length")
    return normalized or None


def _brand(value: object) -> str:
    normalized = _text(value, "brand", 120, required=True)
    assert normalized is not None
    return normalized


@dataclass(frozen=True, slots=True)
class Bicycle:
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

    @classmethod
    def create(
        cls,
        *,
        bicycle_id: str,
        customer_id: str,
        organization_id: str,
        location_id: str,
        brand: str,
        model: str | None = None,
        bicycle_type: str | None = None,
        wheel_size: str | None = None,
        notes: str | None = None,
        now: datetime | None = None,
    ) -> Bicycle:
        timestamp = now or _now()
        return cls(
            bicycle_id=_required(bicycle_id, "bicycle_id"),
            customer_id=_required(customer_id, "customer_id"),
            organization_id=_required(organization_id, "organization_id"),
            location_id=_required(location_id, "location_id"),
            brand=_brand(brand),
            model=_text(model, "model", 120),
            bicycle_type=_text(bicycle_type, "bicycle_type", 60),
            wheel_size=_text(wheel_size, "wheel_size", 30),
            notes=_text(notes, "notes", 2000),
            created_at=timestamp,
            updated_at=timestamp,
            version=1,
        )

    def update(
        self,
        *,
        brand: str | object = _UNSET,
        model: str | object | None = _UNSET,
        bicycle_type: str | object | None = _UNSET,
        wheel_size: str | object | None = _UNSET,
        notes: str | object | None = _UNSET,
        now: datetime | None = None,
    ) -> Bicycle:
        next_brand = self.brand if brand is _UNSET else _brand(brand)
        next_model = self.model if model is _UNSET else _text(model, "model", 120)
        next_type = (
            self.bicycle_type if bicycle_type is _UNSET else _text(bicycle_type, "bicycle_type", 60)
        )
        next_wheel = (
            self.wheel_size if wheel_size is _UNSET else _text(wheel_size, "wheel_size", 30)
        )
        next_notes = self.notes if notes is _UNSET else _text(notes, "notes", 2000)
        return replace(
            self,
            brand=next_brand,
            model=next_model,
            bicycle_type=next_type,
            wheel_size=next_wheel,
            notes=next_notes,
            updated_at=now or _now(),
            version=self.version + 1,
        )
