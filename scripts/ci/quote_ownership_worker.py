"""Fixed one-shot owner/child/observer. Imports never start runtime work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from scripts.ci.quote_ownership_evidence import CODES, SECOND, validate_observation


class WorkerRefusal(RuntimeError):
    def __init__(self, code: str = "protocol") -> None:
        self.code = code if code in CODES else "protocol"
        super().__init__("ownership_worker_refused")


def _within(adapter: Any, deadline: int, code: str = "case_deadline") -> None:
    if adapter.now() >= deadline:
        raise WorkerRefusal(code)


def _empty_case(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
        "backend": None,
        "process": None,
        **dict.fromkeys(("start_ns", "ready_ns", "stop_ns", "reaped_ns", "absent_ns")),
        **dict.fromkeys(("read_only", "clean_session", "same_backend"), False),
    }


def run_owner(adapter: Any, identity: dict[str, object], setup_deadline_ns: int) -> dict[str, Any]:
    """Concrete finite choreography; tests supply only fake process/clock adapters."""
    started = setup_deadline_ns - 65 * SECOND
    observer_info: dict[str, Any] = {
        **dict.fromkeys(("reserved", "read_only", "transaction_idle", "closed", "reaped"), False),
        "process": None,
        "reserved_setup_ns": None,
        "closed_ns": None,
        "reaped_ns": None,
    }
    result: dict[str, Any] = {
        "status": "failed",
        "failure": "protocol",
        "setup_ns": 0,
        "elapsed_ns": 0,
        "observer": observer_info,
        "cases": [_empty_case("H"), _empty_case("S")],
    }
    observer: Any = None
    children = []
    go = None
    end = setup_deadline_ns
    current = None
    last_poll: int | None = None

    def absent(backend: dict[str, Any], deadline: int) -> bool:
        nonlocal last_poll
        if last_poll is not None:
            adapter.wait_until(last_poll + 50_000_000, deadline)
        _within(adapter, deadline)
        last_poll = adapter.now()
        return bool(observer.absent(backend, deadline))

    try:
        _within(adapter, setup_deadline_ns, "setup_deadline")
        observer = adapter.reserve(setup_deadline_ns)
        observer_info["process"] = dict(observer.process)
        _within(adapter, setup_deadline_ns, "setup_deadline")
        observer_info.update(
            reserved=True,
            read_only=True,
            transaction_idle=True,
            reserved_setup_ns=adapter.now() - started,
        )
        adapter.reserved(setup_deadline_ns)
        go = adapter.go(setup_deadline_ns)
        _within(adapter, setup_deadline_ns, "setup_deadline")
        end = go + 26 * SECOND
        result["setup_ns"] = go - started
        for current in result["cases"]:
            _within(adapter, end, "experiment_deadline")
            t0 = adapter.now()
            deadline = t0 + 8 * SECOND
            case_end = min(end, deadline + (5 * SECOND if current["name"] == "S" else 0))
            current.update(status="failed", start_ns=t0 - go)
            child = adapter.spawn(current["name"], min(end, deadline))
            children.append(child)
            current["process"] = dict(child.process)
            current["backend"] = child.ready(min(end, deadline))
            _within(adapter, min(end, deadline))
            current.update(
                ready_ns=adapter.now() - go, read_only=True, clean_session=True, same_backend=True
            )
            observer.bind(current["name"], current["backend"])
            # Fresh same-role presence binds the named backend before any close/stop.
            if absent(current["backend"], min(end, deadline)):
                raise WorkerRefusal("identity")
            _within(adapter, min(end, deadline))
            if current["name"] == "H":
                current["stop_ns"] = child.request_close(case_end) - go
            else:
                adapter.wait_until(deadline, end)
                _within(adapter, case_end)
                current["stop_ns"] = child.stop(case_end) - go
            child.reap(case_end)
            _within(adapter, case_end)
            current["reaped_ns"] = adapter.now() - go
            for _ in range(255):  # One presence query already consumed the 256-query ceiling.
                _within(adapter, case_end)
                if absent(current["backend"], case_end):
                    current["absent_ns"] = adapter.now() - go
                    break
                adapter.wait_until(min(case_end, adapter.now() + 50_000_000), case_end)
            if current["absent_ns"] is None:
                raise WorkerRefusal("observer_unknown")
            _within(adapter, case_end)
            current["status"] = "passed"
        closed, reaped = observer.close(end)
        _within(adapter, end, "experiment_deadline")
        observer_info.update(closed=True, reaped=True, closed_ns=closed - go, reaped_ns=reaped - go)
        result.update(status="observed", failure=None, elapsed_ns=adapter.now() - go)
        validate_observation(result, identity)
    except Exception as error:
        result["status"] = "failed"
        result["failure"] = error.code if isinstance(error, WorkerRefusal) else "protocol"
        if current is not None and current["status"] != "passed":
            current["status"] = "failed"
        result["setup_ns"] = max(0, (go if go is not None else adapter.now()) - started)
        result["elapsed_ns"] = max(0, adapter.now() - go) if go is not None else 0
        # Cleanup cannot upgrade observation failure or acquire another window.
        try:
            adapter.cleanup(observer, children, end)
        except Exception:
            result["failure"] = "cleanup_unknown"
    return result


# Runtime adapters below are inert until explicitly constructed by contained main.
def launch_spec(
    role: str, case: str, identity: dict[str, object], deadline: int, wait_deadline: int
) -> tuple[list[str], dict[str, str]]:
    import json
    import sys

    if (role, case) not in (("child", "H"), ("child", "S"), ("observer", "setup")):
        raise WorkerRefusal()
    return (
        [sys.executable, "-m", "scripts.ci.quote_ownership_worker", "--role", role, "--case", case],
        {
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp/ocwp-tests",
            "TMPDIR": "/tmp/ocwp-tests",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "OCWP_OWNERSHIP_CONTAINED": "1",
            "OCWP_OWNERSHIP_IDENTITY": json.dumps(identity),
            "OCWP_OWNERSHIP_CASE_DEADLINE_NS": str(deadline),
            "OCWP_OWNERSHIP_WAIT_DEADLINE_NS": str(wait_deadline),
        },
    )


class PipeChannel:
    """Bounded framing on already-owned descriptors; never opens another channel."""

    def __init__(
        self,
        read_fd: int,
        write_fd: int,
        identity: dict[str, object],
        sender: str,
        clock: Callable[[], int] | None = None,
    ) -> None:
        import os
        import time

        self.read_fd, self.write_fd, self.identity, self.sender = (
            read_fd,
            write_fd,
            identity,
            sender,
        )
        self.clock = clock or time.monotonic_ns
        self.sent: dict[str, int] = {}
        self.streams: dict[tuple[str, str], Any] = {}
        os.set_blocking(read_fd, False)
        os.set_blocking(write_fd, False)

    def _transfer(self, data: bytes | None, count: int, deadline: int) -> bytes:
        import os
        import select

        result = bytearray()
        offset = 0
        for _ in range(8192):
            now = self.clock()
            if type(now) is not int or now < 0 or type(deadline) is not int:
                raise WorkerRefusal("protocol")
            remaining = deadline - now
            if remaining <= 0:
                raise WorkerRefusal("case_deadline")
            try:
                readable, writable, _ = select.select(
                    [self.read_fd] if data is None else [],
                    [self.write_fd] if data is not None else [],
                    [],
                    remaining / SECOND,
                )
            except InterruptedError:
                continue
            try:
                if data is None and readable:
                    chunk = os.read(self.read_fd, count - offset)
                    if not chunk:
                        raise WorkerRefusal("protocol")
                    result.extend(chunk)
                    offset += len(chunk)
                elif data is not None and writable:
                    written = os.write(self.write_fd, data[offset:])
                    if written <= 0:
                        raise WorkerRefusal("protocol")
                    offset += written
            except (BlockingIOError, InterruptedError):
                continue
            if offset == count:
                if self.clock() >= deadline:
                    raise WorkerRefusal("case_deadline")
                return bytes(result)
        raise WorkerRefusal("protocol")

    def send(self, event: str, case: str, payload: dict[str, Any], deadline: int) -> None:
        import json

        from scripts.ci.quote_ownership_evidence import decode_frame

        sequence = self.sent.get(case, 0) + 1
        value = {
            "schema": 1,
            "kind": "ocwp.ownership.frame",
            "identity": self.identity,
            "sender": self.sender,
            "case": case,
            "sequence": sequence,
            "event": event,
            "payload": payload,
        }
        body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        raw = len(body).to_bytes(4, "big") + body
        decode_frame(raw, self.identity)
        self.sent[case] = sequence
        self._transfer(raw, len(raw), deadline)

    def receive(
        self,
        sender: str,
        deadline: int,
        *,
        case: str | None = None,
        backend: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from scripts.ci.quote_ownership_evidence import FrameStream, decode_frame

        prefix = self._transfer(None, 4, deadline)
        length = int.from_bytes(prefix, "big")
        if not 0 < length <= 4092:
            raise WorkerRefusal("protocol")
        raw = prefix + self._transfer(None, length, deadline)
        value: dict[str, Any] = decode_frame(raw, self.identity)
        actual_case = str(value["case"])
        if case is not None and actual_case != case:
            raise WorkerRefusal("protocol")
        key = sender, actual_case
        if key not in self.streams:
            binding = backend
            if binding is None and actual_case in ("H", "S"):
                binding = value["payload"].get("backend")
            self.streams[key] = FrameStream(self.identity, sender, actual_case, backend=binding)
        return cast(dict[str, Any], self.streams[key].accept(raw))


class OwnedProcess:
    """One retained Popen identity and pidfd; no PID-only signalling fallback."""

    def __init__(
        self,
        role: str,
        case: str,
        identity: dict[str, object],
        deadline: int,
        wait_deadline: int,
        clock: Callable[[], int],
    ) -> None:
        import subprocess

        self.role, self.case, self.clock = role, case, clock
        self.pidfd: int | None = None
        self.process: dict[str, Any] | None = None
        self.reaped = False
        self.stop_requested = False
        self.close_requested = False
        args, env = launch_spec(role, case, identity, deadline, wait_deadline)
        self.child = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True,
        )
        self.identity = identity
        self.channel: Any = None

    def bind_pidfd(self) -> None:
        import os

        self.pidfd = os.pidfd_open(self.child.pid, 0)
        os.set_inheritable(self.pidfd, False)
        self.process = {**self._stat(), "pidfd_owned": True}
        self._verify()
        if self.child.stdin is None or self.child.stdout is None:
            raise WorkerRefusal("identity")
        self.channel = PipeChannel(
            self.child.stdout.fileno(),
            self.child.stdin.fileno(),
            self.identity,
            "owner",
            self.clock,
        )

    def _stat(self) -> dict[str, int]:
        from pathlib import Path

        from scripts.ci.quote_ownership_evidence import parse_process_identity

        with Path(f"/proc/{self.child.pid}/stat").open("rb") as source:
            return parse_process_identity(source.read(4097), self.child.pid)

    def _verify(self) -> None:
        from pathlib import Path

        if self.pidfd is None or self.process is None or self.child.poll() is not None:
            raise WorkerRefusal("identity")
        current = self._stat()
        if any(current[k] != self.process[k] for k in ("pid", "start_ticks")):
            raise WorkerRefusal("identity")
        with Path(f"/proc/{self.child.pid}/task/{self.child.pid}/children").open("rb") as source:
            if source.read(4097).strip():
                raise WorkerRefusal("identity")

    def ready(self, deadline: int) -> dict[str, Any]:
        message = self.channel.receive("child", deadline, case=self.case)
        self._verify()
        if message["event"] != "READY":
            raise WorkerRefusal("identity")
        return cast(dict[str, Any], message["payload"]["backend"])

    def request_close(self, deadline: int) -> int:
        self._verify()
        if self.close_requested:
            raise WorkerRefusal("protocol")
        self.close_requested = True
        requested = self.clock()
        case = "H" if self.role == "child" else "teardown"
        self.channel.send("CLOSE", case, {}, deadline)
        message = self.channel.receive(self.role, deadline, case=case)
        if message["event"] != "CLOSED":
            raise WorkerRefusal("protocol")
        return requested

    def stop(self, deadline: int) -> int:
        import signal

        self._verify()
        requested = self.clock()
        if requested >= deadline or self.stop_requested:
            raise WorkerRefusal("case_deadline")
        self.stop_requested = True
        if self.pidfd is None:
            raise WorkerRefusal("identity")
        signal.pidfd_send_signal(self.pidfd, signal.SIGKILL, None, 0)
        return requested

    def reap(self, deadline: int) -> None:
        import os

        if (
            self.reaped
            and getattr(self, "descriptors_disposed", False)
            and not getattr(self, "reap_failed", False)
        ):
            return
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise WorkerRefusal("reap_unknown")
        if not getattr(self, "os_reaped", False):
            self.exit_status = self.child.wait(timeout=remaining / SECOND)
            self.os_reaped = True
            if self.clock() >= deadline:
                self.reap_failed = True
                raise WorkerRefusal("reap_unknown")
        self.reaped = True  # OS wait completed; descriptor disposal is a separate fact.
        attempted: set[str] = getattr(self, "close_attempted", set())
        self.close_attempted = attempted
        failed = getattr(self, "reap_failed", False)
        close_failed = getattr(self, "close_failed", False)
        # Attempt each exact handle once even if an earlier close failed. An
        # ambiguous close is never retried against a possibly recycled numeric FD.
        for name in ("stdin", "stdout", "pidfd"):
            if name in attempted:
                continue
            attempted.add(name)
            try:
                if name == "pidfd":
                    descriptor, self.pidfd = self.pidfd, None
                    if descriptor is not None:
                        os.close(descriptor)
                else:
                    pipe = getattr(self.child, name)
                    if pipe is not None:
                        pipe.close()
            except Exception:
                close_failed = True
                failed = True
        self.close_failed = close_failed
        self.descriptors_disposed = not close_failed
        expected = -9 if self.stop_requested else 0
        if self.role == "child" and self.case == "S" and not self.stop_requested:
            failed = True
        if self.exit_status != expected or self.clock() >= deadline:
            failed = True
        self.reap_failed = failed
        if failed:
            raise WorkerRefusal("reap_unknown")
        self.reaped = True


class ObserverProxy:
    def __init__(self, owned: OwnedProcess) -> None:
        self.owned = owned
        self.process = owned.process
        self.case: str | None = None
        self.backend: dict[str, Any] | None = None

    def bind(self, case: str, backend: dict[str, Any]) -> None:
        if (self.case, case) not in ((None, "H"), ("H", "S")):
            raise WorkerRefusal("protocol")
        self.case, self.backend = case, backend

    def absent(self, backend: dict[str, Any], deadline: int) -> bool:
        if self.case is None or backend != self.backend:
            raise WorkerRefusal("identity")
        self.owned.channel.send("OBSERVE", self.case, {"backend": backend}, deadline)
        message = self.owned.channel.receive("observer", deadline, case=self.case, backend=backend)
        if message["event"] != "OBSERVED":
            raise WorkerRefusal("observer_unknown")
        return not message["payload"]["present"]

    def close(self, deadline: int) -> tuple[int, int]:
        self.owned.request_close(deadline)
        closed = self.owned.clock()
        self.owned.reap(deadline)
        return closed, self.owned.clock()


class RuntimeAdapter:
    def __init__(self, identity: dict[str, object], host: PipeChannel) -> None:
        import time

        self.identity, self.host, self.now = identity, host, time.monotonic_ns
        self.processes: list[OwnedProcess] = []
        self.observer: ObserverProxy | None = None
        self.experiment_end: int | None = None

    def _spawn(self, role: str, case: str, deadline: int, wait_end: int) -> OwnedProcess:
        process = OwnedProcess(role, case, self.identity, deadline, wait_end, self.now)
        self.processes.append(process)  # Retain handle even if pidfd/identity binding fails.
        process.bind_pidfd()
        return process

    def reserve(self, deadline: int) -> ObserverProxy:
        from scripts.ci.quote_ownership_database import preflight

        preflight(self.now, deadline)
        owned = self._spawn("observer", "setup", deadline, deadline)
        message = owned.channel.receive("observer", deadline, case="setup")
        if message["event"] != "RESERVED":
            raise WorkerRefusal("observer_unknown")
        self.observer = ObserverProxy(owned)
        return self.observer

    def reserved(self, deadline: int) -> None:
        self.host.send("RESERVED", "setup", {"read_only": True, "transaction_idle": True}, deadline)

    def go(self, deadline: int) -> int:
        message = self.host.receive("host", deadline, case="setup")
        if message["event"] != "GO" or self.observer is None:
            raise WorkerRefusal("protocol")
        started = self.now()
        self.experiment_end = started + 26 * SECOND
        self.observer.owned.channel.send(
            "BEGIN", "setup", {"experiment_deadline_ns": self.experiment_end}, deadline
        )
        return started

    def spawn(self, case: str, deadline: int) -> OwnedProcess:
        if self.experiment_end is None:
            raise WorkerRefusal("protocol")
        return self._spawn(
            "child",
            case,
            deadline,
            min(self.experiment_end, deadline + (5 * SECOND if case == "S" else 0)),
        )

    def wait_until(self, target: int, deadline: int) -> None:
        import time

        if target > deadline:
            raise WorkerRefusal("experiment_deadline")
        remaining = target - self.now()
        if remaining > 0:
            time.sleep(remaining / SECOND)

    def cleanup(self, observer: Any, children: Any, deadline: int) -> None:
        # Failure cleanup is finite, owned and uses only the original remaining window.
        failed = False
        for owned in reversed(self.processes):
            if (
                owned.reaped
                and getattr(owned, "descriptors_disposed", False)
                and not getattr(owned, "reap_failed", False)
            ):
                continue
            try:
                if owned.child.poll() is None and not owned.stop_requested:
                    owned.stop(deadline)
                owned.reap(deadline)
            except Exception:
                failed = True
        if failed:
            raise WorkerRefusal("cleanup_unknown")


def _child_main(channel: PipeChannel, case: str, deadline: int, wait_end: int) -> int:
    from scripts.ci.quote_ownership_database import open_clean_session

    clean = open_clean_session(channel.clock, deadline)
    channel.send(
        "READY",
        case,
        {"backend": clean.backend, "read_only": True, "clean_session": True, "same_backend": True},
        deadline,
    )
    command = channel.receive("owner", wait_end, case=case)
    if case != "H" or command["event"] != "CLOSE":
        raise WorkerRefusal("protocol")
    clean.close(channel.clock, deadline)
    channel.send("CLOSED", "H", {}, deadline)
    return 0


def _observer_main(channel: PipeChannel, setup_end: int) -> int:
    from scripts.ci.quote_ownership_database import close_observer, observe_absence, open_observer

    raw = open_observer(channel.clock, setup_end)
    channel.send("RESERVED", "setup", {"read_only": True, "transaction_idle": True}, setup_end)
    command = channel.receive("owner", setup_end)
    end = setup_end
    if command["event"] == "BEGIN" and command["case"] == "setup":
        end = command["payload"]["experiment_deadline_ns"]
        if not 0 < end - channel.clock() <= 26 * SECOND:
            raise WorkerRefusal("experiment_deadline")
        command = channel.receive("owner", end)
    elif not (command["event"] == "CLOSE" and command["case"] == "teardown"):
        raise WorkerRefusal("protocol")
    current = "H"
    seen_h = False
    for _ in range(513):
        if command["event"] == "CLOSE" and command["case"] == "teardown":
            close_observer(raw, channel.clock, end)
            channel.send("CLOSED", "teardown", {}, end)
            return 0
        if command["event"] != "OBSERVE" or command["case"] not in ("H", "S"):
            raise WorkerRefusal("protocol")
        if (current == "S" and command["case"] == "H") or (not seen_h and command["case"] == "S"):
            raise WorkerRefusal("protocol")
        current = command["case"]
        seen_h = seen_h or current == "H"
        backend = command["payload"]["backend"]
        absent = observe_absence(raw, backend, channel.clock, end)
        channel.send(
            "OBSERVED",
            current,
            {
                "backend": backend,
                "present": not absent,
                "read_only": True,
                "transaction_idle": True,
            },
            end,
        )
        command = channel.receive("owner", end)
    raise WorkerRefusal("protocol")


def main() -> int:
    """Explicit contained consumer only. Routine pytest never invokes this path."""
    import argparse
    import json
    import os
    import time

    from scripts.ci.quote_ownership_evidence import FrameStream

    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("owner", "child", "observer"), required=True)
    parser.add_argument("--case", choices=("setup", "H", "S"), required=True)
    args = parser.parse_args()
    if os.getcwd() != "/app" or os.environ.get("OCWP_OWNERSHIP_CONTAINED") != "1":
        return 1
    try:
        identity = json.loads(os.environ["OCWP_OWNERSHIP_IDENTITY"])
        FrameStream(identity, "host", "setup")  # Closed source/guard identity, no IO.
        if identity["database"] != "ocwp" or identity["role"] != "ocwp":
            return 1
        if any(
            k.startswith("PG") or k in {"OCWP_DATABASE_URL", "OCWP_DATABASE_URL_FILE"}
            for k in os.environ
        ):
            return 1
        channel = PipeChannel(0, 1, identity, args.role)
        if args.role == "owner" and args.case == "setup":
            deadline = int(os.environ["OCWP_OWNERSHIP_SETUP_DEADLINE_NS"])
            if not 0 < deadline - time.monotonic_ns() <= 65 * SECOND:
                return 1
            adapter = RuntimeAdapter(identity, channel)
            result = run_owner(adapter, identity, deadline)
            end = adapter.experiment_end or deadline
            channel.send("RESULT", "teardown", result, end)
            return 0 if result["status"] == "observed" else 1
        deadline = int(os.environ["OCWP_OWNERSHIP_CASE_DEADLINE_NS"])
        wait_end = int(os.environ["OCWP_OWNERSHIP_WAIT_DEADLINE_NS"])
        if args.role == "child" and args.case in ("H", "S"):
            if (
                not 0 < deadline - time.monotonic_ns() <= 8 * SECOND
                or not deadline <= wait_end <= deadline + 5 * SECOND
            ):
                return 1
            return _child_main(channel, args.case, deadline, wait_end)
        if args.role == "observer" and args.case == "setup":
            if not 0 < deadline - time.monotonic_ns() <= 65 * SECOND:
                return 1
            return _observer_main(channel, deadline)
        return 1
    except Exception:
        # No arbitrary exception/SQL/credential output, including during startup.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
