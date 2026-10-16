"""Tiny state/deadline tests. No quote specimen or Docker execution."""

import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/ci/quote_capacity_micro.py"
spec = importlib.util.spec_from_file_location("online_guard", PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def state(n, phase):
    return json.dumps(dict(ordinal=n, state=phase))


def test_fixed_handshake_never_refreshes_operation_deadline():
    gate = m.OnlineGate(100, 0)
    assert gate.observe(state(0, "bootstrap"), 1) is None
    assert gate.observe(state(1, "ready"), 2) == "grant:1"
    assert gate.deadline == 22
    assert gate.observe(state(1, "ready"), 10) is None
    assert gate.deadline == 22
    assert gate.observe(state(1, "done"), 21) == "ack:1"
    assert gate.observe(state(1, "done"), 22) is None
    assert gate.observe(state(2, "ready"), 23) == "grant:2"
    assert gate.deadline == 43


@pytest.mark.parametrize(
    "raw",
    [state(2, "ready"), state(1, "done"), state(True, "ready"), "{}", "null", state(1, "other")],
)
def test_bad_initial_handshake_is_closed(raw):
    with pytest.raises(m.ProofFailure):
        m.OnlineGate(100, 0).observe(raw, 1)


def test_deadline_covers_grant_command_and_late_success():
    gate = m.OnlineGate(100, 0)
    gate.observe(state(1, "ready"), 1)
    with pytest.raises(m.ProofFailure):
        gate.observe(state(1, "done"), 21)


def test_bootstrap_and_gaps_cannot_hang():
    gate = m.OnlineGate(100, 0)
    with pytest.raises(m.ProofFailure):
        gate.observe(state(0, "bootstrap"), 20)
    gate = m.OnlineGate(100, 0)
    gate.observe(state(1, "ready"), 1)
    gate.observe(state(1, "done"), 2)
    with pytest.raises(m.ProofFailure):
        gate.observe(state(1, "done"), 22)


def test_exact39_ordinals_and_no_replayed_completed_state():
    gate = m.OnlineGate(100, 0)
    for n in range(1, 40):
        assert gate.observe(state(n, "ready"), n) == f"grant:{n}"
        assert gate.observe(state(n, "done"), n + 0.1) == f"ack:{n}"
    assert gate.complete
    with pytest.raises(m.ProofFailure):
        gate.observe(state(39, "ready"), 40)


def test_aggregate_deadline_caps_last_operation():
    gate = m.OnlineGate(10, 0)
    gate.observe(state(1, "ready"), 9)
    assert gate.deadline == 10
    with pytest.raises(m.ProofFailure):
        gate.observe(state(1, "done"), 10)


def evidence():
    return dict(
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
        operation_seconds=[0.1] * 39,
        process_cpu_seconds=1.0,
        record_bytes=[100] * 33,
        history_bytes=3334,
        raw_request_bytes=[100] * 33,
        revision33_rejected=True,
        exact_retries=3,
    )


def test_online_closed_result_and_framing():
    assert m.online_result(json.dumps(evidence()))["history_bytes"] == 3334


@pytest.mark.parametrize(
    "key,value",
    [
        ("record_bytes", [262145] * 33),
        ("history_bytes", 3335),
        ("operation_seconds", [20] * 39),
        ("new_operations", 34),
        ("raw_request_bytes", [131073] * 33),
        ("service_order_state", "AUTHORIZED"),
        ("exact_retries", 2),
    ],
)
def test_online_invalid_results_reject(key, value):
    body = evidence()
    body[key] = value
    with pytest.raises(m.ProofFailure):
        m.online_result(json.dumps(body))


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "setup_deadline",
        "grant_deadline",
        "zero_exit_late",
        "cleanup",
        "stop_failed",
        "aggregate",
        "finalization",
    ],
)
def test_host_deadlines_stop_work_and_cleanup_exact_owned(tmp_path, monkeypatch, fault):
    from types import SimpleNamespace

    now = [0.0]
    pending = [state(n, phase) for n in range(1, 40) for phase in ("ready", "done")]
    containers = []
    actions = []
    spawned = []
    removed = []
    timeouts = []
    killed = []
    monkeypatch.setattr(m.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(m.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(m.signal, "signal", lambda *args: None)
    monkeypatch.setattr(m.os, "killpg", lambda *args: killed.append(args))
    monkeypatch.setattr(
        m,
        "source_query",
        lambda kind, execute: "c" * 40 if kind == "head" else "d" * 40 if kind == "tree" else "",
    )
    monkeypatch.setattr(m, "inspect_owned", lambda *args: None)
    monkeypatch.setattr(m, "effective_privileges", lambda *args: {"uid": 10001})
    monkeypatch.setattr(
        m, "parse_probe", lambda *args: {"cpu_usec": 2_000_000, "memory_peak": 1000}
    )

    def reconcile(*args):
        actions.append("reconcile")
        if fault == "finalization":
            now[0] += 21
        return list(containers)

    monkeypatch.setattr(m, "reconcile_owned", reconcile)

    def canary(cid, execute):
        containers.remove(cid)
        return dict(cpu_usec=2_000_000, memory_peak=1000)

    monkeypatch.setattr(m, "cancellation_canary", canary)

    def fake_run(args, *, timeout=5):
        assert 0 < timeout <= 10
        timeouts.append(timeout)
        now[0] += 0.001
        if args[:3] == ["docker", "image", "inspect"]:
            return "d" * 40 if "ocwp.source-tree" in args[4] else "sha256:" + "e" * 64
        if args[1] == "create":
            cid = str(len(containers) + 1) * 64
            containers.append(cid)
            Path(args[args.index("--cidfile") + 1]).write_text(cid)
            if fault == "setup_deadline":
                now[0] = 21
            return cid
        if args[1] == "exec" and args[-1] == "/tmp/quote-online-state.json":
            if fault == "aggregate":
                now[0] += 2
            return pending.pop(0)
        if args[1] == "exec" and args[-1] == "/tmp/quote-micro-result.json":
            return json.dumps(evidence())
        if (
            args[1] == "exec"
            and "grant:1" in args[-1]
            and fault in {"grant_deadline", "stop_failed"}
        ):
            now[0] += 20
        if args[1] == "kill":
            actions.append("kill")
            if fault == "stop_failed":
                raise m.ProofFailure("command_timeout")
        if args[1] == "inspect":
            return "false"
        if args[1] == "rm":
            if fault == "cleanup":
                raise m.ProofFailure("cleanup_failed")
            removed.append(args[-1])
            containers.remove(args[-1])
        if args[1] == "ps":
            return "\n".join(containers)
        return ""

    monkeypatch.setattr(m, "run", fake_run)

    def popen(*args, **kwargs):
        spawned.append(1)

        def poll():
            if fault == "zero_exit_late":
                now[0] = 101
                return 0
            return None if pending else 0

        return SimpleNamespace(poll=poll, returncode=0, pid=999, wait=lambda **kw: None)

    monkeypatch.setattr(m.subprocess, "Popen", popen)
    output = tmp_path / "result.json"
    args = ("worker", "pg", "c" * 40, output, tmp_path / "owned.json")
    if fault == "none":
        m.supervise(*args, online_once=True)
    else:
        with pytest.raises(m.ProofFailure):
            m.supervise(*args, online_once=True)
    result = json.loads(output.read_text())
    assert result["status"] == ("micro_passed_not_capacity" if fault == "none" else "failed")
    assert result["cleanup"] == (
        "failed" if fault in {"cleanup", "finalization"} else "verified_absent"
    )
    assert len(spawned) == (0 if fault == "setup_deadline" else 1)
    if fault not in {"cleanup", "finalization"}:
        assert not containers
    if fault == "grant_deadline":
        assert killed and result["online_progress"]["ordinal"] == 1
    if fault in {"grant_deadline", "zero_exit_late", "stop_failed", "aggregate"}:
        assert actions[:2] == ["kill", "kill"]
        assert result["workload_stop"] == (
            "failed_or_unverified" if fault == "stop_failed" else "verified_not_running"
        )
    if fault == "none":
        assert len(result["host_operation_seconds"]) == 39
    if fault == "aggregate":
        assert result["elapsed_seconds"] < 85


def test_dedicated_trigger_is_single_opened_run_and_single_job():
    source = (PATH.parents[2] / ".github/workflows/quote-online-once-20261016.yml").read_text()
    assert "types: [opened]" in source
    assert "github.run_number == '1' && github.run_attempt == '1'" in source
    assert "github.head_ref == 'codex/quote-online-once-20261016'" in source
    assert "github.event.pull_request.head.repo.full_name == github.repository" in source
    assert "github.repository == 'IzignaMx/open-cycling-workshop'" in source
    assert source.count("    runs-on:") == 1
    assert "--online-once" in source
    assert all(
        word not in source
        for word in (
            "workflow_dispatch:",
            "schedule:",
            "push:",
            "matrix:",
            "synchronize",
            "reopened",
        )
    )


def test_whole_job_and_preparation_deadlines_are_explicit():
    source = (PATH.parents[2] / ".github/workflows/quote-online-once-20261016.yml").read_text()
    assert "    timeout-minutes: 15" in source
    assert "        timeout-minutes: 9" in source
    assert source.count("--kill-after=5s 210s docker build") == 2
    assert "--kill-after=5s 60s docker pull" in source
    assert "--kill-after=30s 120s python3" in source
    assert "timeout-minutes: 20" not in source
    assert "timeout-minutes: 12" not in source
