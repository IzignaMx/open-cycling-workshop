from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    organization_id: str
    location_id: str | None
    capabilities: frozenset[str]
    session_version: int = 1
    dataset_incarnation: str | None = None
    expires_at: datetime | None = field(default=None, compare=False, repr=False)


def authorize(
    principal: Principal,
    *,
    capability: str,
    organization_id: str,
    location_id: str | None = None,
) -> None:
    if principal.organization_id != organization_id:
        raise PermissionError("organization scope denied")
    if (
        principal.location_id is not None
        and location_id is not None
        and principal.location_id != location_id
    ):
        raise PermissionError("location scope denied")
    if capability not in principal.capabilities and "*" not in principal.capabilities:
        raise PermissionError(f"missing capability: {capability}")
