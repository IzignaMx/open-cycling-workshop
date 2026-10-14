from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

EntityType = Literal["customer", "bicycle", "service_order"]
MutationOperation = Literal["create", "update"]


class SyncConflict(RuntimeError):
    """A mutation cannot be merged automatically without risking data loss."""

    def __init__(self, message: str, *, error_code: str = "sync_conflict") -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class SyncApplicationContext:
    """Trusted caller identity supplied by the server, never a wire payload."""

    actor_id: str
    write_protocol: int = 0
    canonical_digest: str | None = None
    admitted_session_id: int | None = None


@dataclass(frozen=True, slots=True)
class MutationEnvelope:
    mutation_id: str
    entity_type: EntityType
    entity_id: str
    operation: MutationOperation
    organization_id: str
    location_id: str
    base_version: int | None
    occurred_at: datetime
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class MutationResult:
    mutation_id: str
    status: Literal["applied"]
    entity_id: str
    entity_version: int


@dataclass(frozen=True, slots=True)
class ChangeItem:
    cursor: int
    entity_type: str
    entity_id: str
    operation: str
    organization_id: str
    location_id: str
    entity_version: int
    occurred_at: datetime
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChangePage:
    items: list[ChangeItem]
    next_cursor: int
    has_more: bool
