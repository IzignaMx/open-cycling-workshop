from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

_UNSET = object()


def _now() -> datetime:
    return datetime.now(UTC)


def _required(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} must not be blank")
    return value.strip()


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


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
            brand=" ".join(_required(brand, "brand").split()),
            model=_optional_text(model),
            bicycle_type=_optional_text(bicycle_type),
            wheel_size=_optional_text(wheel_size),
            notes=_optional_text(notes),
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
        next_brand = (
            self.brand if brand is _UNSET else " ".join(_required(str(brand), "brand").split())
        )
        next_model = (
            self.model
            if model is _UNSET
            else _optional_text(model if isinstance(model, str) else None)
        )
        next_type = (
            self.bicycle_type
            if bicycle_type is _UNSET
            else _optional_text(bicycle_type if isinstance(bicycle_type, str) else None)
        )
        next_wheel = (
            self.wheel_size
            if wheel_size is _UNSET
            else _optional_text(wheel_size if isinstance(wheel_size, str) else None)
        )
        next_notes = (
            self.notes
            if notes is _UNSET
            else _optional_text(notes if isinstance(notes, str) else None)
        )
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
