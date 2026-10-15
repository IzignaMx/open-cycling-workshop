from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest
from cycling_workshop.quotes.decisions import (
    DecisionCommand,
    DecisionEvidence,
    EntryRecording,
    QuoteDecisionLedger,
    plan_initial_transition,
)
from cycling_workshop.quotes.domain import LaborLine, PartLine, Quote
from cycling_workshop.quotes.history import QuoteHistory
from cycling_workshop.service_orders.domain import ServiceOrder

NOW = datetime(2026, 10, 15, 10, tzinfo=UTC)


def quote() -> Quote:
    return Quote.for_order(
        organization_id="org",
        location_id="loc",
        order_id="order",
        currency="MXN",
        quote_id="q1",
        now=NOW,
        lines=[LaborLine("labor", "Work", 60, 100), PartLine("part", "Part", "p", 2, 50)],
    )


def ledger() -> QuoteDecisionLedger:
    return QuoteDecisionLedger(QuoteHistory((quote(),)))


def command(book: QuoteDecisionLedger, **changes: object) -> DecisionCommand:
    head = book.history.head
    values: dict[str, object] = {
        "decision_id": "d1",
        "organization_id": "org",
        "location_id": "loc",
        "order_id": "order",
        "lineage_id": "q1",
        "quote_id": head.quote_id,
        "quote_version": head.version,
        "expected_head_id": head.quote_id,
        "expected_head_version": head.version,
        "expected_decision_sequence": book.sequence,
        "recorded_by_actor_id": "staff",
        "mode": "initial",
        "outcome": "APPROVE",
        "approved_line_ids": ("part", "labor"),
        "evidence": DecisionEvidence("customer", "customer", "phone", NOW),
        "supersedes_entry_id": None,
        "reason": None,
    }
    values.update(changes)
    return DecisionCommand(**values)  # type: ignore[arg-type]


def order() -> ServiceOrder:
    return (
        ServiceOrder.create(
            order_id="order",
            customer_id="customer",
            organization_id="org",
            location_id="loc",
            reported_problem="noise",
            now=NOW,
        )
        .transition("start_diagnosis", actor_id="staff", now=NOW)
        .order
    )


def record(book: QuoteDecisionLedger | None = None, **changes: object):
    book = ledger() if book is None else book
    return book.record(command(book, **changes), recorded_at=NOW)


def revise(book: QuoteDecisionLedger, *, now: datetime = NOW, quote_id: str = "q2"):
    return book.revise(
        lines=book.history.head.lines,
        quote_id=quote_id,
        now=now,
        expected_head_id=book.history.head.quote_id,
        expected_head_version=book.history.head.version,
        expected_decision_sequence=book.sequence,
    )


@pytest.mark.parametrize(
    "outcome, selected, action",
    [
        ("APPROVE", ["part", "labor"], "authorize"),
        ("PARTIAL", ["part"], "authorize"),
        ("REJECT", [], "reject"),
    ],
)
def test_fresh_decision_and_initial_transition(outcome, selected, action):
    before = ledger()
    result = record(before, outcome=outcome, approved_line_ids=selected)
    assert before.entries == ()
    assert result.ledger.sequence == 1
    assert result.entry.command.approved_line_ids == tuple(sorted(selected))
    assert len(result.entry.line_decisions) == 2
    assert result.projection == result.ledger.projection
    assert result.event.evidence_entry_id == result.entry.command.decision_id
    assert not hasattr(result.event, "evidence")
    assert not hasattr(result.event, "note")
    plan = plan_initial_transition(result.ledger, order(), result)
    assert plan.action == action
    assert plan.expected_order_version == 2
    assert plan.expected_head_id == "q1"
    assert plan.expected_decision_sequence == 1
    assert order().transition(plan.action, actor_id="staff", now=NOW).order.state in {
        "AUTHORIZED",
        "REJECTED",
    }


def test_exact_replay_preserves_receipt_and_returns_current_ledger_projection():
    original = record()
    revised = revise(original.ledger).ledger
    replay = revised.record(original.entry.command, recorded_at=NOW - timedelta(days=20))
    assert replay.replayed is True and replay.event is None
    assert replay.entry == original.entry
    assert replay.ledger == revised
    assert replay.projection.outcome == "NO_CURRENT_DECISION"
    assert replay.entry.recording.recorded_at == NOW
    with pytest.raises(ValueError):
        plan_initial_transition(revised, order(), replay)


def test_replacement_withdrawal_then_customer_change_is_append_only():
    initial = record()
    withdrawal = record(
        initial.ledger,
        decision_id="d2",
        mode="withdraw_record",
        outcome="WITHDRAW",
        approved_line_ids=(),
        evidence=None,
        supersedes_entry_id="d1",
        reason="wrong record",
    )
    assert withdrawal.projection.outcome == "WITHDRAW"
    assert withdrawal.projection.approved_line_ids == ()
    assert withdrawal.entry.line_decisions == ()
    changed = record(
        withdrawal.ledger,
        decision_id="d3",
        mode="customer_change",
        outcome="PARTIAL",
        approved_line_ids=("part",),
        supersedes_entry_id="d2",
        reason="customer revised choice",
    )
    assert changed.ledger.entries[:2] == withdrawal.ledger.entries
    assert changed.ledger.entries[0] == initial.entry
    assert changed.projection.approved_line_ids == ("part",)
    assert len(changed.entry.line_decisions) == 2
    with pytest.raises(ValueError):
        plan_initial_transition(changed.ledger, order(), changed)
    replay = changed.ledger.record(initial.entry.command, recorded_at=NOW)
    assert replay.entry == initial.entry
    assert replay.projection == changed.projection


@pytest.mark.parametrize("later", ["revision", "replacement", "withdrawal"])
def test_retained_initial_result_cannot_plan_after_later_change(later):
    initial = record()
    if later == "revision":
        current = revise(initial.ledger).ledger
    else:
        withdrawing = later == "withdrawal"
        current = record(
            initial.ledger,
            decision_id="d2",
            mode="withdraw_record" if withdrawing else "record_correction",
            outcome="WITHDRAW" if withdrawing else "REJECT",
            approved_line_ids=(),
            evidence=None if withdrawing else initial.entry.command.evidence,
            supersedes_entry_id="d1",
            reason="correction",
        ).ledger
    with pytest.raises(ValueError):
        plan_initial_transition(current, order(), initial)


def test_initial_planner_rejects_foreign_missing_or_mismatched_result():
    initial = record()
    for current in [
        ledger(),
        QuoteDecisionLedger(QuoteHistory((replace(quote(), quote_id="other"),))),
    ]:
        with pytest.raises(ValueError):
            plan_initial_transition(current, order(), initial)
    for wrong in [replace(order(), location_id="elsewhere"), replace(order(), state="AUTHORIZED")]:
        with pytest.raises(ValueError):
            plan_initial_transition(initial.ledger, wrong, initial)
    with pytest.raises(ValueError):
        plan_initial_transition(
            initial.ledger, order(), replace(initial, projection=ledger().projection)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "PARTIAL", "approved_line_ids": ()},
        {"outcome": "PARTIAL", "approved_line_ids": ("part", "labor")},
        {"outcome": "APPROVE", "approved_line_ids": ("part",)},
        {"outcome": "REJECT", "approved_line_ids": ("part",)},
        {"approved_line_ids": ("unknown",)},
        {"approved_line_ids": ("part", "part")},
        {"approved_line_ids": "part"},
        {"quote_id": "other"},
        {"quote_version": 2},
        {"expected_head_id": "other"},
        {"expected_head_version": 2},
        {"expected_decision_sequence": 1},
        {"organization_id": "other"},
        {"location_id": "other"},
        {"order_id": "other"},
        {"lineage_id": "other"},
        {"recorded_by_actor_id": " "},
        {"mode": "unknown"},
        {"outcome": "unknown"},
        {"evidence": None},
        {"reason": "unexpected", "supersedes_entry_id": "d0"},
        {"expected_decision_sequence": True},
        {"quote_version": 1.0},
    ],
)
def test_invalid_decision_has_no_effect(changes):
    before = ledger()
    with pytest.raises(ValueError):
        before.record(command(before, **changes), recorded_at=NOW)
    assert before.entries == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"recorded_by_actor_id": "staff2"},
        {"expected_decision_sequence": 9},
        {"expected_head_id": "other"},
        {"reason": "different"},
        {"evidence": DecisionEvidence("customer", "customer2", "phone", NOW)},
        {"outcome": "PARTIAL", "approved_line_ids": ("part",)},
    ],
)
def test_same_id_changed_semantic_proof_conflicts(changes):
    initial = record()
    with pytest.raises(ValueError):
        initial.ledger.record(replace(initial.entry.command, **changes), recorded_at=NOW)
    assert initial.ledger.sequence == 1


def test_two_decisions_and_revision_cas_do_not_merge():
    before = ledger()
    stale = command(before, decision_id="d2")
    initial = record(before)
    with pytest.raises(ValueError):
        initial.ledger.record(stale, recorded_at=NOW)
    with pytest.raises(ValueError):
        initial.ledger.revise(
            lines=quote().lines,
            quote_id="q2",
            now=NOW,
            expected_head_id="q1",
            expected_head_version=1,
            expected_decision_sequence=0,
        )
    revised = revise(before).ledger
    with pytest.raises(ValueError):
        revised.record(stale, recorded_at=NOW)


def test_revision_chronology_and_deferred_historical_correction():
    book = ledger()
    initial = book.record(command(book), recorded_at=NOW + timedelta(hours=2))
    with pytest.raises(ValueError):
        revise(initial.ledger, now=NOW + timedelta(hours=1))
    # Standalone Task 4 contract is intentionally less restrictive.
    assert quote().revise(lines=quote().lines, now=NOW + timedelta(hours=1)).successor.version == 2
    revised = revise(initial.ledger, now=NOW + timedelta(hours=2))
    assert revised.ledger.sequence == 1 and revised.ledger.entries == initial.ledger.entries
    assert revised.event is None
    for mode, outcome, evidence in [
        ("record_correction", "REJECT", initial.entry.command.evidence),
        ("withdraw_record", "WITHDRAW", None),
    ]:
        late = command(
            revised.ledger,
            decision_id="d2",
            quote_id="q1",
            quote_version=1,
            mode=mode,
            outcome=outcome,
            evidence=evidence,
            approved_line_ids=(),
            supersedes_entry_id="d1",
            reason="late",
        )
        with pytest.raises(ValueError):
            revised.ledger.record(late, recorded_at=NOW + timedelta(hours=3))
    assert QuoteDecisionLedger(revised.ledger.history, revised.ledger.entries) == revised.ledger


@pytest.mark.parametrize("time", [NOW - timedelta(seconds=1), NOW + timedelta(seconds=1)])
def test_decision_time_within_revision_and_recording(time):
    with pytest.raises(ValueError):
        record(evidence=DecisionEvidence("customer", "customer", "phone", time))


def test_reconstruction_rejects_tampered_proof_price_recording_or_sequence():
    initial = record()
    entry = initial.entry
    invalid_entries = [
        replace(entry, command=replace(entry.command, recorded_by_actor_id="other")),
        replace(entry, command=replace(entry.command, expected_decision_sequence=7), sequence=8),
        replace(entry, command=replace(entry.command, expected_head_id="missing")),
        replace(entry, pricing=replace(entry.pricing, total_minor=999)),
        replace(entry, recording=EntryRecording("staff", NOW - timedelta(hours=1))),
        replace(entry, line_decisions=()),
    ]
    for invalid in invalid_entries:
        with pytest.raises(ValueError):
            QuoteDecisionLedger(initial.ledger.history, (invalid,))
    with pytest.raises(ValueError):
        QuoteDecisionLedger(initial.ledger.history, (entry, entry))


def test_immutable_inputs_and_records():
    selected = ["part"]
    before = ledger()
    cmd = command(before, outcome="PARTIAL", approved_line_ids=selected)
    selected.clear()
    result = before.record(cmd, recorded_at=NOW)
    assert result.projection.approved_line_ids == ("part",)
    with pytest.raises(FrozenInstanceError):
        result.entry.sequence = 10
    with pytest.raises(FrozenInstanceError):
        result.entry.command.evidence.channel = "email"
    assert isinstance(result.ledger.entries, tuple)


@pytest.mark.parametrize(
    "kind, party, channel, timestamp",
    [
        ("staff", "customer", "phone", NOW),
        ("customer", "", "phone", NOW),
        ("customer", "customer", "fax", NOW),
        ("customer", "customer", "phone", NOW.replace(tzinfo=None)),
    ],
)
def test_evidence_validation(kind, party, channel, timestamp):
    with pytest.raises(ValueError):
        DecisionEvidence(kind, party, channel, timestamp)


@pytest.mark.parametrize("field", ["subtotal_minor", "discount_minor", "tax_minor", "total_minor"])
def test_pricing_values_reject_bool_and_float_even_when_equal(field):
    initial = record()
    for value in (False, True, float(getattr(initial.entry.pricing, field))):
        with pytest.raises(ValueError):
            replace(initial.entry.pricing, **{field: value})


def test_line_decisions_reject_boolean_lookalike_and_copy_nested_collections():
    initial = record()
    with pytest.raises(ValueError):
        replace(initial.entry.line_decisions[0], approved=1)
    pricing = initial.entry.pricing
    charges = list(pricing.charges)
    copied = replace(pricing, charges=charges)
    charges.clear()
    assert copied == pricing


def test_planner_rejects_foreign_event_even_with_matching_entry():
    initial = record()
    mismatched = replace(initial, event=replace(initial.event, evidence_entry_id="other"))
    with pytest.raises(ValueError):
        plan_initial_transition(initial.ledger, order(), mismatched)


@pytest.mark.parametrize(
    "state",
    [
        "INTAKE",
        "AUTHORIZED",
        "REJECTED",
        "IN_PROGRESS",
        "WAITING_FOR_PARTS",
        "READY",
        "CLOSED",
        "CANCELLED",
    ],
)
def test_every_non_diagnosis_state_refuses_initial_plan(state):
    initial = record()
    with pytest.raises(ValueError):
        plan_initial_transition(initial.ledger, replace(order(), state=state), initial)


def test_new_recording_cannot_precede_latest_entry_or_current_head():
    original = ledger()
    initial = original.record(command(original), recorded_at=NOW + timedelta(hours=1))
    correction = command(
        initial.ledger,
        decision_id="d2",
        mode="record_correction",
        supersedes_entry_id="d1",
        reason="correct",
    )
    with pytest.raises(ValueError):
        initial.ledger.record(correction, recorded_at=NOW)
    new = revise(ledger(), now=NOW + timedelta(hours=2)).ledger
    with pytest.raises(ValueError):
        new.record(command(new), recorded_at=NOW)


def test_customer_change_after_withdrawal_respects_last_customer_time():
    original = ledger()
    initial = original.record(
        command(
            original,
            evidence=DecisionEvidence("customer", "customer", "phone", NOW + timedelta(hours=1)),
        ),
        recorded_at=NOW + timedelta(hours=1),
    )
    withdrawal = initial.ledger.record(
        command(
            initial.ledger,
            decision_id="d2",
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            supersedes_entry_id="d1",
            reason="wrong",
        ),
        recorded_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(ValueError):
        withdrawal.ledger.record(
            command(
                withdrawal.ledger,
                decision_id="d3",
                mode="customer_change",
                supersedes_entry_id="d2",
                reason="changed",
            ),
            recorded_at=NOW + timedelta(hours=1),
        )
    # A correction may fix a reported customer time within this revision's interval.
    corrected = withdrawal.ledger.record(
        command(
            withdrawal.ledger,
            decision_id="d3",
            mode="record_correction",
            supersedes_entry_id="d2",
            reason="corrected time",
        ),
        recorded_at=NOW + timedelta(hours=1),
    )
    assert corrected.entry.command.evidence.decided_at == NOW


@pytest.mark.parametrize(
    "changes",
    [
        {"supersedes_entry_id": None},
        {"supersedes_entry_id": "missing"},
        {"supersedes_entry_id": "d2"},
        {"reason": None},
        {"reason": " "},
        {"mode": "withdraw_record", "outcome": "APPROVE"},
        {"mode": "record_correction", "outcome": "WITHDRAW"},
    ],
)
def test_correction_requires_latest_target_reason_and_consistent_mode(changes):
    initial = record()
    values = {
        "decision_id": "d2",
        "mode": "record_correction",
        "supersedes_entry_id": "d1",
        "reason": "fix",
    }
    values.update(changes)
    with pytest.raises(ValueError):
        record(initial.ledger, **values)


def test_old_correction_target_cannot_branch_chain():
    initial = record()
    corrected = record(
        initial.ledger,
        decision_id="d2",
        mode="record_correction",
        supersedes_entry_id="d1",
        reason="fix",
    )
    with pytest.raises(ValueError):
        record(
            corrected.ledger,
            decision_id="d3",
            mode="record_correction",
            supersedes_entry_id="d1",
            reason="branch",
        )


def test_utc_normalization_and_all_documented_evidence_channels():
    from datetime import timezone

    for channel in ("in_person", "phone", "email", "messaging", "written", "portal"):
        evidence = DecisionEvidence(
            "representative",
            "proxy",
            channel,
            NOW.astimezone(timezone(timedelta(hours=5))),
            "opaque-reference",
            "note",
        )
        assert evidence.decided_at == NOW and evidence.decided_at.tzinfo == UTC
        result = record(evidence=evidence)
        assert result.entry.command.evidence == evidence
        assert result.entry.recording.recorded_by_actor_id == "staff"


@pytest.mark.parametrize("field, value", [("mode", "initial"), ("outcome", "APPROVE")])
def test_commands_reject_mutable_string_lookalikes(field, value):
    from collections import UserString

    with pytest.raises(ValueError):
        command(ledger(), **{field: UserString(value)})


@pytest.mark.parametrize("field, value", [("party_kind", "customer"), ("channel", "phone")])
def test_evidence_rejects_mutable_string_lookalikes(field, value):
    from collections import UserString

    evidence = DecisionEvidence("customer", "customer", "phone", NOW)
    with pytest.raises(ValueError):
        replace(evidence, **{field: UserString(value)})
