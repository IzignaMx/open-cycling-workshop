"""One opt-in four-revision diagnostic; no capacity or latency qualification."""

import cProfile
import json
import os
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from cycling_workshop.quotes import commands, reconstruction, repository, storage
from cycling_workshop.quotes.commands import CreateQuoteCommand, ReviseQuoteCommand
from cycling_workshop.quotes.domain import DiscountLine, LaborLine, TaxLine
from cycling_workshop.quotes.models import QuoteDecisionRecord
from cycling_workshop.quotes.repository import QuoteRepository
from cycling_workshop.quotes.requests import CreateQuoteRequest, decode_quote_request
from cycling_workshop.service_orders.models import ServiceOrderRecord
from sqlalchemy import event, func, select, text
from test_administration_postgres import administration_postgres as administration_postgres
from test_quote_repository import admitted, counts
from test_quote_repository_postgres import quote_postgres as quote_postgres
from test_quote_storage import NOW, uid

# Bind exact code objects, not profiler string matches. These five source identities
# are reviewed alongside the independent host validator. Timings overlap: neither
# cumulative values nor the candidate/load/commit spans are additive buckets.
PROFILE_FUNCTIONS = {
    "reconstruct": reconstruction._reconstruct,
    "row_assembly": reconstruction._revision_document,
    "canonical_json": storage.canonical_bytes,
    "quote_codec": storage.encode_quote,
    "command_proof": commands.command_from_proof,
}


def profile_functions(profiler):
    observed = {entry.code: entry for entry in profiler.getstats()}
    result = {}
    for label, function in PROFILE_FUNCTIONS.items():
        entry = observed.get(function.__code__)
        result[label] = (
            None
            if entry is None
            else {
                "primitive_calls": entry.callcount - entry.reccallcount,
                "total_calls": entry.callcount,
                "own_seconds": entry.inlinetime,
                "cumulative_seconds": entry.totaltime,
            }
        )
    return result


def atomic_progress(destination, progress):
    payload = json.dumps(progress, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(payload) >= 16384:
        raise ValueError("profile output exceeds fixed bound")
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def initial_progress():
    return {
        "schema": 1,
        "active_ordinal": None,
        "complete": False,
        "process_cpu_seconds": None,
        "records": [],
    }


class ProfileActions:
    def __init__(self, progress, destination, *, cpu_started):
        self.progress = progress
        self.destination = destination
        self.cpu_started = cpu_started
        self.active = None
        self.cursor_started = None
        self.cursor_verb = None

    @contextmanager
    def span(self, label):
        if self.active is None:
            yield
            return
        started = time.monotonic()
        try:
            yield
        finally:
            self.active[label]["calls"] += 1
            self.active[label]["seconds"] += time.monotonic() - started

    def before_cursor(self, connection, cursor, statement, parameters, context, executemany):
        # Deliberately retain no SQL text, parameters or execution context.
        if self.active is not None:
            assert self.cursor_started is None
            self.cursor_started = time.monotonic()
            first = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "OTHER"
            self.cursor_verb = (
                first if first in {"SELECT", "INSERT", "UPDATE", "DELETE"} else "OTHER"
            )

    def after_cursor(self, connection, cursor, statement, parameters, context, executemany):
        if self.active is not None:
            assert self.cursor_started is not None
            self.active["sql"]["calls"] += 1
            self.active["sql"]["seconds"] += time.monotonic() - self.cursor_started
            self.active["sql"]["verbs"][self.cursor_verb] += 1
            self.cursor_started = None
            self.cursor_verb = None

    def run(self, ordinal, action, operation):
        expected = ("create", "revise", "revise", "revise", "fresh_load", "exact_retry")
        assert type(ordinal) is int and 1 <= ordinal <= 6
        assert ordinal == len(self.progress["records"]) + 1
        assert action == expected[ordinal - 1] and not self.progress["complete"]
        self.progress["active_ordinal"] = ordinal
        atomic_progress(self.destination, self.progress)
        self.active = {
            label: {"calls": 0, "seconds": 0.0}
            for label in ("candidate", "reconstruction", "commit", "sql")
        }
        self.active["sql"]["verbs"] = dict.fromkeys(
            ("SELECT", "INSERT", "UPDATE", "DELETE", "OTHER"), 0
        )
        profiler = cProfile.Profile()
        wall_started, cpu_started = time.monotonic(), time.process_time()
        profiler.enable()
        try:
            evidence = operation()
        finally:
            profiler.disable()
            wall_seconds = time.monotonic() - wall_started
            cpu_seconds = time.process_time() - cpu_started
            spans, self.active = self.active, None
        # An exception never reaches this publication: its active ordinal and last
        # contiguous completed prefix survive. Missing metrics are not zero-filled.
        assert self.cursor_started is None
        record = {
            "ordinal": ordinal,
            "action": action,
            "wall_seconds": wall_seconds,
            "process_cpu_seconds": cpu_seconds,
            **spans,
            "functions": profile_functions(profiler),
            **evidence,
        }
        self.progress["records"].append(record)
        self.progress["active_ordinal"] = None
        if ordinal == 6:
            self.progress["complete"] = True
            self.progress["process_cpu_seconds"] = time.process_time() - self.cpu_started
        atomic_progress(self.destination, self.progress)


@pytest.fixture
def profile_postgres(request):
    # This starts before the ordinary PostgreSQL fixture, without modifying its
    # setup or teardown. The host's 20s wall cutoff also includes pytest bootstrap.
    assert os.environ.get("OCWP_QUOTE_MICRO") == "contained"
    cpu_started = time.process_time()
    progress = initial_progress()
    destination = Path("/tmp/quote-profile-result.json")
    atomic_progress(destination, progress)
    db = request.getfixturevalue("quote_postgres")
    return db, ProfileActions(progress, destination, cpu_started=cpu_started)


@pytest.mark.skipif(
    os.environ.get("OCWP_QUOTE_MICRO") != "contained", reason="host containment preflight required"
)
def test_four_revisions_fresh_load_and_exact_retry(profile_postgres, monkeypatch):
    # No full-shape construction occurs on import or through the tiny helper tests.
    assert os.environ.get("OCWP_QUOTE_MICRO") == "contained"
    db, measurement = profile_postgres
    with db.factory() as session:
        assert session.scalar(text("SHOW lock_timeout")) == "15s"
        assert session.scalar(text("SHOW statement_timeout")) == "20s"
        assert int(session.scalar(text("SHOW server_version_num"))) // 10000 == 18
        original_order = tuple(
            session.execute(
                select(ServiceOrderRecord.__table__).where(ServiceOrderRecord.id == "order-a")
            ).one()
        )

    advance = repository.advance
    load_with_bytes = QuoteRepository._load_with_bytes

    def timed_advance(*args, **kwargs):
        with measurement.span("candidate"):
            return advance(*args, **kwargs)

    def timed_load(self, *args, **kwargs):
        with measurement.span("reconstruction"):
            return load_with_bytes(self, *args, **kwargs)

    monkeypatch.setattr(repository, "advance", timed_advance)
    monkeypatch.setattr(QuoteRepository, "_load_with_bytes", timed_load)
    event.listen(db.engine, "before_cursor_execute", measurement.before_cursor)
    event.listen(db.engine, "after_cursor_execute", measurement.after_cursor)
    receipts, results, logical_sizes = [], [], []
    raw_create = None
    loaded = None

    def fixed_lines():
        # Exactly the separately reviewed record shape; no size parameter, search,
        # padding field or alternate recipe. Rebuild inside every append action.
        description = ("Synthetic inspection of braking steering bearings and drivetrain. " * 8)[
            :499
        ] + "."
        assert len(description) == len(description.encode("ascii")) == 500
        assert " ".join(description.split()) == description
        charges = tuple(LaborLine(uid(1000 + i), description, 60, 10000) for i in range(80))
        targets = tuple(line.line_id for line in charges[:50])
        lines = (
            *charges,
            *(DiscountLine(uid(1080 + i), description, 50, targets) for i in range(10)),
            *(TaxLine(uid(1090 + i), description, 1000, targets) for i in range(10)),
        )
        assert len(lines) == 100
        assert (
            sum(len(line.scope_line_ids) for line in lines if isinstance(line, DiscountLine)) == 500
        )
        assert sum(len(line.base_line_ids) for line in lines if isinstance(line, TaxLine)) == 500
        return lines

    def command_from_request(raw):
        request = decode_quote_request([raw])
        common = {
            "operation_id": request.operation_id,
            "quote_id": request.quote_id,
            "organization_id": "a",
            "location_id": "location-a",
            "order_id": "order-a",
            "actor_id": "actor-a",
            "expected_order_version": request.expected_order_version,
            "lines": request.lines,
        }
        if isinstance(request, CreateQuoteRequest):
            return CreateQuoteCommand(**common, currency=request.currency)
        return ReviseQuoteCommand(
            **common,
            lineage_id=request.lineage_id,
            expected_head_id=request.expected_head_id,
            expected_head_version=request.expected_head_version,
            expected_decision_sequence=request.expected_decision_sequence,
        )

    def assert_stored(session, revisions):
        actual = counts(session)
        assert actual == (1, revisions, revisions, revisions)
        assert session.scalar(select(func.count()).select_from(QuoteDecisionRecord)) == 0
        assert (
            tuple(
                session.execute(
                    select(ServiceOrderRecord.__table__).where(ServiceOrderRecord.id == "order-a")
                ).one()
            )
            == original_order
        )
        return list(actual)

    def evidence(revisions, actual_counts, raw_size=None, logical_size=None):
        # Canonical JSON arrays have only [, commas, ]; their member byte counts
        # were measured from each immutable operation-time record, before supersession.
        history_bytes = 2 + sum(logical_sizes) + len(logical_sizes) - 1
        assert 0 < history_bytes <= 16 * 1024 * 1024
        return {
            "raw_request_bytes": raw_size,
            "logical_bytes": logical_size,
            "history_bytes": history_bytes,
            "revisions": revisions,
            "receipts": len(receipts),
            "counts": actual_counts,
        }

    def append_revision(version):
        nonlocal raw_create
        lines = fixed_lines()
        document = {
            "kind": "create" if version == 1 else "revise",
            "operation_id": uid(199 + version),
            "quote_id": uid(version),
            "expected_order_version": 1,
            "lines": storage.encode_lines(lines),
        }
        if version == 1:
            document["currency"] = "MXN"
        else:
            document.update(
                lineage_id=uid(1),
                expected_head_id=uid(version - 1),
                expected_head_version=version - 1,
                expected_decision_sequence=0,
            )
        raw = storage.canonical_bytes(document)
        if version == 1:
            raw_create = raw
        command = command_from_request(raw)
        assert command.lines == lines
        recorded_at = NOW + timedelta(seconds=version - 1)
        with db.factory() as session:
            admitted(session)
            result = QuoteRepository(session).apply(command, recorded_at=recorded_at)
            assert not result.replayed
            assert result.receipt.command == command
            assert result.receipt.ordinal == result.receipt.quote_version == version
            assert result.receipt.operation_id == uid(199 + version)
            assert result.receipt.quote_id == uid(version)
            assert result.receipt.decision_sequence == 0
            assert result.receipt.recorded_at == recorded_at
            assert result.receipt.quote_outbox_id not in {item.quote_outbox_id for item in receipts}
            assert result.ledger.sequence == 0 and result.ledger.entries == ()
            assert result.ledger.projection.outcome == "NO_CURRENT_DECISION"
            head = result.ledger.history.head
            assert head.quote_id == uid(version) and head.version == version
            assert head.lines == lines and head.currency == "MXN"
            assert len(result.ledger.history.revisions) == version
            assert (
                head.totals.subtotal_minor,
                head.totals.discount_minor,
                head.totals.tax_minor,
                head.totals.total_minor,
            ) == (800000, 500, 499500, 1299000)
            if results:
                previous = results[-1].ledger.history
                assert result.ledger.history.revisions[:-2] == previous.revisions[:-1]
                assert result.ledger.history.revisions[-2] == replace(
                    previous.head, superseded_at=recorded_at, superseded_by=head.quote_id
                )
            assert (result.order.state, result.order.version) == ("DIAGNOSIS", 1)
            logical_size = len(
                storage.canonical_bytes(reconstruction.logical_record(command, result.ledger))
            )
            assert 0 < logical_size <= 256 * 1024
            actual_counts = assert_stored(session, version)
            with measurement.span("commit"):
                session.commit()
        receipts.append(result.receipt)
        results.append(result)
        logical_sizes.append(logical_size)
        return evidence(version, actual_counts, len(raw), logical_size)

    def fresh_load():
        nonlocal loaded
        with db.factory() as session:
            admitted(session)
            loaded = QuoteRepository(session).load("a", "location-a", "order-a")
            assert loaded is not None
            assert loaded.ledger == results[-1].ledger
            assert loaded.receipts == tuple(receipts)
            actual_counts = assert_stored(session, 4)
            with measurement.span("commit"):
                session.commit()
        return evidence(4, actual_counts)

    def exact_retry():
        assert raw_create is not None and loaded is not None
        command = command_from_request(raw_create)
        assert command == receipts[0].command
        with db.factory() as session:
            admitted(session)
            replay = QuoteRepository(session).apply(command, recorded_at=NOW)
            assert replay.replayed and replay.receipt == receipts[0]
            assert replay.ledger == loaded.ledger == results[-1].ledger
            assert (replay.order.state, replay.order.version) == ("DIAGNOSIS", 1)
            assert replay.ledger.entries == () and replay.ledger.sequence == 0
            assert len(loaded.receipts) == len(receipts) == len(results) == len(logical_sizes) == 4
            actual_counts = assert_stored(session, 4)
            with measurement.span("commit"):
                session.commit()
        return evidence(4, actual_counts)

    try:
        measurement.run(1, "create", lambda: append_revision(1))
        measurement.run(2, "revise", lambda: append_revision(2))
        measurement.run(3, "revise", lambda: append_revision(3))
        measurement.run(4, "revise", lambda: append_revision(4))
        measurement.run(5, "fresh_load", fresh_load)
        measurement.run(6, "exact_retry", exact_retry)
    finally:
        event.remove(db.engine, "before_cursor_execute", measurement.before_cursor)
        event.remove(db.engine, "after_cursor_execute", measurement.after_cursor)


def test_profile_helpers_report_only_observed_allowlisted_functions():
    profiler = cProfile.Profile()
    profiler.runcall(lambda: sum((1, 2)))
    assert profile_functions(profiler) == {
        "reconstruct": None,
        "row_assembly": None,
        "canonical_json": None,
        "quote_codec": None,
        "command_proof": None,
    }


def test_profile_helpers_atomic_replace_and_size_limit(tmp_path, monkeypatch):
    destination = tmp_path / "progress.json"
    initial = {"schema": 1, "records": []}
    atomic_progress(destination, initial)
    assert json.loads(destination.read_bytes()) == initial
    original = destination.read_bytes()
    with pytest.raises(ValueError, match="profile output exceeds fixed bound"):
        atomic_progress(destination, {"padding": "x" * 16384})
    assert destination.read_bytes() == original

    def interrupted_replace(source, target):
        assert Path(source).read_bytes() != original
        assert Path(target) == destination
        raise OSError("synthetic interruption")

    monkeypatch.setattr("os.replace", interrupted_replace)
    with pytest.raises(OSError, match="synthetic interruption"):
        atomic_progress(destination, {"schema": 1, "records": [1]})
    assert destination.read_bytes() == original


def test_profile_helpers_failed_action_retains_completed_prefix(tmp_path):
    progress = initial_progress()
    destination = tmp_path / "progress.json"
    measurement = ProfileActions(progress, destination, cpu_started=0.0)

    def small_action():
        return {
            "raw_request_bytes": None,
            "logical_bytes": None,
            "history_bytes": None,
            "revisions": 1,
            "receipts": 1,
            "counts": [1, 1, 1, 1],
        }

    measurement.run(1, "create", small_action)
    completed = json.loads(destination.read_bytes())
    assert completed["records"][0]["ordinal"] == 1
    assert completed["records"][0]["functions"]["reconstruct"] is None
    assert completed["process_cpu_seconds"] is None

    def fail():
        raise AssertionError("synthetic action failure")

    with pytest.raises(AssertionError, match="synthetic action failure"):
        measurement.run(2, "revise", fail)
    interrupted = json.loads(destination.read_bytes())
    assert interrupted["records"] == completed["records"]
    assert interrupted["active_ordinal"] == 2
    assert interrupted["complete"] is False
    assert interrupted["process_cpu_seconds"] is None


def test_profile_helpers_observed_tiny_json_has_own_and_cumulative_metrics():
    profiler = cProfile.Profile()
    assert profiler.runcall(storage.canonical_bytes, {"value": 1}) == b'{"value":1}'
    metrics = profile_functions(profiler)
    canonical = metrics["canonical_json"]
    assert canonical["primitive_calls"] == canonical["total_calls"] == 1
    assert 0 <= canonical["own_seconds"] <= canonical["cumulative_seconds"]
    assert metrics["reconstruct"] is metrics["row_assembly"] is None
    assert metrics["quote_codec"] is metrics["command_proof"] is None
    assert set(canonical) == {"primitive_calls", "total_calls", "own_seconds", "cumulative_seconds"}


def test_profile_helpers_six_tiny_actions_complete_without_domain_shape(tmp_path):
    progress = initial_progress()
    destination = tmp_path / "progress.json"
    measurement = ProfileActions(progress, destination, cpu_started=time.process_time())

    def small_action():
        with measurement.span("candidate"):
            storage.canonical_bytes({"value": 1})
        with measurement.span("reconstruction"):
            pass
        measurement.before_cursor(None, None, "NOT RETAINED", (), None, False)
        measurement.after_cursor(None, None, "NOT RETAINED", (), None, False)
        with measurement.span("commit"):
            pass
        return {
            "raw_request_bytes": None,
            "logical_bytes": None,
            "history_bytes": None,
            "revisions": 0,
            "receipts": 0,
            "counts": [0, 0, 0, 0],
        }

    for ordinal, action in enumerate(
        ("create", "revise", "revise", "revise", "fresh_load", "exact_retry"), 1
    ):
        measurement.run(ordinal, action, small_action)
        saved = json.loads(destination.read_bytes())
        assert [row["ordinal"] for row in saved["records"]] == list(range(1, ordinal + 1))
        assert saved["active_ordinal"] is None
        assert saved["complete"] is (ordinal == 6)
    assert set(saved) == {"schema", "active_ordinal", "complete", "process_cpu_seconds", "records"}
    assert saved["process_cpu_seconds"] >= 0
    assert len(destination.read_bytes()) < 16384
    assert b"NOT RETAINED" not in destination.read_bytes()
    for row in saved["records"]:
        assert set(row) == {
            "ordinal",
            "action",
            "wall_seconds",
            "process_cpu_seconds",
            "candidate",
            "reconstruction",
            "commit",
            "sql",
            "functions",
            "raw_request_bytes",
            "logical_bytes",
            "history_bytes",
            "revisions",
            "receipts",
            "counts",
        }
        assert row["wall_seconds"] >= 0 and row["process_cpu_seconds"] >= 0
        for label in ("candidate", "reconstruction", "commit", "sql"):
            assert set(row[label]) == (
                {"calls", "seconds", "verbs"} if label == "sql" else {"calls", "seconds"}
            )
            assert row[label]["calls"] == 1 and row[label]["seconds"] >= 0
        assert row["sql"]["verbs"] == dict(SELECT=0, INSERT=0, UPDATE=0, DELETE=0, OTHER=1)
    prior = destination.read_bytes()
    with pytest.raises(AssertionError):
        measurement.run(7, "revise", small_action)
    assert destination.read_bytes() == prior


def test_profile_helpers_sql_verbs_are_closed_counts_without_statements(tmp_path):
    measurement = ProfileActions(initial_progress(), tmp_path / "unused.json", cpu_started=0)
    measurement.active = {
        "sql": {
            "calls": 0,
            "seconds": 0.0,
            "verbs": dict.fromkeys(("SELECT", "INSERT", "UPDATE", "DELETE", "OTHER"), 0),
        }
    }
    for statement in (
        " select private",
        "INSERT private",
        "UPDATE private",
        "DELETE private",
        "SAVEPOINT private",
        "",
    ):
        measurement.before_cursor(None, None, statement, None, None, False)
        measurement.after_cursor(None, None, statement, None, None, False)
    assert measurement.active["sql"]["calls"] == 6
    assert measurement.active["sql"]["verbs"] == dict(
        SELECT=1, INSERT=1, UPDATE=1, DELETE=1, OTHER=2
    )
    assert "private" not in json.dumps(measurement.active)
