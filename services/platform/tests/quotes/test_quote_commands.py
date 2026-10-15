"""Quote-owned immutable semantic proofs, without HTTP/admission metadata."""

from collections import UserString
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone

import pytest
from cycling_workshop.quotes.commands import (
    CreateQuoteCommand,
    RecordQuoteDecisionCommand,
    ReviseQuoteCommand,
    command_from_proof,
    operation_proof,
)
from cycling_workshop.quotes.decisions import QuoteDecisionLedger
from cycling_workshop.quotes.history import QuoteHistory
from test_quote_storage import NOW, command, quote, uid


def create(**changes):
    values = dict(
        operation_id=uid(200),
        quote_id=uid(1),
        organization_id="org",
        location_id="loc",
        order_id="order",
        actor_id="staff",
        expected_order_version=2,
        currency="MXN",
        lines=quote().lines,
    )
    values.update(changes)
    return CreateQuoteCommand(**values)


def revise(**changes):
    values = dict(
        operation_id=uid(201),
        quote_id=uid(2),
        organization_id="org",
        location_id="loc",
        order_id="order",
        actor_id="staff",
        expected_order_version=2,
        lineage_id=uid(1),
        expected_head_id=uid(1),
        expected_head_version=1,
        expected_decision_sequence=0,
        lines=quote().lines,
    )
    values.update(changes)
    return ReviseQuoteCommand(**values)


def record(**changes):
    book = QuoteDecisionLedger(QuoteHistory((quote(),)))
    return RecordQuoteDecisionCommand(command(book, **changes), expected_order_version=2)


@pytest.mark.parametrize("operation", [create(), revise(), record()])
def test_proof_roundtrip_is_exact_and_scoped(operation):
    request = operation
    proof = operation_proof(request)
    assert command_from_proof(proof) == request
    assert request.organization_id == "org"
    assert request.location_id == "loc"
    assert request.order_id == "order"
    assert request.actor_id == "staff"
    assert request.lineage_id == uid(1)
    assert "recorded_at" not in proof
    assert "session_version" not in proof
    assert "dataset_incarnation" not in proof
    assert "authorization_epoch" not in proof


def test_create_has_absent_head_and_root_revision_identity():
    request = create()
    assert request.expected_head_id is None
    assert request.expected_head_version == request.expected_decision_sequence == 0
    assert request.lineage_id == request.quote_id
    assert command_from_proof(operation_proof(request)).lines == request.lines


def test_command_freezes_input_line_sequence_and_returns_detached_proof():
    lines = list(quote().lines)
    request = create(lines=lines)
    lines.clear()
    assert len(request.lines) == 4
    proof = operation_proof(request)
    proof["lines"].clear()
    assert len(request.lines) == 4
    with pytest.raises(FrozenInstanceError):
        request.actor_id = "changed"


def test_selection_order_and_equivalent_utc_instants_are_semantically_equal():
    first = record(outcome="APPROVE", approved_line_ids=(uid(10), uid(11)))
    evidence = replace(
        first.command.evidence, decided_at=NOW.astimezone(timezone(timedelta(hours=-6)))
    )
    second = record(outcome="APPROVE", approved_line_ids=(uid(11), uid(10)), evidence=evidence)
    assert operation_proof(first) == operation_proof(second)
    assert first.operation_id == first.command.decision_id


@pytest.mark.parametrize(
    "changed",
    [
        lambda x: replace(x, expected_order_version=3),
        lambda x: replace(x, command=replace(x.command, recorded_by_actor_id="another-actor")),
        lambda x: replace(x, command=replace(x.command, reason="Different reason")),
        lambda x: replace(x, command=replace(x.command, expected_decision_sequence=1)),
        lambda x: replace(
            x, command=replace(x.command, evidence=replace(x.command.evidence, note="changed"))
        ),
    ],
)
def test_semantic_mutations_change_proof(changed):
    original = record()
    assert operation_proof(changed(original)) != operation_proof(original)


def test_revision_presentation_order_is_semantic():
    request = revise()
    assert operation_proof(request) != operation_proof(
        replace(request, lines=tuple(reversed(request.lines)))
    )


@pytest.mark.parametrize("value", [True, 2.0, "2", 0, 9_007_199_254_740_992])
def test_order_version_requires_exact_bounded_positive_integer(value):
    with pytest.raises(ValueError):
        create(expected_order_version=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": "not-a-uuid"},
        {"quote_id": "q"},
        {"actor_id": UserString("staff")},
        {"currency": "mxn"},
        {"lines": object()},
        {"organization_id": "x" * 37},
    ],
)
def test_invalid_creation_proof_refused(changes):
    with pytest.raises(ValueError):
        create(**changes)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(unknown="field"),
        lambda p: p.update(schema_version=True),
        lambda p: p.update(kind="other"),
        lambda p: p.update(expected_order_version=True),
        lambda p: p["lines"][0].update(unknown="field"),
        lambda p: p.update(actor_id="staff\x00"),
    ],
)
def test_damaged_stored_proof_fails_closed(mutate):
    proof = deepcopy(operation_proof(create()))
    mutate(proof)
    with pytest.raises(ValueError):
        command_from_proof(proof)


def test_wrong_new_revision_identity_and_precondition_shapes_refused():
    for changes in (
        {"quote_id": uid(1)},
        {"expected_head_version": 0},
        {"expected_decision_sequence": True},
    ):
        with pytest.raises(ValueError):
            revise(**changes)


@pytest.mark.parametrize("factory", [create, revise])
def test_cyclic_or_deep_wrong_shape_lines_fail_with_controlled_value_error(factory):
    cyclic = []
    cyclic.append(cyclic)
    deep = []
    for _ in range(1100):
        deep = [deep]
    for lines in (cyclic, deep):
        with pytest.raises(ValueError):
            factory(lines=lines)
