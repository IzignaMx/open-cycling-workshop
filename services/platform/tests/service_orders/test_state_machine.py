from datetime import UTC, datetime

import pytest
from cycling_workshop.service_orders.domain import (
    InvalidStateTransitionError,
    ServiceOrder,
    UnknownActionError,
)

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def _order(**overrides) -> ServiceOrder:
    payload: dict[str, object] = {
        "order_id": "order-1",
        "customer_id": "customer-1",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "reported_problem": "  Cadena  saltando ",
        "intake_condition": " Rayado del cuadro ",
        "accessories": "  Canasto, luz ",
        "priority": "normal",
        "now": NOW,
    }
    payload.update(overrides)
    return ServiceOrder.create(**payload)  # type: ignore[arg-type]


def test_order_create_starts_at_intake_and_normalizes_text() -> None:
    order = _order()

    assert order.state == "INTAKE"
    assert order.reported_problem == "Cadena saltando"
    assert order.intake_condition == "Rayado del cuadro"
    assert order.accessories == "Canasto, luz"
    assert order.version == 1
    assert order.diagnosis is None


def test_order_requires_reported_problem_and_scope() -> None:
    with pytest.raises(ValueError, match="reported_problem"):
        _order(reported_problem="   ")
    with pytest.raises(ValueError, match="customer_id"):
        _order(customer_id="")


# --- legal transition matrix -------------------------------------------------

LEGAL_STEPS: list[tuple[list[str], str]] = [
    (["start_diagnosis"], "DIAGNOSIS"),
    (["start_diagnosis", "authorize"], "AUTHORIZED"),
    (["start_diagnosis", "reject"], "REJECTED"),
    (["start_diagnosis", "authorize", "start_work"], "IN_PROGRESS"),
    (["start_diagnosis", "authorize", "start_work", "request_parts"], "WAITING_FOR_PARTS"),
    (
        ["start_diagnosis", "authorize", "start_work", "request_parts", "resume_work"],
        "IN_PROGRESS",
    ),
    (["start_diagnosis", "authorize", "start_work", "mark_ready"], "READY"),
    (["start_diagnosis", "authorize", "start_work", "mark_ready", "close"], "CLOSED"),
    (["cancel"], "CANCELLED"),
    (["start_diagnosis", "authorize", "cancel"], "CANCELLED"),
    (["start_diagnosis", "authorize", "start_work", "cancel"], "CANCELLED"),
    (["start_diagnosis", "authorize", "start_work", "request_parts", "cancel"], "CANCELLED"),
    (["start_diagnosis", "reject", "cancel"], "CANCELLED"),
]


@pytest.mark.parametrize(("actions", "expected_state"), LEGAL_STEPS)
def test_legal_transitions(actions: list[str], expected_state: str) -> None:
    order = _order()
    for action in actions:
        order = order.transition(action, actor_id="user-1", now=NOW).order

    assert order.state == expected_state


# --- illegal transition matrix ------------------------------------------------

ILLEGAL_STEPS: list[tuple[list[str], str]] = [
    (["mark_ready"], "mark_ready from INTAKE"),
    (["close"], "close from INTAKE"),
    (["start_work"], "start_work skips diagnosis authorization"),
    (["authorize"], "authorize from INTAKE"),
    (["start_diagnosis", "mark_ready"], "mark_ready from DIAGNOSIS"),
    (["start_diagnosis", "authorize", "authorize"], "double authorize"),
    (["start_diagnosis", "authorize", "start_work", "start_work"], "double start_work"),
    (["start_diagnosis", "authorize", "start_work", "mark_ready", "cancel"], "cancel from READY"),
    (
        ["start_diagnosis", "authorize", "start_work", "mark_ready", "close", "close"],
        "close from CLOSED",
    ),
    (["cancel", "cancel"], "cancel from CANCELLED"),
    (["start_diagnosis", "reject", "start_work"], "start_work from REJECTED"),
    (
        ["start_diagnosis", "authorize", "start_work", "request_parts", "mark_ready"],
        "ready from WAITING",
    ),
]


@pytest.mark.parametrize(
    ("actions", "label"),
    ILLEGAL_STEPS,
    ids=[label for _, label in ILLEGAL_STEPS],
)
def test_illegal_transitions_are_permanent_errors(actions: list[str], label: str) -> None:
    order = _order()
    *prefix, failing = actions
    for action in prefix:
        order = order.transition(action, actor_id="user-1", now=NOW).order
    from_state = order.state

    with pytest.raises(
        InvalidStateTransitionError,
        match=f"{failing}_from_{from_state}".lower(),
    ):
        order.transition(failing, actor_id="user-1", now=NOW)


def test_unknown_action_is_rejected() -> None:
    with pytest.raises(UnknownActionError):
        _order().transition("explode", actor_id="user-1", now=NOW)


# --- events -------------------------------------------------------------------


def test_every_transition_emits_one_append_only_event() -> None:
    order = _order()
    result = order.transition(
        "start_diagnosis", actor_id="user-1", note=" revisión inicial ", now=NOW
    )

    assert order.state == "INTAKE"  # immutable original
    assert result.order.state == "DIAGNOSIS"
    assert result.order.version == order.version + 1
    event = result.event
    assert event.order_id == order.order_id
    assert event.from_state == "INTAKE"
    assert event.to_state == "DIAGNOSIS"
    assert event.action == "start_diagnosis"
    assert event.actor_id == "user-1"
    assert event.note == "revisión inicial"
    assert event.occurred_at == NOW
    assert event.event_id  # durable identity for append-only storage


def test_waiting_parts_roundtrip_keeps_history() -> None:
    order = _order()
    seen: list[str] = []
    for action in ["start_diagnosis", "authorize", "start_work", "request_parts", "resume_work"]:
        order = order.transition(action, actor_id="user-1", now=NOW).order
        seen.append(action)

    assert seen.count("request_parts") == 1
    assert order.state == "IN_PROGRESS"
    assert order.version == 1 + len(seen)


def test_set_diagnosis_requires_text_and_bumps_version() -> None:
    order = _order().transition("start_diagnosis", actor_id="user-1", now=NOW).order

    diagnosed = order.set_diagnosis("  Cadena gastada, casete desgastado ", now=NOW)

    assert diagnosed.diagnosis == "Cadena gastada, casete desgastado"
    assert diagnosed.version == order.version + 1
    assert diagnosed.state == "DIAGNOSIS"
    with pytest.raises(ValueError, match="diagnosis"):
        order.set_diagnosis("   ", now=NOW)
