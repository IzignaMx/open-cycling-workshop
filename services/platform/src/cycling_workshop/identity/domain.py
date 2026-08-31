from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    organization_id: str
    location_id: str | None
    capabilities: frozenset[str]
    session_version: int = 1


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
