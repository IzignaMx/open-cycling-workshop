"""Prepare the existing ephemeral GitHub service between independent browser phases.

This is not general-purpose database cleanup or hostile-host attestation. The
reviewed sequential verify job owns the service CID and runner. Inspect-to-port
and session-check-to-reset races remain within that trusted lifecycle. Unexpected
clients (even transient health probes) cause refusal, never termination or retry.
No runtime action happens on import. Tests inject every external operation.
"""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

FIXTURE_DSN = "postgresql+psycopg://ocwp:ocwp-test@127.0.0.1:5432/ocwp_e2e"
DSN_KEYS = ("OCWP_E2E_DATABASE_URL", "OCWP_DATABASE_URL", "OCWP_TEST_DATABASE_URL")
ROOT = Path(__file__).resolve().parents[2]
INSPECT_FORMAT = (
    '{"id":{{json .Id}},"image":{{json .Config.Image}},"image_id":{{json .Image}},'
    '"running":{{json .State.Running}},"health":{{json .State.Health.Status}},'
    '"network_mode":{{json .HostConfig.NetworkMode}},"privileged":{{json .HostConfig.Privileged}},'
    '"binds":{{json .HostConfig.Binds}},"volumes_from":{{json .HostConfig.VolumesFrom}},'
    '"pid_mode":{{json .HostConfig.PidMode}},"cap_add":{{json .HostConfig.CapAdd}},'
    '"devices":{{json .HostConfig.Devices}},"mounts":{{json .Mounts}},'
    '"ports":{{json .NetworkSettings.Ports}}}'
)


LISTENER_REASONS = frozenset({"oversized", "malformed", "read_error", "protected_listener"})


def safe_listener_reason(stage: object, reason: object) -> str | None:
    if stage == "listeners" and isinstance(reason, str) and reason in LISTENER_REASONS:
        return reason
    return None


class FixtureRefused(RuntimeError):
    def __init__(self, stage: str = "unknown", *, listener_reason: str | None = None) -> None:
        super().__init__("Browser fixture preparation refused")
        self.stage = (
            stage
            if isinstance(stage, str)
            and stage
            in {"environment", "inspect", "service", "listeners", "sessions", "preparation"}
            else "unknown"
        )
        self.listener_reason = safe_listener_reason(self.stage, listener_reason)


def inspect_service(args: list[str], environment: Mapping[str, str]) -> str:
    # Bound combined stdout/stderr while reading; never relay raw process output.
    process = subprocess.Popen(
        args,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = bytearray()
    deadline = time.monotonic() + 5
    try:
        assert process.stdout is not None
        with process.stdout, selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise FixtureRefused("inspect")
                block = os.read(process.stdout.fileno(), 4096)
                if not block:
                    break
                if len(output) + len(block) > 16384:
                    raise FixtureRefused("inspect")
                output.extend(block)
            if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise FixtureRefused("inspect")
        return output.decode("utf-8", errors="strict")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)


def listener_table_clear(table: str) -> bool:
    return listener_table_reason(table) is None


def listener_table_reason(table: str) -> str | None:
    lines = table.splitlines()
    if not lines:
        return "malformed"
    header = lines[0].split()
    if (
        len(header) < 4
        or header[:2] != ["sl", "local_address"]
        or header[2] not in {"rem_address", "remote_address"}
        or header[3:]
        != ["st", "tx_queue", "rx_queue", "tr", "tm->when", "retrnsmt", "uid", "timeout", "inode"]
    ):
        return "malformed"
    address = r"(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{32}):[0-9A-Fa-f]{4}"
    for line in lines[1:]:
        fields = line.split()
        if (
            len(fields) < 10
            or re.fullmatch(r"[0-9]+:", fields[0]) is None
            or re.fullmatch(address, fields[1]) is None
            or re.fullmatch(address, fields[2]) is None
            or fields[3] not in {f"{value:02X}" for value in range(1, 13)}
        ):
            return "malformed"
        if fields[3] == "0A" and int(fields[1].rsplit(":", 1)[1], 16) in {8000, 5173, 5174}:
            return "protected_listener"
    return None


def fixture_listeners_absent() -> bool:
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with Path(path).open("rb") as source:
                table = source.read(65537)
        except Exception:
            raise FixtureRefused("listeners", listener_reason="read_error") from None
        if len(table) > 65536:
            raise FixtureRefused("listeners", listener_reason="oversized")
        try:
            decoded = table.decode("ascii")
        except UnicodeError:
            raise FixtureRefused("listeners", listener_reason="read_error") from None
        reason = listener_table_reason(decoded)
        if reason is not None:
            raise FixtureRefused("listeners", listener_reason=reason)
    return True


def other_fixture_sessions() -> int:
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        FIXTURE_DSN,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=2000"},
    )
    try:
        with engine.connect() as connection:
            value = connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                    "AND backend_type = 'client backend' AND pid <> pg_backend_pid()"
                )
            ).scalar_one()
            if type(value) is not int:
                raise FixtureRefused()
            return value
    finally:
        engine.dispose()


def prepare_existing_fixture(environment: Mapping[str, str]) -> None:
    # Existing destination checks/migrations/seeding stay authoritative. The child
    # exits on failure; no subsequent browser phase starts with a partial fixture.
    result = subprocess.run(
        [sys.executable, "scripts/e2e/prepare_e2e_database.py"],
        cwd=ROOT,
        env={**environment, **{key: FIXTURE_DSN for key in DSN_KEYS}},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise FixtureRefused()


def prepare_phase(
    environment: Mapping[str, str],
    *,
    inspect: Callable[[list[str], Mapping[str, str]], str] = inspect_service,
    listeners_absent: Callable[[], bool] = fixture_listeners_absent,
    other_sessions: Callable[[], int] = other_fixture_sessions,
    prepare: Callable[[Mapping[str, str]], None] = prepare_existing_fixture,
) -> dict[str, object]:
    environment = dict(environment)
    stage = "environment"
    try:
        cid = environment.get("OCWP_E2E_SERVICE_ID", "")
        if (
            environment.get("GITHUB_ACTIONS") != "true"
            or environment.get("GITHUB_JOB") != "verify"
            or re.fullmatch(r"[a-f0-9]{64}", cid) is None
            or any(environment.get(key) != FIXTURE_DSN for key in DSN_KEYS)
            or any(
                key.startswith("PG")
                or key.startswith("DOCKER_")
                or key in {name + "_FILE" for name in DSN_KEYS}
                for key in environment
            )
        ):
            raise FixtureRefused()
        stage = "inspect"
        raw = inspect(
            [
                "docker",
                "--host",
                "unix:///var/run/docker.sock",
                "inspect",
                "--type",
                "container",
                "--format",
                INSPECT_FORMAT,
                cid,
            ],
            environment,
        )
        if len(raw) > 16384:
            raise FixtureRefused()
        stage = "service"
        detail = json.loads(raw)
        if (
            not isinstance(detail, dict)
            or detail.get("id") != cid
            or detail.get("image") != "postgres:18.4-trixie"
            or not isinstance(detail.get("image_id"), str)
            or re.fullmatch(r"sha256:[a-f0-9]{64}", detail["image_id"]) is None
            or detail.get("running") is not True
            or detail.get("health") != "healthy"
            or detail.get("privileged") is not False
            or detail.get("binds") not in (None, [])
            or detail.get("volumes_from") not in (None, [])
            or detail.get("pid_mode") != ""
            or detail.get("cap_add") not in (None, [])
            or detail.get("devices") not in (None, [])
            or not isinstance(detail.get("network_mode"), str)
            or detail["network_mode"] in ("host", "none", "", "default")
            or detail["network_mode"].startswith("container:")
        ):
            raise FixtureRefused()
        mounts = detail.get("mounts")
        if (
            not isinstance(mounts, list)
            or len(mounts) != 1
            or any(
                not isinstance(mount, dict)
                or mount.get("Type") != "volume"
                or mount.get("Destination")
                not in {"/var/lib/postgresql", "/var/lib/postgresql/data"}
                for mount in mounts
            )
        ):
            raise FixtureRefused()
        ports = detail.get("ports")
        if not isinstance(ports, dict) or set(ports) != {"5432/tcp"}:
            raise FixtureRefused()
        bindings = ports["5432/tcp"]
        if (
            not isinstance(bindings, list)
            or not 1 <= len(bindings) <= 2
            or any(
                not isinstance(binding, dict)
                or binding.get("HostPort") != "5432"
                or binding.get("HostIp") not in {"0.0.0.0", "127.0.0.1", "::", "::1"}
                for binding in bindings
            )
        ):
            raise FixtureRefused()
        if not any(binding["HostIp"] in {"0.0.0.0", "127.0.0.1"} for binding in bindings):
            raise FixtureRefused()
        stage = "listeners"
        if not listeners_absent():
            raise FixtureRefused()
        stage = "sessions"
        clients = other_sessions()
        if type(clients) is not int or clients != 0:
            raise FixtureRefused()
        stage = "preparation"
        prepare(environment)
        return {"prepared": True, "container_id": cid, "image_id": detail["image_id"]}
    except Exception as error:
        reason = safe_listener_reason(stage, getattr(error, "listener_reason", None))
        raise FixtureRefused(stage, listener_reason=reason) from None


def main() -> int:
    try:
        print(json.dumps(prepare_phase(os.environ), sort_keys=True))
        return 0
    except FixtureRefused as error:
        # Revalidate at emission: exception attributes are mutable and never trusted.
        stage = FixtureRefused(error.stage).stage
        result: dict[str, object] = {"prepared": False, "stage": stage, "reason": "refused"}
        reason = safe_listener_reason(stage, getattr(error, "listener_reason", None))
        if reason is not None:
            result["listener_reason"] = reason
        print(json.dumps(result), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
