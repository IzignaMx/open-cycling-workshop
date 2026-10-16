"""Opt-in three-operation hosted probe; never a maximum history or activation."""

import json
import os
import time
from pathlib import Path

import pytest
from cycling_workshop.quotes.repository import QuoteRepository
from sqlalchemy import text
from test_administration_postgres import administration_postgres as administration_postgres
from test_quote_repository import admitted, counts, creation, decision, revision
from test_quote_repository_postgres import quote_postgres as quote_postgres
from test_quote_storage import NOW, uid


@pytest.mark.skipif(
    os.environ.get("OCWP_QUOTE_MICRO") != "contained", reason="host containment preflight required"
)
def test_three_operations_fresh_load_and_exact_retry(quote_postgres):
    db = quote_postgres
    timings = {}
    cpu_started = time.process_time()
    with db.factory() as session:
        assert session.scalar(text("SHOW lock_timeout")) == "15s"
        assert session.scalar(text("SHOW statement_timeout")) == "20s"
        assert int(session.scalar(text("SHOW server_version_num"))) // 10000 == 18
    commands = [
        creation(),
        revision(),
        decision(
            quote_id=uid(2), quote_version=2, expected_head_id=uid(2), expected_head_version=2
        ),
    ]
    receipts = []
    for label, command in zip(("create", "revise", "decision"), commands, strict=True):
        started = time.monotonic()
        with db.factory() as session:
            admitted(session)
            result = QuoteRepository(session).apply(command, recorded_at=NOW)
            session.commit()
            receipts.append(result.receipt)
        timings[label] = time.monotonic() - started
        assert timings[label] < 20
    started = time.monotonic()
    with db.factory() as session:
        admitted(session)
        snapshot = QuoteRepository(session).load("a", "location-a", "order-a")
        assert len(snapshot.ledger.history.revisions) == 2
        assert snapshot.ledger.sequence == 1
        assert len(snapshot.ledger.history.head.lines) == 4
        assert counts(session) == (1, 2, 3, 3)
        session.commit()
    timings["fresh_load"] = time.monotonic() - started
    started = time.monotonic()
    with db.factory() as session:
        admitted(session)
        replay = QuoteRepository(session).apply(commands[0], recorded_at=NOW)
        assert replay.replayed and replay.receipt == receipts[0]
        assert replay.ledger == snapshot.ledger
        assert counts(session) == (1, 2, 3, 3)
        session.commit()
    timings["exact_retry"] = time.monotonic() - started
    assert all(seconds < 20 for seconds in timings.values())
    Path("/tmp/quote-micro-result.json").write_text(
        json.dumps(
            {
                "new_operations": 3,
                "revisions": 2,
                "decisions": 1,
                "lines_per_revision": 4,
                "lock_timeout_ms": 15000,
                "statement_timeout_ms": 20000,
                "operation_seconds": timings,
                "process_cpu_seconds": time.process_time() - cpu_started,
                "maximum_capacity_qualified": False,
            }
        )
    )
