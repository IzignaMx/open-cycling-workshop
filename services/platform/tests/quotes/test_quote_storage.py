"""Private persistence codecs do not narrow the existing pure-domain API."""

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from cycling_workshop.quotes.decisions import DecisionCommand, DecisionEvidence, QuoteDecisionLedger
from cycling_workshop.quotes.domain import DiscountLine, LaborLine, PartLine, Quote, TaxLine
from cycling_workshop.quotes.history import QuoteHistory
from cycling_workshop.quotes.storage import (
    MAX_SAFE_INTEGER,
    canonical_bytes,
    decode_entry,
    decode_quote,
    encode_entry,
    encode_quote,
    validate_history_bytes,
    validate_storage_ledger,
)

NOW = datetime(2026, 10, 15, 12, tzinfo=UTC)


def uid(number):
    return f"019a0000-0000-7000-8000-{number:012x}"


def quote(lines=None):
    return Quote.for_order(
        quote_id=uid(1),
        organization_id="org",
        location_id="loc",
        order_id="order",
        currency="MXN",
        now=NOW,
        lines=lines
        if lines is not None
        else (
            LaborLine(uid(10), " Labor   snapshot ", 60, 120),
            PartLine(uid(11), "Part snapshot", "legacy-product", 2, 50),
            DiscountLine(uid(12), "Discount", 20, (uid(11), uid(10))),
            TaxLine(uid(13), "Tax", 1600, (uid(11), uid(10))),
        ),
    )


def command(book, **changes):
    head = book.history.head
    values = dict(
        decision_id=uid(100),
        organization_id="org",
        location_id="loc",
        order_id="order",
        lineage_id=uid(1),
        quote_id=head.quote_id,
        quote_version=head.version,
        expected_head_id=head.quote_id,
        expected_head_version=head.version,
        expected_decision_sequence=book.sequence,
        recorded_by_actor_id="staff",
        mode="initial",
        outcome="PARTIAL",
        approved_line_ids=(uid(10),),
        evidence=DecisionEvidence(
            "customer", "legacy-customer", "phone", NOW, "call-1", " Exact note "
        ),
    )
    values.update(changes)
    return DecisionCommand(**values)


def test_quote_round_trip_preserves_complete_snapshot_and_signed_discount():
    original = quote()
    document = encode_quote(original)
    assert decode_quote(document) == original
    assert document["totals"]["line_amounts"][2] == [uid(12), -20]
    assert document["lines"][0]["description"] == "Labor snapshot"
    document["lines"][0]["description"] = "mutated copy"
    assert original.lines[0].description == "Labor snapshot"


def test_historical_supersession_is_preserved_by_codec():
    pair = quote().revise(lines=quote().lines, quote_id=uid(2), now=NOW + timedelta(seconds=1))
    assert decode_quote(encode_quote(pair.predecessor)) == pair.predecessor
    assert decode_quote(encode_quote(pair.successor)) == pair.successor


def test_entry_round_trip_preserves_proof_recording_per_line_and_full_pricing():
    book = QuoteDecisionLedger(QuoteHistory((quote(),)))
    result = book.record(command(book), recorded_at=NOW)
    document = encode_entry(result.entry)
    assert decode_entry(document) == result.entry
    assert document["command"]["evidence"]["note"] == " Exact note "
    assert document["pricing"]["discounts"][0]["allocations"]
    assert QuoteDecisionLedger(book.history, (decode_entry(document),)) == result.ledger


@pytest.mark.parametrize(
    "mode,outcome,evidence",
    [
        ("customer_change", "REJECT", DecisionEvidence("representative", "rep", "portal", NOW)),
        (
            "record_correction",
            "APPROVE",
            DecisionEvidence("customer", "legacy-customer", "written", NOW),
        ),
        ("withdraw_record", "WITHDRAW", None),
    ],
)
def test_repository_codec_preserves_pure_modes_not_exposed_online(mode, outcome, evidence):
    book = QuoteDecisionLedger(QuoteHistory((quote(),)))
    first = book.record(command(book), recorded_at=NOW)
    selected = (uid(10), uid(11)) if outcome == "APPROVE" else ()
    second = first.ledger.record(
        command(
            first.ledger,
            decision_id=uid(101),
            mode=mode,
            outcome=outcome,
            evidence=evidence,
            approved_line_ids=selected,
            supersedes_entry_id=uid(100),
            reason="Correct record",
        ),
        recorded_at=NOW,
    )
    assert decode_entry(encode_entry(second.entry)) == second.entry
    validate_storage_ledger(second.ledger)


@pytest.mark.parametrize("value", [True, 1.0, "120", MAX_SAFE_INTEGER + 1])
def test_persisted_numeric_coercion_and_overflow_are_refused(value):
    document = encode_quote(quote())
    document["lines"][0]["hourly_rate_minor"] = value
    with pytest.raises(ValueError):
        decode_quote(document)


def test_safe_result_with_larger_internal_multiplication_is_allowed():
    original = quote((LaborLine(uid(10), "Maximum rate", 60, MAX_SAFE_INTEGER),))
    assert decode_quote(encode_quote(original)).totals.total_minor == MAX_SAFE_INTEGER


def test_pure_unbounded_arithmetic_remains_valid_but_storage_refuses_it():
    original = quote((LaborLine(uid(10), "Large", 60, MAX_SAFE_INTEGER + 1),))
    assert original.totals.total_minor == MAX_SAFE_INTEGER + 1
    with pytest.raises(ValueError):
        encode_quote(original)


def test_bounded_inputs_can_still_produce_refused_computed_money():
    original = quote((PartLine(uid(10), "Two", "product", 2, MAX_SAFE_INTEGER),))
    with pytest.raises(ValueError):
        encode_quote(original)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(unknown="field"),
        lambda d: d["lines"][0].update(unknown="field"),
        lambda d: d["totals"].update(total_minor=999),
        lambda d: d["lines"][0].update(line_id="not-v7"),
        lambda d: d["lines"][0].update(minutes=1_000_001),
        lambda d: d["lines"][0].update(description="x" * 501),
        lambda d: d["lines"][0].update(description="nul\x00text"),
        lambda d: d["lines"][0].update(description="bad\ud800"),
        lambda d: d.update(created_at="2026-10-15T12:00:00"),
        lambda d: d.update(created_at="2026-10-15T12:00:00.0000001Z"),
        lambda d: d.update(version=True),
    ],
)
def test_corrupt_storage_shape_and_boundaries_fail_closed(mutation):
    document = deepcopy(encode_quote(quote()))
    mutation(document)
    with pytest.raises(ValueError):
        decode_quote(document)


def test_storage_timestamps_are_canonical_utc_and_lossless():
    original = replace(quote(), created_at=NOW.astimezone(timezone(timedelta(hours=-6))))
    assert encode_quote(original)["created_at"] == "2026-10-15T12:00:00.000000Z"
    assert decode_quote(encode_quote(original)).created_at == NOW


def test_line_and_reference_edge_limits_are_independent():
    with pytest.raises(ValueError):
        encode_quote(quote(tuple(LaborLine(uid(1000 + i), "Work", 1, 0) for i in range(101))))
    charges = tuple(LaborLine(uid(1000 + i), "Work", 1, 0) for i in range(50))
    taxes = tuple(
        TaxLine(uid(2000 + i), "Tax", 0, tuple(x.line_id for x in charges)) for i in range(21)
    )
    with pytest.raises(ValueError):
        encode_quote(quote((*charges, *taxes)))


def test_revision_limit_does_not_block_decision_with_remaining_budget():
    book = QuoteDecisionLedger(QuoteHistory((quote(),)))
    for i in range(2, 33):
        book = book.revise(
            lines=book.history.head.lines,
            quote_id=uid(i + 1000),
            now=NOW,
            expected_head_id=book.history.head.quote_id,
            expected_head_version=book.history.head.version,
            expected_decision_sequence=book.sequence,
        ).ledger
    result = book.record(command(book), recorded_at=NOW)
    validate_storage_ledger(result.ledger)
    excessive = book.revise(
        lines=book.history.head.lines,
        quote_id=uid(1033),
        now=NOW,
        expected_head_id=book.history.head.quote_id,
        expected_head_version=32,
        expected_decision_sequence=0,
    ).ledger
    with pytest.raises(ValueError):
        validate_storage_ledger(excessive)


def test_evidence_and_full_history_budgets_are_explicit():
    book = QuoteDecisionLedger(QuoteHistory((quote(),)))
    evidence = DecisionEvidence("customer", "legacy-customer", "phone", NOW, note="x" * 2001)
    entry = book.record(command(book, evidence=evidence), recorded_at=NOW).entry
    with pytest.raises(ValueError):
        encode_entry(entry)
    with pytest.raises(ValueError):
        validate_history_bytes([{"large": "x" * (16 * 1024 * 1024)}])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1.0, object(), {1: "numeric key"}])
def test_canonical_bytes_reject_non_json_or_nonexact_numbers(bad):
    with pytest.raises(ValueError):
        canonical_bytes(bad)


@pytest.mark.parametrize("key", ["\x00", "\ud800"])
def test_canonical_json_keys_obey_text_encoding_contract(key):
    with pytest.raises(ValueError):
        canonical_bytes({key: None})


def test_forged_cyclic_dataclass_cannot_overflow_the_serializer():
    value = quote()
    object.__setattr__(value, "lines", (value,))
    with pytest.raises(ValueError):
        encode_quote(value)
