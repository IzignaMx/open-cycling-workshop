from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime

_UNSET = object()


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("display_name must not be blank")
    return normalized


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise ValueError("email is not valid")
    return normalized


def _normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(value.split())
    return normalized or None


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: str
    organization_id: str
    location_id: str
    display_name: str
    email: str | None
    phone: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        customer_id: str,
        organization_id: str,
        location_id: str,
        display_name: str,
        email: str | None = None,
        phone: str | None = None,
        now: datetime | None = None,
    ) -> Customer:
        timestamp = now or _now()
        return cls(
            customer_id=customer_id,
            organization_id=organization_id,
            location_id=location_id,
            display_name=_normalize_name(display_name),
            email=_normalize_email(email),
            phone=_normalize_phone(phone),
            created_at=timestamp,
            updated_at=timestamp,
            version=1,
        )

    def rename(self, display_name: str, *, now: datetime | None = None) -> Customer:
        return replace(
            self,
            display_name=_normalize_name(display_name),
            updated_at=now or _now(),
            version=self.version + 1,
        )

    def change_contact(
        self,
        *,
        email: str | None,
        phone: str | None,
        now: datetime | None = None,
    ) -> Customer:
        return self.update(email=email, phone=phone, now=now)

    def update(
        self,
        *,
        display_name: str | object = _UNSET,
        email: str | object | None = _UNSET,
        phone: str | object | None = _UNSET,
        now: datetime | None = None,
    ) -> Customer:
        next_name = (
            self.display_name if display_name is _UNSET else _normalize_name(str(display_name))
        )
        next_email = (
            self.email
            if email is _UNSET
            else _normalize_email(email if isinstance(email, str) else None)
        )
        next_phone = (
            self.phone
            if phone is _UNSET
            else _normalize_phone(phone if isinstance(phone, str) else None)
        )
        return replace(
            self,
            display_name=next_name,
            email=next_email,
            phone=next_phone,
            updated_at=now or _now(),
            version=self.version + 1,
        )
