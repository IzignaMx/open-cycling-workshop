"""Prepared, unexecuted small DTO tests; no runtime or capacity evidence."""

import json

import pytest
from cycling_workshop.quotes.reads import QuoteReadError
from cycling_workshop.quotes.responses import (
    CommandResponse,
    OrderTransitionEffects,
    Receipt,
    encode_command_response,
)
from cycling_workshop.quotes.storage import MAX_SAFE_INTEGER
from cycling_workshop.service_orders.domain import OrderState
from pydantic import ValidationError


def uid(number):
    return f"00000000-0000-7000-8000-{number:012x}"


def document(*, decision=False, transition=False, delivery="applied"):
    """Handcrafted wire fields only: no domain, repository or database fixture."""
    return {
        "delivery": delivery,
        "receipt": {
            "operation_id": uid(2),
            "kind": "decision" if decision else "create",
            "ordinal": 2 if decision else 1,
            "quote_id": uid(1),
            "quote_version": 1,
            "decision_id": uid(2) if decision else None,
            "decision_sequence": 1 if decision else 0,
            "recorded_at": "2026-10-16T12:00:00.000000Z",
            "recorded_by_actor_id": "actor-a",
            "totals": {
                "subtotal_minor": 1,
                "discount_minor": 0,
                "tax_minor": 0,
                "total_minor": 1,
            },
            "effects": {
                "kind": "order_transition" if transition else "quote_only",
                "quote_outbox_id": uid(3),
                "order_event_id": "order-event-a" if transition else None,
                "resulting_order_version": 3 if transition else None,
                "change_cursor": 4 if transition else None,
                "order_outbox_id": "order-outbox-a" if transition else None,
            },
        },
        "current": {
            "organization_id": "org-a",
            "location_id": "location-a",
            "order_id": "order-a",
            "lineage_id": uid(1),
            "head_quote_id": uid(1),
            "head_version": 1,
            "decision_sequence": 1 if decision else 0,
        },
        "current_decision": {
            "decision_id": uid(2),
            "quote_id": uid(1),
            "sequence": 1,
            "outcome": "APPROVE",
        }
        if decision
        else None,
        "order": {
            "organization_id": "org-a",
            "location_id": "location-a",
            "order_id": "order-a",
            "state": "AUTHORIZED" if transition else "DIAGNOSIS",
            "version": 3 if transition else 2,
        },
    }


def test_create_and_applied_decision_round_trip_exact_closed_fields():
    for value in (document(), document(decision=True, transition=True)):
        response = CommandResponse.model_validate(value)
        raw = encode_command_response(response)
        assert json.loads(raw) == value
        assert CommandResponse.model_validate_json(raw) == response
        assert b"proof" not in raw and b"evidence" not in raw
        with pytest.raises(ValidationError):
            response.delivery = "replayed"


def test_replay_preserves_historical_quote_only_decision_with_fresh_context():
    value = document(decision=True, delivery="replayed")
    receipt = value["receipt"].copy()
    value["current"].update(head_quote_id=uid(4), head_version=2)
    value["current_decision"] = None
    value["order"].update(state="CANCELLED", version=9)
    raw = encode_command_response(CommandResponse.model_validate(value))
    assert json.loads(raw)["receipt"] == receipt
    assert json.loads(raw)["current_decision"] is None
    assert json.loads(raw)["order"]["state"] == "CANCELLED"


def test_revision_and_replayed_transition_keep_operation_time_fields():
    revised = document()
    revised["receipt"].update(kind="revise", quote_id=uid(4), quote_version=2, ordinal=3)
    revised["receipt"]["decision_sequence"] = 1
    revised["current"].update(head_quote_id=uid(4), head_version=2, decision_sequence=1)
    assert json.loads(encode_command_response(CommandResponse.model_validate(revised))) == revised
    replayed = document(decision=True, transition=True, delivery="replayed")
    replayed["current"].update(head_quote_id=uid(4), head_version=2)
    replayed["current_decision"] = None
    replayed["order"].update(state="CANCELLED", version=9)
    assert json.loads(encode_command_response(CommandResponse.model_validate(replayed))) == replayed


@pytest.mark.parametrize(
    "value",
    [document(decision=True), document(transition=True)],
)
def test_applied_decision_requires_transition_and_revision_requires_quote_only(value):
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize(
    "field", ["order_event_id", "resulting_order_version", "change_cursor", "order_outbox_id"]
)
def test_effect_tuple_refuses_partial_nulls_and_nonnull_quote_only(field):
    transition = document(decision=True, transition=True)
    quote_only = document(decision=True, delivery="replayed")
    quote_only["receipt"]["effects"][field] = transition["receipt"]["effects"][field]
    transition["receipt"]["effects"][field] = None
    for value in (transition, quote_only):
        with pytest.raises(ValidationError):
            CommandResponse.model_validate(value)


@pytest.mark.parametrize(
    "quote_version,decision_sequence,ordinal",
    [(1, 1, 3), (MAX_SAFE_INTEGER, 1, MAX_SAFE_INTEGER)],
)
def test_receipt_ordinal_is_the_safe_sum_of_revision_and_decision_sequence(
    quote_version, decision_sequence, ordinal
):
    value = document(decision=True, transition=True)["receipt"]
    value.update(
        quote_version=quote_version, decision_sequence=decision_sequence, ordinal=ordinal
    )
    with pytest.raises(ValidationError):
        Receipt.model_validate(value)


def test_order_transition_requires_two_distinct_outbox_delivery_identities():
    value = document(decision=True, transition=True)["receipt"]["effects"]
    value["order_outbox_id"] = value["quote_outbox_id"]
    with pytest.raises(ValidationError):
        OrderTransitionEffects.model_validate(value)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("receipt",),
        ("receipt", "totals"),
        ("receipt", "effects"),
        ("current",),
        ("current_decision",),
        ("order",),
    ],
)
def test_all_objects_refuse_extra_fields_and_require_every_listed_field(path):
    value = document(decision=True, transition=True)
    target = value
    for key in path:
        target = target[key]
    target["proof"] = "private"
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)
    del target["proof"]
    for field in tuple(target):
        saved = target.pop(field)
        with pytest.raises(ValidationError):
            CommandResponse.model_validate(value)
        target[field] = saved


@pytest.mark.parametrize(
    "path",
    [
        ("receipt", "ordinal"),
        ("receipt", "quote_version"),
        ("receipt", "decision_sequence"),
        ("receipt", "totals", "total_minor"),
        ("receipt", "effects", "resulting_order_version"),
        ("receipt", "effects", "change_cursor"),
        ("current", "head_version"),
        ("current", "decision_sequence"),
        ("current_decision", "sequence"),
        ("order", "version"),
    ],
)
@pytest.mark.parametrize("bad", [True, 1.0, "1", -1, MAX_SAFE_INTEGER + 1])
def test_numeric_fields_refuse_coercion_and_unsafe_values(path, bad):
    value = document(decision=True, transition=True)
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize(
    "path",
    [
        ("receipt", "ordinal"),
        ("receipt", "quote_version"),
        ("receipt", "effects", "resulting_order_version"),
        ("receipt", "effects", "change_cursor"),
        ("current", "head_version"),
        ("current_decision", "sequence"),
        ("order", "version"),
    ],
)
def test_positive_versions_refuse_zero(path):
    value = document(decision=True, transition=True)
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = 0
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize(
    "path",
    [
        ("delivery",),
        ("receipt", "kind"),
        ("receipt", "effects", "kind"),
        ("current_decision", "outcome"),
        ("order", "state"),
    ],
)
def test_literal_discriminators_and_states_are_closed(path):
    value = document(decision=True, transition=True)
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = "unknown"
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize("bad", ["bad id", "x\x00", "\ud800", "x" * 37])
@pytest.mark.parametrize(
    "path",
    [
        ("order", "order_id"),
        ("receipt", "recorded_by_actor_id"),
        ("receipt", "effects", "order_event_id"),
        ("receipt", "effects", "order_outbox_id"),
    ],
)
def test_legacy_identifiers_keep_composite_canonical_validation(path, bad):
    value = document(decision=True, transition=True)
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = bad
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize(
    "bad", ["legacy-id", uid(0xABC).upper(), "00000000-0000-4000-8000-000000000003"]
)
def test_quote_outbox_requires_canonical_uuidv7(bad):
    value = document()
    value["receipt"]["effects"]["quote_outbox_id"] = bad
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


@pytest.mark.parametrize("bad", ["2026-10-16T12:00:00Z", "2026-02-30T12:00:00.000000Z"])
def test_recording_requires_canonical_calendar_valid_microsecond_utc(bad):
    value = document()
    value["receipt"]["recorded_at"] = bad
    with pytest.raises(ValidationError):
        CommandResponse.model_validate(value)


def test_scope_and_current_decision_must_match_current_head():
    for path, bad in (
        (("order", "order_id"), "other-order"),
        (("current_decision", "quote_id"), uid(99)),
        (("current_decision", "sequence"), 2),
        (("receipt", "decision_id"), uid(99)),
        (("receipt", "decision_sequence"), 0),
    ):
        value = document(decision=True, transition=True)
        value[path[0]][path[1]] = bad
        with pytest.raises(ValidationError):
            CommandResponse.model_validate(value)


def test_withdrawal_remains_visible_and_safe_integer_extreme_is_exact():
    value = document(decision=True, delivery="replayed")
    value["current_decision"]["outcome"] = "WITHDRAW"
    value["receipt"]["totals"].update(subtotal_minor=MAX_SAFE_INTEGER, total_minor=MAX_SAFE_INTEGER)
    assert json.loads(encode_command_response(CommandResponse.model_validate(value))) == value


def test_order_state_schema_matches_existing_nine_state_domain_enum():
    schema = CommandResponse.model_json_schema()
    assert set(schema["$defs"]["OrderNow"]["properties"]["state"]["enum"]) == {
        state.value for state in OrderState
    }
    for name, definition in schema["$defs"].items():
        if "properties" in definition:
            assert definition["additionalProperties"] is False, name
            assert set(definition["required"]) == set(definition["properties"]), name


def test_encoder_revalidates_nested_bypasses_and_checks_actual_utf8_bytes(monkeypatch):
    import cycling_workshop.quotes.responses as responses

    value = document()
    value["receipt"]["recorded_by_actor_id"] = "técnico"
    response = CommandResponse.model_validate(value)
    raw = encode_command_response(response)
    monkeypatch.setattr(responses, "RESPONSE_LIMIT", len(raw))
    assert encode_command_response(response) == raw
    monkeypatch.setattr(responses, "RESPONSE_LIMIT", len(raw) - 1)
    with pytest.raises(QuoteReadError, match="quote_response_too_large"):
        encode_command_response(response)
    broken = response.model_copy(
        update={
            "receipt": response.receipt.model_copy(
                update={"totals": response.receipt.totals.model_copy(update={"total_minor": True})}
            )
        }
    )
    with pytest.raises(QuoteReadError, match="invalid_quote_projection"):
        encode_command_response(broken)
    with pytest.raises(QuoteReadError, match="invalid_quote_projection"):
        encode_command_response(value)
