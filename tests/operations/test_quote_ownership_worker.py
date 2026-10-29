"""Fake runtime choreography only; never spawn/stop children or connect to a DB."""

import pytest
from test_quote_ownership_measurement import identity as identity

from scripts.ci.quote_ownership_worker import WorkerRefusal, run_owner


class FakeProcess:
    def __init__(self, runtime, case):
        self.runtime, self.case = runtime, case
        self.process = {"pid": 101 if case == "H" else 102, "start_ticks": 50, "pidfd_owned": True}
        self.backend = {
            "pid": 201 if case == "H" else 202,
            "start_us": 51,
            "database": "synthetic",
            "role": "mock_pending_role",
        }

    def ready(self, deadline):
        self.runtime.events.append((self.case, "ready", deadline))
        self.runtime.time += self.runtime.ready_delay
        return self.backend

    def request_close(self, deadline):
        self.runtime.events.append((self.case, "close", deadline))
        return self.runtime.time

    def stop(self, deadline):
        self.runtime.events.append((self.case, "stop", self.runtime.time, deadline))
        return self.runtime.time

    def reap(self, deadline):
        self.runtime.events.append((self.case, "reap", deadline))
        self.runtime.time += 1


class FakeObserver:
    def __init__(self, runtime):
        self.runtime = runtime
        self.process = {"pid": 90, "start_ticks": 40, "pidfd_owned": True}
        self.seen = {}

    def bind(self, case, backend):
        self.runtime.events.append((case, "bind"))

    def absent(self, backend, deadline):
        pid = backend["pid"]
        self.seen[pid] = self.seen.get(pid, 0) + 1
        return self.seen[pid] > 1

    def close(self, deadline):
        self.runtime.events.append(("observer", "close", deadline))
        self.runtime.time += 2
        return self.runtime.time - 1, self.runtime.time


class FakeRuntime:
    def __init__(self, *, setup_delay=1, ready_delay=1, duplicate_go=False):
        self.time = 0
        self.setup_delay, self.ready_delay = setup_delay, ready_delay
        self.events = []
        self.duplicate_go = duplicate_go

    def now(self):
        return self.time

    def reserve(self, deadline):
        self.events.append(("reserve", deadline))
        self.time += self.setup_delay
        return FakeObserver(self)

    def reserved(self, deadline):
        self.events.append(("reserved", deadline))

    def go(self, deadline):
        self.events.append(("go", deadline))
        return self.time

    def spawn(self, case, deadline):
        self.events.append((case, "spawn", self.time, deadline))
        return FakeProcess(self, case)

    def wait_until(self, target, deadline):
        assert target <= deadline
        self.time = max(self.time, target)

    def cleanup(self, observer, children, deadline):
        self.events.append(("failure_cleanup", deadline))


def test_fake_owner_two_cases_and_reserved_observer_inside_original_budget(identity):
    runtime = FakeRuntime()
    result = run_owner(runtime, identity, 65_000_000_000)
    assert result["status"] == "observed"
    assert [x[:2] for x in runtime.events if len(x) >= 2 and x[1] == "spawn"] == [
        ("H", "spawn"),
        ("S", "spawn"),
    ]
    assert [x[0] for x in runtime.events[:3]] == ["reserve", "reserved", "go"]
    assert result["observer"]["reaped"] is True
    assert result["elapsed_ns"] <= 26_000_000_000
    assert result["cases"][1]["stop_ns"] == result["cases"][1]["start_ns"] + 8_000_000_000
    assert all(case["read_only"] and case["same_backend"] for case in result["cases"])


@pytest.mark.parametrize(
    "setup_delay,ready_delay,expected_spawn",
    [
        (65_000_000_001, 1, []),
        (1, 8_000_000_001, ["H"]),
    ],
)
def test_fake_owner_failure_never_admits_another_case(
    identity, setup_delay, ready_delay, expected_spawn
):
    runtime = FakeRuntime(setup_delay=setup_delay, ready_delay=ready_delay)
    result = run_owner(runtime, identity, 65_000_000_000)
    assert result["status"] == "failed"
    assert [e[0] for e in runtime.events if len(e) > 1 and e[1] == "spawn"] == expected_spawn
    assert result["cases"][1]["status"] == "skipped"
    assert any(e[0] == "failure_cleanup" for e in runtime.events)


def test_process_launch_is_fixed_and_does_not_inherit_unlisted_descriptors(identity):
    from scripts.ci.quote_ownership_worker import launch_spec

    args, env = launch_spec("child", "H", identity, 100, 200)
    assert args[-4:] == ["--role", "child", "--case", "H"]
    assert "OCWP_DATABASE_URL" not in env
    assert "PGPASSWORD" not in env
    assert env["OCWP_OWNERSHIP_CASE_DEADLINE_NS"] == "100"
    with pytest.raises(WorkerRefusal):
        launch_spec("arbitrary-module", "H", identity, 100, 200)


def test_pipe_read_interruption_keeps_original_deadline(monkeypatch, identity):
    import os
    import select

    from scripts.ci.quote_ownership_worker import PipeChannel

    monkeypatch.setattr(os, "set_blocking", lambda *_: None)
    channel = PipeChannel(10, 11, identity, "owner", lambda: 1)
    calls = []

    def ready(*args):
        calls.append(args[-1])
        if len(calls) == 1:
            raise InterruptedError()
        return [10], [], []

    monkeypatch.setattr(select, "select", ready)
    monkeypatch.setattr(os, "read", lambda *_: b"x")
    assert channel._transfer(None, 1, 100) == b"x"
    assert calls == [99 / 1_000_000_000] * 2


def test_spawn_retains_handle_before_fallible_pipe_setup(monkeypatch, identity):
    import os
    import subprocess

    from scripts.ci.quote_ownership_worker import RuntimeAdapter

    class Pipe:
        def fileno(self):
            return 99

    class Child:
        pid = 123
        stdin = Pipe()
        stdout = Pipe()

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: Child())
    monkeypatch.setattr(os, "set_blocking", lambda *_: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(os, "pidfd_open", lambda *_: (_ for _ in ()).throw(OSError()))
    runtime = RuntimeAdapter(identity, None)
    with pytest.raises(OSError):
        runtime._spawn("child", "H", 100, 100)
    assert len(runtime.processes) == 1
    assert runtime.processes[0].child.pid == 123


@pytest.mark.parametrize("chunks", [[b"a", b"bc"], [b"", b"abc"]])
def test_pipe_partial_reads_or_eof_are_bounded(monkeypatch, identity, chunks):
    import os
    import select

    from scripts.ci.quote_ownership_worker import PipeChannel

    monkeypatch.setattr(os, "set_blocking", lambda *_: None)
    monkeypatch.setattr(select, "select", lambda *_: ([10], [], []))
    values = iter(chunks)
    monkeypatch.setattr(os, "read", lambda *_: next(values))
    channel = PipeChannel(10, 11, identity, "owner", lambda: 0)
    if chunks[0]:
        assert channel._transfer(None, 3, 100) == b"abc"
    else:
        with pytest.raises(WorkerRefusal):
            channel._transfer(None, 3, 100)


def test_pipe_partial_write_and_late_clock(monkeypatch, identity):
    import os
    import select

    from scripts.ci.quote_ownership_worker import PipeChannel

    monkeypatch.setattr(os, "set_blocking", lambda *_: None)
    monkeypatch.setattr(select, "select", lambda *_: ([], [11], []))
    writes = []
    monkeypatch.setattr(os, "write", lambda fd, data: writes.append((fd, data)) or 1)
    channel = PipeChannel(10, 11, identity, "owner", lambda: 0)
    channel._transfer(b"abc", 3, 100)
    assert writes == [(11, b"abc"), (11, b"bc"), (11, b"c")]
    channel.clock = lambda: 100
    with pytest.raises(WorkerRefusal):
        channel._transfer(b"x", 1, 100)


def test_pidfd_stop_uses_exact_retained_handle_not_pid(monkeypatch):
    import signal

    from scripts.ci.quote_ownership_worker import OwnedProcess

    process = object.__new__(OwnedProcess)
    process.pidfd = 77
    process.clock = lambda: 10
    process.stop_requested = False
    process._verify = lambda: None
    calls = []
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *args: calls.append(args))
    assert process.stop(100) == 10
    assert calls == [(77, signal.SIGKILL, None, 0)]
    with pytest.raises(WorkerRefusal):
        process.stop(100)
    assert len(calls) == 1


def test_reaped_process_still_closes_every_owned_descriptor_after_first_close_failure(monkeypatch):
    import os
    from types import SimpleNamespace

    from scripts.ci.quote_ownership_worker import OwnedProcess

    calls = []

    def bad_close():
        calls.append("stdin")
        raise OSError("synthetic close")

    process = object.__new__(OwnedProcess)
    process.role, process.case = "child", "H"
    process.pidfd, process.reaped, process.stop_requested = 77, False, False
    process.close_requested = True
    process.clock = lambda: 1
    process.child = SimpleNamespace(
        wait=lambda **kwargs: 0,
        returncode=0,
        stdin=SimpleNamespace(close=bad_close),
        stdout=SimpleNamespace(close=lambda: calls.append("stdout")),
    )
    monkeypatch.setattr(os, "close", lambda fd: calls.append(fd))
    with pytest.raises(WorkerRefusal):
        process.reap(100)
    assert calls == ["stdin", "stdout", 77]
    with pytest.raises(WorkerRefusal):
        process.reap(100)
    assert calls == ["stdin", "stdout", 77]
