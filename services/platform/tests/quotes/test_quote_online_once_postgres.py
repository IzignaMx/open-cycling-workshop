"""One fixed 32+1 repository profile. Hosted handshake required before construction."""

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from cycling_workshop.quotes.domain import DiscountLine, LaborLine, TaxLine
from cycling_workshop.quotes.reconstruction import logical_record
from cycling_workshop.quotes.repository import QuoteConflictError, QuoteRepository
from cycling_workshop.quotes.requests import decode_initial_decision_request, decode_quote_request
from cycling_workshop.quotes.storage import canonical_bytes, encode_lines, validate_history_bytes
from cycling_workshop.service_orders.models import ServiceOrderRecord
from sqlalchemy import text
from test_administration_postgres import administration_postgres as administration_postgres
from test_quote_record_feasibility_postgres import record_reference
from test_quote_repository import admitted, counts, creation, decision, revision
from test_quote_repository_postgres import quote_postgres as quote_postgres
from test_quote_storage import NOW, uid


def atomic_state(ordinal, state):
    path = Path("/tmp/quote-online-state.json")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(dict(ordinal=ordinal, state=state)))
    temporary.replace(path)


def wait_permit(value):
    # Host owns the authoritative deadline and force-removes this container on expiry.
    path = Path("/tmp/quote-online-permit")
    while not path.exists() or path.read_text() != value:
        time.sleep(0.01)


@contextmanager
def operation(ordinal, timings):
    atomic_state(ordinal, "ready")
    wait_permit(f"grant:{ordinal}")
    started = time.monotonic()
    yield started
    timings.append(time.monotonic() - started)
    assert timings[-1] < 20
    atomic_state(ordinal, "done")
    wait_permit(f"ack:{ordinal}")


@pytest.mark.skipif(
    os.environ.get("OCWP_QUOTE_MICRO") != "contained",
    reason="host containment and handshake required",
)
def test_one_online_profile(quote_postgres):
    db = quote_postgres
    timings = []
    records = []
    raw_sizes = []
    replay_cases = []
    cpu_started = time.process_time()
    for ordinal in range(1, 33):
        with operation(ordinal, timings):
            if ordinal == 1:
                with db.factory() as session:
                    assert session.scalar(text("SHOW lock_timeout")) == "15s"
                    assert session.scalar(text("SHOW statement_timeout")) == "20s"
                    assert int(session.scalar(text("SHOW server_version_num"))) // 10000 == 18
                description = (
                    "Synthetic inspection of braking steering bearings and drivetrain. " * 8
                )[:499] + "."
                assert len(description) == len(description.encode("ascii")) == 500
                assert " ".join(description.split()) == description
                charges = tuple(LaborLine(uid(1000 + i), description, 60, 10000) for i in range(80))
                targets = tuple(line.line_id for line in charges[:50])
                lines = (
                    *charges,
                    *(DiscountLine(uid(1080 + i), description, 50, targets) for i in range(10)),
                    *(TaxLine(uid(1090 + i), description, 1000, targets) for i in range(10)),
                )
            document = dict(
                kind="create" if ordinal == 1 else "revise",
                operation_id=uid(199 + ordinal),
                quote_id=uid(ordinal),
                expected_order_version=1,
                lines=encode_lines(lines),
            )
            if ordinal == 1:
                document["currency"] = "MXN"
            else:
                document.update(
                    lineage_id=uid(1),
                    expected_head_id=uid(ordinal - 1),
                    expected_head_version=ordinal - 1,
                    expected_decision_sequence=0,
                )
            raw = canonical_bytes(document)
            request = decode_quote_request([raw])
            assert all(line.description == description for line in request.lines)
            common = dict(
                operation_id=request.operation_id,
                quote_id=request.quote_id,
                expected_order_version=request.expected_order_version,
                lines=request.lines,
            )
            command = (
                creation(**common, currency=request.currency)
                if ordinal == 1
                else revision(
                    **common,
                    lineage_id=request.lineage_id,
                    expected_head_id=request.expected_head_id,
                    expected_head_version=request.expected_head_version,
                    expected_decision_sequence=request.expected_decision_sequence,
                )
            )
            with db.factory() as session:
                admitted(session)
                result = QuoteRepository(session).apply(command, recorded_at=NOW)
                session.commit()
            assert result.ledger.history.head.version == ordinal
            assert result.ledger.sequence == 0
            totals = result.ledger.history.head.totals
            assert (
                totals.subtotal_minor,
                totals.discount_minor,
                totals.tax_minor,
                totals.total_minor,
            ) == (800000, 500, 499500, 1299000)
            record = logical_record(command, result.ledger)
            assert len(canonical_bytes(record)) <= 262144
            records.append(record)
            raw_sizes.append(len(raw))
            if ordinal in (1, 16):
                replay_cases.append((command, result.receipt))
    with operation(33, timings):
        excessive = revision(
            operation_id=uid(232),
            quote_id=uid(33),
            lines=lines,
            expected_head_id=uid(32),
            expected_head_version=32,
        )
        with db.factory() as session:
            admitted(session)
            with pytest.raises(
                QuoteConflictError, match="quote storage history count limit exceeded"
            ):
                QuoteRepository(session).apply(excessive, recorded_at=NOW)
            assert counts(session) == (1, 32, 32, 32)
            unchanged = QuoteRepository(session).load("a", "location-a", "order-a")
            assert unchanged.ledger == result.ledger
            order = session.get(ServiceOrderRecord, "order-a")
            assert order.state == "DIAGNOSIS" and order.version == 1
            session.commit()
    with operation(34, timings):
        note = (
            "Synthetic customer approval recorded for this inspection and itemized estimate. " * 27
        )[:1999] + "."
        reference = record_reference()
        assert len(note) == len(note.encode("ascii")) == 2000
        assert len(reference) == len(reference.encode("ascii")) == 200
        raw = canonical_bytes(
            dict(
                decision_id=uid(100),
                expected_order_version=1,
                lineage_id=uid(1),
                expected_head_id=uid(32),
                expected_head_version=32,
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
        request = decode_initial_decision_request([raw], action="authorize")
        assert request.approved_line_ids == () and request.expected_order_version == 1
        with db.factory() as session:
            admitted(session)
            locked = QuoteRepository(session).load("a", "location-a", "order-a")
            selected = tuple(
                line.line_id
                for line in locked.ledger.history.head.lines
                if isinstance(line, LaborLine)
            )
            assert len(selected) == 80
            approve = decision(
                decision_id=request.decision_id,
                lineage_id=request.lineage_id,
                quote_id=request.expected_head_id,
                quote_version=request.expected_head_version,
                expected_head_id=request.expected_head_id,
                expected_head_version=request.expected_head_version,
                expected_decision_sequence=request.expected_decision_sequence,
                outcome="APPROVE",
                approved_line_ids=selected,
                evidence=request.evidence,
            )
            result = QuoteRepository(session).apply(approve, recorded_at=NOW)
            assert result.order.state == "DIAGNOSIS" and result.order.version == 1
            assert counts(session) == (1, 32, 33, 33)
            session.commit()
        assert result.ledger.sequence == 1
        assert len(result.ledger.entries) == 1
        assert result.ledger.entries[-1].command.outcome == "APPROVE"
        assert result.ledger.entries[-1].command.approved_line_ids == selected
        pricing = result.ledger.entries[-1].pricing
        assert (
            pricing.subtotal_minor,
            pricing.discount_minor,
            pricing.tax_minor,
            pricing.total_minor,
        ) == (800000, 500, 499500, 1299000)
        assert sum(len(item.allocations) for item in pricing.discounts) == 500
        assert sum(len(item.base_line_ids) for item in pricing.taxes) == 500
        records.append(logical_record(approve, result.ledger))
        raw_sizes.append(len(raw))
        replay_cases.append((approve, result.receipt))
    with operation(35, timings), db.factory() as session:
        admitted(session)
        snapshot = QuoteRepository(session).load("a", "location-a", "order-a")
        assert snapshot.ledger == result.ledger
        assert len(snapshot.receipts) == 33
        assert len(snapshot.ledger.history.revisions) == 32
        assert counts(session) == (1, 32, 33, 33)
        session.commit()
    for ordinal, (command, receipt) in enumerate(replay_cases, 36):
        with operation(ordinal, timings), db.factory() as session:
            admitted(session)
            replay = QuoteRepository(session).apply(command, recorded_at=NOW)
            assert replay.replayed and replay.receipt == receipt
            assert replay.ledger == snapshot.ledger
            assert replay.order.state == "DIAGNOSIS" and replay.order.version == 1
            assert counts(session) == (1, 32, 33, 33)
            session.commit()
    with operation(39, timings) as final_started:
        record_bytes = [len(canonical_bytes(record)) for record in records]
        history_bytes = len(canonical_bytes(records))
        validate_history_bytes(records)
        assert len(record_bytes) == len(raw_sizes) == 33
        assert all(0 < size <= 262144 for size in record_bytes)
        assert all(0 < size <= 131072 for size in raw_sizes)
        assert history_bytes == sum(record_bytes) + 34 <= 8650786
        # Host deadline includes the evidence write and commit of the done checkpoint.
        Path("/tmp/quote-micro-result.json").write_text(
            json.dumps(
                dict(
                    new_operations=33,
                    revisions=32,
                    decisions=1,
                    lines_per_revision=100,
                    target_edges=1000,
                    service_order_state="DIAGNOSIS",
                    service_order_version=1,
                    lock_timeout_ms=15000,
                    statement_timeout_ms=20000,
                    maximum_capacity_qualified=False,
                    revision33_rejected=True,
                    exact_retries=3,
                    operation_seconds=[*timings, time.monotonic() - final_started],
                    process_cpu_seconds=time.process_time() - cpu_started,
                    record_bytes=record_bytes,
                    history_bytes=history_bytes,
                    raw_request_bytes=raw_sizes,
                )
            )
        )
