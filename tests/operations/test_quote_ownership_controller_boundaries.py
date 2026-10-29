"""Mock-only host resource/deadline boundaries; no Docker/process/DB actions."""

import pytest

from scripts.ci import quote_ownership_measurement as controller
from scripts.ci.quote_ownership_worker import WorkerRefusal


def probe(role, *, peak=8192, count=5, pressure=0):
    memory, pids = controller.containment.full_role_limits(role)
    values = [
        str(memory * 1024**2),
        "0",
        "100000 100000",
        str(pids),
        "4096",
        str(peak),
        "usage_usec 100\nuser_usec 80\nsystem_usec 20",
        f"oom 0\noom_kill 0\nmax {pressure}",
        "max 0",
    ]
    return (
        "0::/"
        + "".join(
            f"\n---{key}---\n{value}"
            for key, value in zip(controller.containment.FIELDS, values, strict=True)
        )
        + f"\n---ownership-pids---\n{count}"
    )


def host():
    runtime = object.__new__(controller.HostRuntime)
    runtime.containers = {"worker": "a" * 64, "db": "b" * 64}
    runtime.resources = dict.fromkeys(
        (
            "worker_peak_bytes",
            "pg_peak_bytes",
            "worker_processes",
            "pg_processes",
            "pressure_events",
        ),
        0,
    )
    return runtime


def test_sample_preserves_cumulative_memory_peak_and_sampled_process_maxima():
    runtime = host()
    values = {"peak": 16384, "count": 7}
    calls = []

    def execute(args):
        calls.append(args)
        role = "worker" if args[2] == runtime.containers["worker"] else "db"
        return probe(role, **values)

    runtime.client = lambda deadline: execute
    runtime.sample(100)
    values.update(peak=8192, count=5)
    runtime.sample(100)
    assert runtime.resources == {
        "worker_peak_bytes": 16384,
        "pg_peak_bytes": 16384,
        "worker_processes": 7,
        "pg_processes": 7,
        "pressure_events": 0,
    }
    assert len(calls) == 4
    assert all(args[:2] == ["docker", "exec"] for args in calls)
    assert all("pids.current" in args[-1] for args in calls)
    # Process values are sampled maxima, not a claim of kernel pids.peak.


@pytest.mark.parametrize(
    "fault",
    ["memory_pressure", "pids_pressure", "count_limit", "zero_count", "malformed", "duplicate"],
)
def test_sample_refuses_pressure_unknown_or_invalid_process_counts(fault):
    runtime = host()

    def execute(args):
        role = "worker" if args[2] == runtime.containers["worker"] else "db"
        value = probe(
            role,
            pressure=1 if fault == "memory_pressure" else 0,
            count=999 if fault == "count_limit" else 0 if fault == "zero_count" else 5,
        )
        if fault == "pids_pressure":
            value = value.replace("---pids.events---\nmax 0", "---pids.events---\nmax 1")
        if fault == "malformed":
            value = "invalid"
        if fault == "duplicate":
            value += "\n---ownership-pids---\n5"
        return value

    runtime.client = lambda deadline: execute
    with pytest.raises((WorkerRefusal, controller.containment.ProofFailure)):
        runtime.sample(100)


@pytest.mark.parametrize(
    "role,remaining,requested,expected",
    [
        ("canary", 65, 15, 15),
        ("worker", 65, 15, 5),
        ("db", 65, 15, 5),
        ("canary", 2, 15, 2),
        ("worker", 2, 5, 2),
    ],
)
def test_client_caps_are_clipped_to_original_remaining_time(
    monkeypatch, role, remaining, requested, expected
):
    runtime = host()
    runtime.now = lambda: 0
    calls = []
    monkeypatch.setattr(
        controller.containment,
        "full_client",
        lambda args, **kwargs: calls.append((args, kwargs["timeout"])) or "ok",
    )
    args = ["docker", "create", "--name", f"ocwp-quote-token-{role}"]
    assert runtime.client(remaining * controller.SECOND)(args, timeout=requested) == "ok"
    assert calls == [(args, expected)]


@pytest.mark.parametrize("expired_before", [True, False])
def test_client_expiry_never_renews_deadline_or_accepts_late_result(monkeypatch, expired_before):
    runtime = host()
    times = iter([100] if expired_before else [0, 100])
    runtime.now = lambda: next(times)
    calls = []
    monkeypatch.setattr(
        controller.containment, "full_client", lambda *a, **k: calls.append(k) or "late"
    )
    with pytest.raises(WorkerRefusal):
        runtime.client(100)(["docker", "inspect", "a" * 64])
    assert len(calls) == (0 if expired_before else 1)
    if calls:
        assert calls[0]["timeout"] == 100 / controller.SECOND
