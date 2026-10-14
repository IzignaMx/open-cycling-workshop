"""Finite metadata retention and atomic admission under the organization barrier."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.sync.baseline_models import BaselineFamily

USER_FAMILIES = 8
ORGANIZATION_FAMILIES = 128
ORGANIZATION_ACTIVE = 100
LOCATION_ACTIVE = 2


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def state(family: BaselineFamily) -> dict[str, Any]:
    result = json.loads(family.state_json)
    if not isinstance(result, dict):
        raise ApiError(409, "dataset_changed", "pagination metadata is invalid")
    return result


def save_state(family: BaselineFamily, value: dict[str, Any]) -> None:
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > 16384:
        raise ApiError(409, "dataset_changed", "pagination metadata is invalid")
    family.state_json = encoded


def expire_and_admit(
    session: Session, organization_id: str, user_id: str, location_id: str, now: datetime
) -> None:
    # The organization barrier is already held. No business data is deleted.
    expired = list(
        session.scalars(
            select(BaselineFamily.reference_hash)
            .where(
                BaselineFamily.organization_id == organization_id,
                BaselineFamily.retention_until <= now,
            )
            .order_by(BaselineFamily.reference_hash)
            .limit(ORGANIZATION_FAMILIES)
        )
    )
    if expired:
        session.execute(delete(BaselineFamily).where(BaselineFamily.reference_hash.in_(expired)))
    rows = list(
        session.execute(
            select(
                BaselineFamily.user_id,
                BaselineFamily.location_id,
                BaselineFamily.phase,
                BaselineFamily.retention_until,
            )
            .where(BaselineFamily.organization_id == organization_id)
            .limit(ORGANIZATION_FAMILIES + 1)
        )
    )
    own = [r for r in rows if r.user_id == user_id]
    active = [r for r in rows if r.phase in {"scan", "finalize", "baseline_delta"}]
    location = [r for r in active if r.user_id == user_id and r.location_id == location_id]
    if len(location) >= LOCATION_ACTIVE:
        _capacity(location, now, 409, "baseline_in_progress")
    if len(own) >= USER_FAMILIES:
        _capacity(own, now, 429, "baseline_capacity")
    if len(active) >= ORGANIZATION_ACTIVE:
        _capacity(active, now, 429, "baseline_capacity")
    if len(rows) >= ORGANIZATION_FAMILIES:
        _capacity(rows, now, 429, "baseline_capacity")


def _capacity(rows: list[Any], now: datetime, status: int, code: str) -> None:
    expiry = min(aware(row.retention_until) for row in rows)
    raise ApiError(
        status,
        code,
        "pagination capacity is occupied",
        {
            "retry_after_seconds": max(1, math.ceil((expiry - now).total_seconds())),
            "expires_at": expiry.isoformat().replace("+00:00", "Z"),
        },
    )
