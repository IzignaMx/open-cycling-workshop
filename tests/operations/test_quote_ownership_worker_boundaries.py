"""Mock-only runtime boundary coverage; no actual fd, process, proc read or DB."""

import io
from itertools import pairwise
from types import SimpleNamespace

import pytest
from test_quote_ownership_measurement import identity as identity

from scripts.ci import quote_ownership_database as database
from scripts.ci import quote_ownership_worker as worker


def owned_process(*, ticks=41, descendants=b""):
    process = object.__new__(worker.OwnedProcess)
    process.pidfd = 77
    process.process = {"pid": 123, "start_ticks": ticks, "pidfd_owned": True}
    process.child = SimpleNamespace(pid=123, poll=lambda: None)
    process.reaped = False
    process.stop_requested = False
    process.close_requested = False
    process.clock = lambda: 10
    return process


def mocked_proc(monkeypatch, *, ticks=41, descendants=b""):
    from pathlib import Path

    paths = []

    def opened(path, mode):
        paths.append(str(path))
        assert mode == "rb"
        if str(path).endswith("/stat"):
            return io.BytesIO(b"123 (comm (with) spaces) S " + b"0 " * 18 + str(ticks).encode())
        assert str(path) == "/proc/123/task/123/children"
        return io.BytesIO(descendants)

    monkeypatch.setattr(Path, "open", opened)
    return paths


@pytest.mark.parametrize("ticks,descendants", [(42, b""), (41, b"999"), (41, b" " + b"9" * 4096)])
def test_owned_process_refuses_changed_incarnation_or_descendants(monkeypatch, ticks, descendants):
    import signal

    paths = mocked_proc(monkeypatch, ticks=ticks, descendants=descendants)
    process = owned_process()
    signals = []
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *args: signals.append(args))
    with pytest.raises(worker.WorkerRefusal) as caught:
        process.stop(100)
    assert caught.value.code == "identity"
    assert not signals and paths


def test_pidfd_failure_keeps_registry_and_cleanup_never_falls_back_to_pid(monkeypatch, identity):
    import os
    import signal
    import subprocess

    child = SimpleNamespace(pid=123, stdin=None, stdout=None, poll=lambda: None)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(
        os, "pidfd_open", lambda *_: (_ for _ in ()).throw(OSError("synthetic pidfd"))
    )
    fallback = []
    monkeypatch.setattr(os, "kill", lambda *a: fallback.append(a))
    monkeypatch.setattr(os, "killpg", lambda *a: fallback.append(a))
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *a: fallback.append(a))
    runtime = worker.RuntimeAdapter(identity, None)
    runtime.now = lambda: 0
    with pytest.raises(OSError):
        runtime._spawn("child", "S", 100, 200)
    assert len(runtime.processes) == 1 and runtime.processes[0].child is child
    with pytest.raises(worker.WorkerRefusal) as caught:
        runtime.cleanup(None, [], 100)
    assert caught.value.code == "cleanup_unknown" and fallback == []


def test_late_stop_never_sends_signal(monkeypatch):
    import signal

    process = owned_process()
    process._verify = lambda: None
    process.clock = lambda: 100
    signals = []
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *a: signals.append(a))
    with pytest.raises(worker.WorkerRefusal):
        process.stop(100)
    assert not signals and not process.stop_requested


@pytest.mark.parametrize("fault", ["timeout", "late_return"])
def test_reap_has_no_extra_window_or_false_closed_receipt(monkeypatch, fault):
    import os
    import subprocess

    process = owned_process()
    clock = [10]
    process.clock = lambda: clock[0]
    waits = []
    closed = []

    def wait(*, timeout):
        waits.append(timeout)
        if fault == "timeout":
            raise subprocess.TimeoutExpired("fixed-child", timeout)
        clock[0] = 100
        return 0

    process.child.wait = wait
    process.child.stdin = SimpleNamespace(close=lambda: closed.append("stdin"))
    process.child.stdout = SimpleNamespace(close=lambda: closed.append("stdout"))
    monkeypatch.setattr(os, "close", lambda fd: closed.append(fd))
    with pytest.raises((subprocess.TimeoutExpired, worker.WorkerRefusal)):
        process.reap(100)
    assert waits == [90 / worker.SECOND]
    assert not process.reaped and process.pidfd == 77 and closed == []


class FakeChannel:
    def __init__(self, commands, clock=None):
        self.commands = iter(commands)
        self.clock = clock or (lambda: 1)
        self.events = []

    def send(self, event, case, payload, deadline):
        self.events.append(("send", event, case, payload, deadline))

    def receive(self, sender, deadline, **kwargs):
        self.events.append(("receive", sender, deadline))
        value = next(self.commands)
        if isinstance(value, Exception):
            raise value
        return value


def install_fake_observer(monkeypatch):
    raw = object()
    events = []
    monkeypatch.setattr(
        database, "open_observer", lambda clock, end: events.append(("open", end)) or raw
    )
    monkeypatch.setattr(
        database,
        "observe_absence",
        lambda conn, backend, clock, end: events.append(("observe", end)) or True,
    )
    monkeypatch.setattr(
        database, "close_observer", lambda conn, clock, end: events.append(("close", end))
    )
    return events


def test_observer_must_not_observe_before_begin(monkeypatch):
    events = install_fake_observer(monkeypatch)
    channel = FakeChannel(
        [
            {"event": "OBSERVE", "case": "H", "payload": {"backend": {}}},
            {"event": "CLOSE", "case": "teardown", "payload": {}},
        ]
    )
    with pytest.raises(worker.WorkerRefusal):
        worker._observer_main(channel, 65 * worker.SECOND)
    assert not any(e[0] == "observe" for e in events)


def test_observer_begin_uses_fixed_inherited_deadline_without_renewal(monkeypatch):
    events = install_fake_observer(monkeypatch)
    now = [5 * worker.SECOND]
    end = 20 * worker.SECOND
    channel = FakeChannel(
        [
            {"event": "BEGIN", "case": "setup", "payload": {"experiment_deadline_ns": end}},
            {"event": "OBSERVE", "case": "H", "payload": {"backend": {}}},
            {"event": "OBSERVE", "case": "S", "payload": {"backend": {}}},
            {"event": "CLOSE", "case": "teardown", "payload": {}},
        ],
        lambda: now[0],
    )
    assert worker._observer_main(channel, 65 * worker.SECOND) == 0
    assert events == [
        ("open", 65 * worker.SECOND),
        ("observe", end),
        ("observe", end),
        ("close", end),
    ]
    assert all(
        event[2] == end
        for event in channel.events
        if event[:2] == ("receive", "owner") and event[2] != 65 * worker.SECOND
    )


@pytest.mark.parametrize("end", [0, 1, 27 * worker.SECOND + 1])
def test_observer_rejects_expired_or_extended_begin(monkeypatch, end):
    events = install_fake_observer(monkeypatch)
    channel = FakeChannel(
        [{"event": "BEGIN", "case": "setup", "payload": {"experiment_deadline_ns": end}}]
    )
    with pytest.raises(worker.WorkerRefusal):
        worker._observer_main(channel, 65 * worker.SECOND)
    assert events == [("open", 65 * worker.SECOND)]


@pytest.mark.parametrize("close_fails", [False, True])
def test_child_h_only_claims_closed_after_successful_clean_close(monkeypatch, close_fails):
    closes = []

    def close(clock, end):
        closes.append(end)
        if close_fails:
            raise database.DatabaseRefusal()

    clean = SimpleNamespace(backend={"pid": 1}, close=close)
    monkeypatch.setattr(database, "open_clean_session", lambda clock, end: clean)
    channel = FakeChannel([{"event": "CLOSE", "case": "H", "payload": {}}])
    if close_fails:
        with pytest.raises(database.DatabaseRefusal):
            worker._child_main(channel, "H", 100, 100)
    else:
        assert worker._child_main(channel, "H", 100, 100) == 0
    assert closes == [100]
    sent = [e[1] for e in channel.events if e[0] == "send"]
    assert sent == (["READY"] if close_fails else ["READY", "CLOSED"])


def test_child_s_never_accepts_dispatch_or_returns_success(monkeypatch):
    closes = []
    clean = SimpleNamespace(backend={"pid": 1}, close=lambda *_: closes.append(True))
    monkeypatch.setattr(database, "open_clean_session", lambda clock, end: clean)
    channel = FakeChannel([{"event": "DISPATCH", "case": "S", "payload": {}}])
    with pytest.raises(worker.WorkerRefusal):
        worker._child_main(channel, "S", 100, 200)
    assert [e[1] for e in channel.events if e[0] == "send"] == ["READY"]
    # Failure delegates owned process cleanup; no false CLOSED frame.


def channel_without_real_fds(monkeypatch, identity, clock):
    import os

    monkeypatch.setattr(os, "set_blocking", lambda *_: None)
    return worker.PipeChannel(10, 11, identity, "owner", clock)


def test_pipe_oversized_prefix_refuses_before_body_read(monkeypatch, identity):
    channel = channel_without_real_fds(monkeypatch, identity, lambda: 0)
    calls = []

    def transfer(data, count, deadline):
        calls.append(count)
        assert count == 4
        return (4093).to_bytes(4, "big")

    channel._transfer = transfer
    with pytest.raises(worker.WorkerRefusal):
        channel.receive("child", 100, case="H")
    assert calls == [4]


@pytest.mark.parametrize("direction", ["read", "write"])
def test_pipe_syscall_eintr_keeps_remaining_budget(monkeypatch, identity, direction):
    import os
    import select

    clock = [0]
    timeouts = []
    calls = []
    channel = channel_without_real_fds(monkeypatch, identity, lambda: clock[0])

    def selected(reads, writes, errors, timeout):
        timeouts.append(timeout)
        return reads, writes, []

    def transfer(*args):
        calls.append(args)
        clock[0] += 10
        if len(calls) == 1:
            raise InterruptedError()
        return b"x" if direction == "read" else 1

    monkeypatch.setattr(select, "select", selected)
    monkeypatch.setattr(os, "read" if direction == "read" else "write", transfer)
    assert channel._transfer(None if direction == "read" else b"x", 1, 100) == (
        b"x" if direction == "read" else b""
    )
    assert timeouts == [100 / worker.SECOND, 90 / worker.SECOND]


def test_pipe_negative_clock_refuses_before_any_io(monkeypatch, identity):
    import os
    import select

    calls = []
    channel = channel_without_real_fds(monkeypatch, identity, lambda: -1)
    monkeypatch.setattr(select, "select", lambda *_: calls.append("select") or ([10], [], []))
    monkeypatch.setattr(os, "read", lambda *_: calls.append("read") or b"x")
    with pytest.raises(worker.WorkerRefusal):
        channel._transfer(None, 1, 100)
    assert calls == []


def test_observer_requires_h_before_first_s(monkeypatch):
    events = install_fake_observer(monkeypatch)
    end = 20 * worker.SECOND
    channel = FakeChannel(
        [
            {"event": "BEGIN", "case": "setup", "payload": {"experiment_deadline_ns": end}},
            {"event": "OBSERVE", "case": "S", "payload": {"backend": {}}},
            {"event": "CLOSE", "case": "teardown", "payload": {}},
        ]
    )
    with pytest.raises(worker.WorkerRefusal):
        worker._observer_main(channel, 65 * worker.SECOND)
    assert not any(event[0] == "observe" for event in events)


@pytest.mark.parametrize(
    "role,case,stopped,returncode",
    [
        ("child", "H", False, 1),
        ("child", "H", False, -9),
        ("observer", "setup", False, 1),
        ("observer", "setup", False, -9),
        ("child", "S", True, 0),
        ("child", "S", True, -15),
    ],
)
def test_reap_refuses_exit_that_does_not_match_clean_close_or_owned_stop(
    monkeypatch, role, case, stopped, returncode
):
    import os

    process = owned_process()
    process.role = role
    process.case = case
    process.stop_requested = stopped
    process.close_requested = not stopped
    process.child.returncode = returncode
    process.child.wait = lambda **kwargs: returncode
    process.child.stdin = SimpleNamespace(close=lambda: None)
    process.child.stdout = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(os, "close", lambda fd: None)
    with pytest.raises(worker.WorkerRefusal):
        process.reap(100)


def test_owner_absence_polls_share_global_spacing_across_h_and_s(identity):
    from test_quote_ownership_worker import FakeObserver, FakeRuntime

    polls = []

    class Observed(FakeObserver):
        def absent(self, backend, deadline):
            polls.append(self.runtime.now())
            return super().absent(backend, deadline)

    class Runtime(FakeRuntime):
        def reserve(self, deadline):
            self.time += 1
            return Observed(self)

    result = worker.run_owner(Runtime(), identity, 65 * worker.SECOND)
    assert result["status"] == "observed"
    assert len(polls) == 4
    assert all(later - earlier >= 50_000_000 for earlier, later in pairwise(polls))


def test_stop_never_signals_when_captured_request_time_is_late(monkeypatch):
    import signal

    process = owned_process()
    process._verify = lambda: None
    times = iter([99, 100])
    process.clock = lambda: next(times)
    signals = []
    monkeypatch.setattr(signal, "pidfd_send_signal", lambda *args: signals.append(args))
    try:
        requested = process.stop(100)
    except worker.WorkerRefusal:
        assert signals == []
    else:
        # A single captured/check timestamp is also valid: no claim about later
        # OS delivery. But a captured timestamp known to be late cannot authorize.
        assert requested < 100
        assert signals == [(77, signal.SIGKILL, None, 0)]


@pytest.mark.parametrize("failed_close", ["stdin", "stdout", "pidfd"])
def test_reap_close_failure_still_attempts_other_owned_descriptors(monkeypatch, failed_close):
    import os

    process = owned_process()
    process.role = "child"
    process.case = "H"
    process.close_requested = True
    process.child.returncode = 0
    process.child.wait = lambda **kwargs: 0
    closes = []

    def close(name):
        closes.append(name)
        if failed_close == name:
            raise OSError("synthetic close refusal")

    process.child.stdin = SimpleNamespace(close=lambda: close("stdin"))
    process.child.stdout = SimpleNamespace(close=lambda: close("stdout"))
    monkeypatch.setattr(os, "close", lambda fd: close("pidfd"))
    with pytest.raises((OSError, worker.WorkerRefusal)):
        process.reap(100)
    assert closes == ["stdin", "stdout", "pidfd"]
    assert process.os_reaped is True
    assert process.reap_failed is True and process.descriptors_disposed is False
    assert process.pidfd is None  # Ambiguous numeric close must never be retried.
    assert process.close_attempted == {"stdin", "stdout", "pidfd"}
    with pytest.raises(worker.WorkerRefusal):
        process.reap(100)
    assert closes == ["stdin", "stdout", "pidfd"]
