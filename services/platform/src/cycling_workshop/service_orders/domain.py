from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from cycling_workshop.shared.ids import new_id


class OrderState(StrEnum):
    INTAKE = "INTAKE"
    DIAGNOSIS = "DIAGNOSIS"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS"
    READY = "READY"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class UnknownActionError(ValueError):
    """The requested action does not exist in the state machine vocabulary."""


class InvalidStateTransitionError(ValueError):
    """Permanent domain rejection: the action is illegal from the current state."""


# action -> (allowed source states, target state); CANCELLED is terminal and
# only reachable from pre-READY states.
_TRANSITIONS: dict[str, tuple[frozenset[OrderState], OrderState]] = {
    "start_diagnosis": (frozenset({OrderState.INTAKE}), OrderState.DIAGNOSIS),
    "authorize": (frozenset({OrderState.DIAGNOSIS}), OrderState.AUTHORIZED),
    "reject": (frozenset({OrderState.DIAGNOSIS}), OrderState.REJECTED),
    "start_work": (frozenset({OrderState.AUTHORIZED}), OrderState.IN_PROGRESS),
    "request_parts": (frozenset({OrderState.IN_PROGRESS}), OrderState.WAITING_FOR_PARTS),
    "resume_work": (frozenset({OrderState.WAITING_FOR_PARTS}), OrderState.IN_PROGRESS),
    "mark_ready": (frozenset({OrderState.IN_PROGRESS}), OrderState.READY),
    "close": (frozenset({OrderState.READY}), OrderState.CLOSED),
}

_PRE_READY_CANCEL_SOURCES = frozenset(
    state
    for state in OrderState
    if state not in {OrderState.READY, OrderState.CLOSED, OrderState.CANCELLED}
)


def _now() -> datetime:
    return datetime.now(UTC)


def _required(value: str, field: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{field} must not be blank")
    return " ".join(value.split())


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


@dataclass(frozen=True, slots=True)
class ServiceOrderEvent:
    """Append-only timeline entry; one per executed transition."""

    event_id: str
    order_id: str
    organization_id: str
    from_state: str
    to_state: str
    action: str
    actor_id: str
    note: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class TransitionResult:
    order: ServiceOrder
    event: ServiceOrderEvent


@dataclass(frozen=True, slots=True)
class ServiceOrder:
    order_id: str
    customer_id: str
    bicycle_id: str | None
    organization_id: str
    location_id: str
    state: str
    reported_problem: str
    intake_condition: str | None
    accessories: str | None
    priority: str
    diagnosis: str | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def create(
        cls,
        *,
        order_id: str,
        customer_id: str,
        organization_id: str,
        location_id: str,
        reported_problem: str,
        bicycle_id: str | None = None,
        intake_condition: str | None = None,
        accessories: str | None = None,
        priority: str = "normal",
        now: datetime | None = None,
    ) -> ServiceOrder:
        timestamp = now or _now()
        return cls(
            order_id=_required(order_id, "order_id"),
            customer_id=_required(customer_id, "customer_id"),
            bicycle_id=_optional_text(bicycle_id),
            organization_id=_required(organization_id, "organization_id"),
            location_id=_required(location_id, "location_id"),
            state=OrderState.INTAKE.value,
            reported_problem=_required(reported_problem, "reported_problem"),
            intake_condition=_optional_text(intake_condition),
            accessories=_optional_text(accessories),
            priority=_required(priority, "priority"),
            diagnosis=None,
            created_at=timestamp,
            updated_at=timestamp,
            version=1,
        )

    def transition(
        self,
        action: str,
        *,
        actor_id: str,
        note: str | None = None,
        event_id: str | None = None,
        now: datetime | None = None,
    ) -> TransitionResult:
        timestamp = now or _now()
        current = OrderState(self.state)

        if action == "cancel":
            if current not in _PRE_READY_CANCEL_SOURCES:
                raise InvalidStateTransitionError(
                    f"invalid_state_transition: cancel_from_{current.value}".lower()
                )
            target = OrderState.CANCELLED
        elif action in _TRANSITIONS:
            sources, target = _TRANSITIONS[action]
            if current not in sources:
                raise InvalidStateTransitionError(
                    f"invalid_state_transition: {action}_from_{current.value}".lower()
                )
        else:
            raise UnknownActionError(f"unknown transition action: {action}")

        updated = replace(
            self,
            state=target.value,
            updated_at=timestamp,
            version=self.version + 1,
        )
        event = ServiceOrderEvent(
            event_id=event_id or new_id(),
            order_id=self.order_id,
            organization_id=self.organization_id,
            from_state=current.value,
            to_state=target.value,
            action=action,
            actor_id=_required(actor_id, "actor_id"),
            note=_optional_text(note),
            occurred_at=timestamp,
        )
        return TransitionResult(order=updated, event=event)

    def set_diagnosis(self, diagnosis: str, *, now: datetime | None = None) -> ServiceOrder:
        if self.state != OrderState.DIAGNOSIS.value:
            raise InvalidStateTransitionError(
                f"invalid_state_transition: set_diagnosis_from_{self.state}".lower()
            )
        return replace(
            self,
            diagnosis=_required(diagnosis, "diagnosis"),
            updated_at=now or _now(),
            version=self.version + 1,
        )
