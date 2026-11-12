"""Server-side reference cases mirrored by the existing-transition note UI tests."""

import pytest
from cycling_workshop.service_orders.domain import ServiceOrder
from cycling_workshop.service_orders.schemas import OrderTransitionRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("\u0085 Se necesita\n  cadena\u001c ", "Se necesita cadena"),
        ("\u0085\u001c", None),
        ("\ufeffNota\ufeff", "\ufeffNota\ufeff"),
        ("🙂" * 2000, "🙂" * 2000),
        (None, None),
    ],
)
def test_transition_note_contract_retains_existing_server_normalization(note, expected) -> None:
    request = OrderTransitionRequest(action="start_diagnosis", note=note)
    order = ServiceOrder.create(
        order_id="order",
        customer_id="customer",
        organization_id="org",
        location_id="loc",
        reported_problem="Frenos",
    )
    result = order.transition(request.action, actor_id="actor", note=request.note)
    assert result.event.note == expected


@pytest.mark.parametrize("note", ["x" * 2001, "\x00", "\ud800"])
def test_transition_http_note_rejects_unsupported_new_input(note) -> None:
    with pytest.raises(ValidationError):
        OrderTransitionRequest(action="start_diagnosis", note=note)
