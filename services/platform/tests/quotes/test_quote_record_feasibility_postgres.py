"""One fixed legal record shape; opt-in hosted only, never a history-size trial."""

import json
import os
import time
from pathlib import Path

import pytest
from cycling_workshop.quotes.domain import DiscountLine, LaborLine, TaxLine
from cycling_workshop.quotes.reconstruction import logical_record
from cycling_workshop.quotes.repository import QuoteRepository
from cycling_workshop.quotes.requests import decode_initial_decision_request, decode_quote_request
from cycling_workshop.quotes.storage import canonical_bytes, encode_lines, validate_history_bytes
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from test_administration_postgres import administration_postgres as administration_postgres
from test_quote_repository import admitted, counts, creation, decision
from test_quote_repository_postgres import quote_postgres as quote_postgres
from test_quote_storage import NOW, uid


@pytest.mark.skipif(
    os.environ.get("OCWP_QUOTE_MICRO") != "contained", reason="host containment preflight required"
)
def test_one_fixed_revision_and_initial_decision(quote_postgres):
    progress = dict(stage="setup_sql", failure_type=None, byte_counts={})
    checkpoint(progress, "setup_sql")
    try:
        fixed_record(quote_postgres, progress)
    except Exception as error:
        progress["failure_type"] = {
            "AssertionError": "assertion",
            "QuoteRequestError": "request_error",
            "QuoteConflictError": "quote_conflict",
            "QuoteIntegrityError": "quote_integrity",
        }.get(
            type(error).__name__,
            "database_error"
            if isinstance(error, SQLAlchemyError)
            else "value_error"
            if isinstance(error, ValueError)
            else "unexpected",
        )
        checkpoint(progress, progress["stage"])
        raise


def checkpoint(progress, stage, **counts):
    progress["stage"] = stage
    progress["byte_counts"].update(counts)
    Path("/tmp/quote-record-diagnostic.json").write_text(json.dumps(progress))


def fixed_record(quote_postgres, progress):
    db = quote_postgres
    cpu_started = time.process_time()
    timings = {}
    with db.factory() as session:
        assert session.scalar(text("SHOW lock_timeout")) == "15s"
        assert session.scalar(text("SHOW statement_timeout")) == "20s"
        assert int(session.scalar(text("SHOW server_version_num"))) // 10000 == 18
    started = time.monotonic()
    checkpoint(progress, "input_text")
    # Fixed schema-field boundary text, no extra padding fields or parameter search.
    description = ("Synthetic inspection of braking steering bearings and drivetrain. " * 8)[
        :499
    ] + "."
    note = (
        "Synthetic customer approval recorded for this inspection and itemized estimate. " * 27
    )[:1999] + "."
    reference = ("Synthetic inspection reference for the recorded customer approval. " * 4)[
        :199
    ] + "."
    for value, length in ((description, 500), (note, 2000), (reference, 200)):
        assert len(value) == len(value.encode("ascii")) == length
        assert " ".join(value.split()) == value
    charges = tuple(LaborLine(uid(1000 + i), description, 60, 10000) for i in range(80))
    targets = tuple(line.line_id for line in charges[:50])
    lines = (
        *charges,
        *(DiscountLine(uid(1080 + i), description, 50, targets) for i in range(10)),
        *(TaxLine(uid(1090 + i), description, 1000, targets) for i in range(10)),
    )
    raw_create = canonical_bytes(
        dict(
            kind="create",
            operation_id=uid(200),
            quote_id=uid(1),
            expected_order_version=1,
            currency="MXN",
            lines=encode_lines(lines),
        )
    )
    checkpoint(progress, "create_decode", raw_create_bytes=len(raw_create))
    request = decode_quote_request([raw_create])
    assert len(request.lines) == 100
    assert all(line.description == description for line in request.lines)
    create = creation(
        lines=request.lines,
        operation_id=request.operation_id,
        quote_id=request.quote_id,
        expected_order_version=request.expected_order_version,
        currency=request.currency,
    )
    checkpoint(progress, "create_apply")
    with db.factory() as session:
        admitted(session)
        created = QuoteRepository(session).apply(create, recorded_at=NOW)
        session.commit()
    timings["create"] = time.monotonic() - started
    checkpoint(progress, "revision_bytes")
    revision_record = logical_record(create, created.ledger)
    checkpoint(
        progress, "revision_totals", revision_logical_bytes=len(canonical_bytes(revision_record))
    )
    totals = created.ledger.history.head.totals
    assert (totals.subtotal_minor, totals.discount_minor, totals.tax_minor, totals.total_minor) == (
        800000,
        500,
        499500,
        1299000,
    )
    started = time.monotonic()
    raw_decision = canonical_bytes(
        dict(
            decision_id=uid(100),
            expected_order_version=1,
            lineage_id=uid(1),
            expected_head_id=uid(1),
            expected_head_version=1,
            expected_decision_sequence=0,
            evidence=dict(
                party_kind="customer",
                party_id="customer-a",
                channel="written",
                decided_at="2026-10-15T12:00:00.000000Z",
                source_reference=reference,
                note=note,
            ),
        )
    )
    checkpoint(progress, "decision_decode", raw_decision_bytes=len(raw_decision))
    initial = decode_initial_decision_request([raw_decision], action="authorize")
    assert initial.approved_line_ids == ()  # The request cannot supply full-authorize selection.
    checkpoint(progress, "decision_load")
    with db.factory() as session:
        admitted(session)
        locked = QuoteRepository(session).load("a", "location-a", "order-a")
        selected = tuple(
            line.line_id for line in locked.ledger.history.head.lines if isinstance(line, LaborLine)
        )
        assert len(selected) == 80
        assert initial.action == "authorize" and initial.expected_order_version == 1
        approve = decision(
            decision_id=initial.decision_id,
            lineage_id=initial.lineage_id,
            quote_id=initial.expected_head_id,
            quote_version=initial.expected_head_version,
            expected_head_id=initial.expected_head_id,
            expected_head_version=initial.expected_head_version,
            expected_decision_sequence=initial.expected_decision_sequence,
            outcome="APPROVE",
            approved_line_ids=selected,
            evidence=initial.evidence,
        )
        assert approve.expected_order_version == initial.expected_order_version
        checkpoint(progress, "decision_apply")
        decided = QuoteRepository(session).apply(approve, recorded_at=NOW)
        session.commit()
    timings["decision"] = time.monotonic() - started
    checkpoint(progress, "decision_bytes")
    decision_record = logical_record(approve, decided.ledger)
    checkpoint(
        progress, "decision_pricing", decision_logical_bytes=len(canonical_bytes(decision_record))
    )
    entry = decided.ledger.entries[-1]
    assert entry.command.evidence == initial.evidence
    assert entry.command.evidence.note == note
    assert entry.command.evidence.source_reference == reference
    assert len(entry.pricing.discounts) == len(entry.pricing.taxes) == 10
    assert sum(len(item.allocations) for item in entry.pricing.discounts) == 500
    assert sum(len(item.base_line_ids) for item in entry.pricing.taxes) == 500
    assert (
        entry.pricing.subtotal_minor,
        entry.pricing.discount_minor,
        entry.pricing.tax_minor,
        entry.pricing.total_minor,
    ) == (800000, 500, 499500, 1299000)
    logical = [revision_record, decision_record]
    checkpoint(progress, "history_bytes", two_record_history_bytes=len(canonical_bytes(logical)))
    validate_history_bytes(logical)
    checkpoint(progress, "fresh_load")
    started = time.monotonic()
    with db.factory() as session:
        admitted(session)
        snapshot = QuoteRepository(session).load("a", "location-a", "order-a")
        assert snapshot.ledger == decided.ledger
        assert len(snapshot.receipts) == 2
        assert counts(session) == (1, 1, 2, 2)
        session.commit()
    timings["fresh_load"] = time.monotonic() - started
    checkpoint(progress, "exact_retry")
    started = time.monotonic()
    with db.factory() as session:
        admitted(session)
        replay = QuoteRepository(session).apply(create, recorded_at=NOW)
        assert replay.replayed and replay.receipt == created.receipt
        assert replay.ledger == snapshot.ledger
        assert counts(session) == (1, 1, 2, 2)
        session.commit()
    timings["exact_retry"] = time.monotonic() - started
    assert all(seconds < 20 for seconds in timings.values())
    checkpoint(progress, "result_write")
    Path("/tmp/quote-micro-result.json").write_text(
        json.dumps(
            dict(
                new_operations=2,
                revisions=1,
                decisions=1,
                lines_per_revision=100,
                lock_timeout_ms=15000,
                statement_timeout_ms=20000,
                maximum_capacity_qualified=False,
                operation_seconds=timings,
                process_cpu_seconds=time.process_time() - cpu_started,
                record_feasibility=dict(
                    target_edges=sum(
                        len(line.scope_line_ids)
                        if isinstance(line, DiscountLine)
                        else len(line.base_line_ids)
                        for line in lines[80:]
                    ),
                    labor_lines=80,
                    discount_lines=10,
                    tax_lines=10,
                    approved_charges=len(selected),
                    discount_allocations=sum(
                        len(item.allocations) for item in entry.pricing.discounts
                    ),
                    tax_targets=sum(len(item.base_line_ids) for item in entry.pricing.taxes),
                    description_codepoints=len(description),
                    description_utf8_bytes=len(description.encode()),
                    note_codepoints=len(note),
                    note_utf8_bytes=len(note.encode()),
                    source_reference_codepoints=len(reference),
                    source_reference_utf8_bytes=len(reference.encode()),
                    subtotal_minor=totals.subtotal_minor,
                    discount_minor=totals.discount_minor,
                    tax_minor=totals.tax_minor,
                    total_minor=totals.total_minor,
                    raw_create_bytes=len(raw_create),
                    raw_decision_bytes=len(raw_decision),
                    revision_logical_bytes=len(canonical_bytes(revision_record)),
                    decision_logical_bytes=len(canonical_bytes(decision_record)),
                    two_record_history_bytes=len(canonical_bytes(logical)),
                ),
            )
        )
    )

    checkpoint(progress, "complete")
