#!/usr/bin/env python3
"""Disposable Docker-only qualification; never connects to an operator's stack."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/compose/docker-compose.local.yml"
PG_IMAGE = "postgres:18.4-trixie"
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def disposable_environment(inherited: dict[str, str]) -> dict[str, str]:
    """Never inherit an operator's project, database, credentials or cutover setting."""
    return {
        key: value for key, value in inherited.items() if not key.startswith(("COMPOSE_", "OCWP_"))
    } | {"OCWP_CUTOVER_ENABLED": "true"}


def restored_api_override(restore_file: Path) -> dict[str, object]:
    """A generated API-only switch; workers/migrations retain the original target."""
    return {
        "services": {
            "api": {
                "environment": {"OCWP_DATABASE_URL_FILE": "/run/secrets/restore_url"},
                "secrets": [{"source": "restore_url", "target": "restore_url"}],
            }
        },
        "secrets": {"restore_url": {"file": str(restore_file)}},
    }


class BrowserSmoke:
    """One bounded pipe-only browser session survives the actual restore drill.

    Never forward raw child output: an assertion can contain a bearer token or
    session snapshot. Only the closed phase protocol enters durable evidence.
    """

    def __init__(self, command: list[str], *, env: dict[str, str], timeout: float = 180) -> None:
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.timeout = timeout
        self.buffer = b""

    def __enter__(self) -> BrowserSmoke:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send(self, payload: dict[str, object]) -> None:
        body = (json.dumps(payload) + "\n").encode()
        if len(body) > 16384:
            raise RuntimeError("Browser smoke input exceeds limit")
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(body)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            raise RuntimeError("Browser smoke input pipe closed") from None

    def expect(self, phase: str) -> None:
        deadline = time.monotonic() + self.timeout
        assert self.process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise RuntimeError("Browser smoke phase timed out")
                chunk = os.read(self.process.stdout.fileno(), 4097)
                if not chunk:
                    raise RuntimeError("Browser smoke exited before expected phase")
                self.buffer += chunk
                if len(self.buffer) > 4096:
                    raise RuntimeError("Browser smoke phase exceeds limit")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            message = json.loads(line)
        except (ValueError, UnicodeError):
            raise RuntimeError("Browser smoke emitted invalid phase") from None
        if (
            isinstance(message, dict)
            and set(message) == {"phase", "step"}
            and message["phase"] == "failed"
            and isinstance(message["step"], str)
            and re.fullmatch(r"[a-z_]{1,64}", message["step"])
        ):
            raise RuntimeError("Browser smoke failed during " + message["step"])
        if message != {"phase": phase}:
            raise RuntimeError("Browser smoke emitted unexpected phase")

    def finish(self) -> None:
        try:
            code = self.process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Browser smoke exit timed out") from None
        if code:
            raise RuntimeError("Browser smoke exited unsuccessfully")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout):
            if pipe is not None:
                pipe.close()


def redact(value: str, secrets: list[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted]")
    return JWT_PATTERN.sub("[redacted]", value)


def assert_logs_safe(logs: str, secrets: list[str]) -> None:
    # Browser-issued tokens never leave that process. Detect JWT-shaped output
    # too, so those tokens are covered without exporting their value or hash.
    if any(secret and secret in logs for secret in secrets) or JWT_PATTERN.search(logs):
        raise RuntimeError("Container logs contain generated credentials")


def diagnostic_capture(
    parts: list[str],
    *,
    env: dict[str, str],
    secrets: list[str],
    timeout: float = 5,
    max_bytes: int = 16384,
) -> dict[str, object]:
    """Bound one disposable-project probe; never publish partial raw output.

    Redact only a complete capture, so byte truncation cannot split a credential
    into an unrecognizable fragment. Timeout/overflow output is discarded. The
    direct child is reaped and its owned group terminated before fixture cleanup.
    """
    try:
        process = subprocess.Popen(
            parts,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError:
        return {"status": "unavailable"}
    try:
        assert process.stdout is not None
        output = bytearray()
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    return {"status": "timeout"}
                chunk = os.read(process.stdout.fileno(), min(4096, max_bytes + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > max_bytes:
                    return {"status": "output_limit"}
        try:
            code = process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
        return {
            "status": "captured",
            "returncode": code,
            "output": redact(output.decode("utf-8", errors="replace"), secrets),
        }
    except OSError:
        return {"status": "unavailable"}
    finally:
        # A normally exited CLI can leave same-group plugin descendants whose
        # stdio is detached. Terminate those too, not only the timeout path.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=1)
        if process.stdout is not None:
            process.stdout.close()


class RestartDiagnostics:
    """Finite observations of one generated project's API, never a startup fix."""

    INSPECT_FORMAT = (
        "{"
        + ",".join(
            f'"{key}":{{{{json {expression}}}}}'
            for key, expression in {
                "id": ".Id",
                "project": '(index .Config.Labels "com.docker.compose.project")',
                "service": '(index .Config.Labels "com.docker.compose.service")',
                "status": ".State.Status",
                "running": ".State.Running",
                "restarting": ".State.Restarting",
                "exit_code": ".State.ExitCode",
                "oom_killed": ".State.OOMKilled",
                "restart_count": ".RestartCount",
                "error_present": '(ne .State.Error "")',
                "started_at": ".State.StartedAt",
                "finished_at": ".State.FinishedAt",
            }.items()
        )
        + "}"
    )
    EVENT_FORMAT = (
        "{"
        + ",".join(
            f'"{key}":{{{{json {expression}}}}}'
            for key, expression in {
                "id": ".Actor.ID",
                "type": ".Type",
                "action": ".Action",
                "time_nano": ".TimeNano",
                "exit_code": '(index .Actor.Attributes "exitCode")',
                "signal": '(index .Actor.Attributes "signal")',
            }.items()
        )
        + "}"
    )

    def __init__(self, command: list[str], *, env: dict[str, str], secrets: list[str]) -> None:
        self.command, self.env, self.secrets = command, env, secrets

    def _probe(self, parts: list[str]) -> tuple[str, str]:
        try:
            result = diagnostic_capture(parts, env=self.env, secrets=self.secrets)
            status = result.get("status")
            if status in ("timeout", "output_limit", "unavailable"):
                return str(status), ""
            if status != "captured" or result.get("returncode") != 0:
                return "command_failed", ""
            return "captured", str(result["output"])
        except Exception:
            return "unavailable", ""

    def _snapshot(self, container: str, project: str) -> dict[str, object]:
        status, output = self._probe(
            [
                "docker",
                "inspect",
                "--type",
                "container",
                "--format",
                self.INSPECT_FORMAT,
                container,
            ]
        )
        if status != "captured":
            return {"status": status}
        try:
            row = json.loads(output)
            if not isinstance(row, dict) or (
                row.get("id"),
                row.get("project"),
                row.get("service"),
            ) != (container, project, "api"):
                raise ValueError("binding")
            state = {
                key: row[key]
                for key in (
                    "status",
                    "running",
                    "restarting",
                    "exit_code",
                    "oom_killed",
                    "restart_count",
                    "error_present",
                    "started_at",
                    "finished_at",
                )
            }
            if state["status"] not in (
                "created",
                "running",
                "paused",
                "restarting",
                "removing",
                "exited",
                "dead",
            ):
                raise ValueError("status")
            for key in ("running", "restarting", "oom_killed", "error_present"):
                if type(state[key]) is not bool:
                    raise ValueError("boolean")
            for key, maximum in (("exit_code", 255), ("restart_count", 2**31 - 1)):
                if type(state[key]) is not int or not 0 <= state[key] <= maximum:
                    raise ValueError("integer")
            for key in ("started_at", "finished_at"):
                value = state[key]
                if not isinstance(value, str) or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", value
                ):
                    raise ValueError("timestamp")
                datetime.fromisoformat(value)
            return {"status": "captured", "state": state}
        except (ValueError, TypeError, KeyError):
            return {"status": "invalid_output"}

    def _events(self, container: str, project: str, since: object) -> dict[str, object]:
        try:
            until = time.time_ns()
            if type(since) is not int or type(until) is not int or not 0 < since <= until < 2**63:
                return {"status": "invalid_window"}
            status, output = self._probe(
                [
                    "docker",
                    "events",
                    "--since",
                    f"{since // 10**9}.{since % 10**9:09d}",
                    "--until",
                    f"{until // 10**9}.{until % 10**9:09d}",
                    "--filter",
                    "type=container",
                    "--filter",
                    f"container={container}",
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                    "--format",
                    self.EVENT_FORMAT,
                ]
            )
            if status != "captured":
                return {"status": status}
            lines = [line for line in output.splitlines() if line.strip()]
            if len(lines) > 128:
                return {"status": "event_limit"}
            events = []
            for line in lines:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("shape")
                stamp = row.get("time_nano")
                if (
                    row.get("id") != container
                    or row.get("type") != "container"
                    or row.get("action")
                    not in (
                        "create",
                        "start",
                        "stop",
                        "kill",
                        "die",
                        "oom",
                        "restart",
                        "destroy",
                        "pause",
                        "unpause",
                    )
                    or type(stamp) is not int
                    or not since <= stamp <= until
                ):
                    continue
                event: dict[str, object] = {"action": row["action"], "time_nano": stamp}
                for key, maximum in (("exit_code", 255), ("signal", 64)):
                    value = row.get(key)
                    event[key] = (
                        int(value)
                        if isinstance(value, str)
                        and re.fullmatch(r"\d{1,3}", value)
                        and 0 <= int(value) <= maximum
                        else None
                    )
                events.append(event)
            return {
                "status": "captured",
                "window_start_ns": since,
                "window_end_ns": until,
                "events": events,
            }
        except (ValueError, TypeError):
            return {"status": "invalid_output"}
        except Exception:
            return {"status": "unavailable"}

    def capture(self, record: dict[str, object], phase: str) -> None:
        """Collector and clock failures cannot escape into qualification/cleanup."""
        diagnostics = record.setdefault("diagnostics", {})
        assert isinstance(diagnostics, dict)
        snapshots = diagnostics.setdefault("snapshots", {})
        assert isinstance(snapshots, dict)
        snapshots[phase] = {"status": "unavailable"}
        started = None
        with suppress(Exception):
            started = time.monotonic()
        try:
            project = self.command[self.command.index("-p") + 1]
            if not re.fullmatch(r"ocwp-smoke-[a-f0-9]{12}", project):
                snapshots[phase] = {"status": "invalid_project"}
                return
            container = diagnostics.get("container_id")
            if phase == "before_stop":
                with suppress(Exception):
                    since = time.time_ns()
                    if type(since) is int and 0 < since < 2**63:
                        diagnostics["window_start_ns"] = since
                status, output = self._probe([*self.command, "ps", "--all", "--quiet", "api"])
                if status != "captured":
                    snapshots[phase] = {"status": status}
                    return
                container = output.strip()
            if not isinstance(container, str) or not re.fullmatch("[a-f0-9]{64}", container):
                snapshots[phase] = {"status": "unbound_container"}
                return
            snapshots[phase] = self._snapshot(container, project)
            if phase == "before_stop" and snapshots[phase]["status"] == "captured":
                diagnostics["container_id"] = container
            if phase in ("failed", "complete"):
                diagnostics["events"] = self._events(
                    container, project, diagnostics.get("window_start_ns")
                )
        except Exception:
            snapshots[phase] = {"status": "unavailable"}
        finally:
            with suppress(Exception):
                if started is not None:
                    elapsed = time.monotonic() - started
                    if math.isfinite(elapsed) and elapsed >= 0:
                        diagnostics["elapsed_seconds"] = round(
                            diagnostics.get("elapsed_seconds", 0) + elapsed, 3
                        )


def failure_diagnostics(
    command: list[str], *, env: dict[str, str], secrets: list[str]
) -> dict[str, object]:
    """Read only the existing random Compose project before it is removed."""
    services = ("api", "edge", "migrate", "postgres", "worker")
    probe = diagnostic_capture(
        [*command, "ps", "--all", "--format", "json"], env=env, secrets=secrets
    )
    containers = []
    state_status = probe["status"]
    if state_status == "captured" and probe.get("returncode") == 0:
        try:
            raw = str(probe["output"])
            rows = (
                json.loads(raw)
                if raw.lstrip().startswith("[")
                else [json.loads(line) for line in raw.splitlines() if line.strip()]
            )
            if not isinstance(rows, list):
                raise ValueError("unexpected state shape")
            for row in rows:
                if not isinstance(row, dict) or row.get("Service") not in services:
                    continue
                state, health, code = row.get("State"), row.get("Health"), row.get("ExitCode")
                containers.append(
                    {
                        "service": row["Service"],
                        "state": state
                        if state
                        in (
                            "created",
                            "running",
                            "paused",
                            "restarting",
                            "removing",
                            "exited",
                            "dead",
                        )
                        else "unknown",
                        "health": health
                        if health in ("healthy", "unhealthy", "starting")
                        else "unknown",
                        "exit_code": code if type(code) is int and 0 <= code <= 255 else None,
                    }
                )
        except (ValueError, TypeError):
            state_status = "invalid_output"
    logs = {
        service: diagnostic_capture(
            [*command, "logs", "--no-color", "--tail", "40", service], env=env, secrets=secrets
        )
        for service in services
    }
    return {"container_status": state_status, "containers": containers, "logs": logs}


def validate_config(config: dict[str, object]) -> None:
    services = config["services"]
    assert isinstance(services, dict)
    for name, service in services.items():
        for port in service.get("ports", []):
            assert name == "edge" and port["host_ip"] == "127.0.0.1"
        assert not service.get("privileged", False)
    for name in ("api", "worker", "bootstrap"):
        assert (
            services[name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
        )
    assert "data_net" not in services["edge"]["networks"]
    assert "app_net" not in services["postgres"]["networks"]
    assert config["networks"]["data_net"]["internal"] is True  # type: ignore[index]
    assert config["networks"]["app_net"]["internal"] is True  # type: ignore[index]


def request(
    base: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(base + path, data=data, headers=headers)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return (
            response.status,
            {key.lower(): val for key, val in response.headers.items()},
            response.read(),
        )


def wait_ready(base: str) -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            code, _, body = request(base, "/health/ready")
            if code == 200 and json.loads(body)["status"] == "ready":
                return
        except (URLError, TimeoutError, OSError, ValueError, KeyError):
            pass
        time.sleep(2)
    raise RuntimeError("edge/API did not become ready within 180 seconds")


def qualify_api_restarts(
    compose: Callable[..., object],
    base: str,
    verify_branding: Callable[[], None],
    cycles: list[dict[str, object]],
    *,
    diagnostics: Callable[[dict[str, object], str], None] | None = None,
) -> None:
    """Three mandatory same-project cycles; the first failure is never retried."""

    def capture(record: dict[str, object], phase: str) -> None:
        if diagnostics is not None:
            try:
                diagnostics(record, phase)
            except Exception:
                record["diagnostic_callback_status"] = "unavailable"

    def checked_command(record: dict[str, object], action: str) -> None:
        if diagnostics is None:
            compose(action, "api")
            return
        commands = record.setdefault("commands", {})
        assert isinstance(commands, dict)
        result: dict[str, object] = {"status": "running"}
        commands[action] = result

        def stamp(key: str) -> None:
            with suppress(Exception):
                value = time.monotonic()
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    result[key] = value

        stamp("started_monotonic")
        try:
            completed = compose(action, "api")
            result["status"] = "passed"
            code = getattr(completed, "returncode", None)
            if type(code) is int and -255 <= code <= 255:
                result["returncode"] = code
        except Exception:
            result["status"] = "failed"
            raise
        finally:
            stamp("finished_monotonic")

    for number in range(1, 4):
        record: dict[str, object] = {
            "cycle": number,
            "status": "running",
            "phase": "stopping",
        }
        cycles.append(record)

        started = None
        with suppress(Exception):
            started = time.monotonic()
        try:
            capture(record, "before_stop")
            checked_command(record, "stop")
            capture(record, "after_stop")
            record["phase"] = "checking_outage"
            code, _, body = request(base, "/api/v1/auth/me")
            assert code == 502 and b'<div id="root">' not in body
            record["phase"] = "checking_static"
            assert request(base, "/")[0] == 200
            record["phase"] = "starting"
            checked_command(record, "start")
            capture(record, "after_start")
            record["phase"] = "waiting_ready"
            wait_ready(base)
            record["phase"] = "checking_branding"
            verify_branding()
            record["phase"] = "complete"
            record["status"] = "passed"
            capture(record, "complete")
        except Exception:
            record["status"] = "failed"
            capture(record, "failed")
            raise
        finally:
            # Optional timing must never replace the original qualification error.
            with suppress(Exception):
                if started is not None:
                    elapsed = time.monotonic() - started
                    if math.isfinite(elapsed) and elapsed >= 0:
                        record["elapsed_seconds"] = round(elapsed, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("artifacts/local-runtime.json"))
    parser.add_argument(
        "--browser", action="store_true", help="Require installed Playwright Chromium"
    )
    args = parser.parse_args()
    evidence: dict[str, object] = {
        "status": "failed",
        "checks": [],
        "physical_hardware": "not tested",
    }
    checks: list[str] = []
    secrets: list[str] = []
    project = "ocwp-smoke-" + uuid.uuid4().hex[:12]
    env = disposable_environment(dict(os.environ))
    browser: BrowserSmoke | None = None
    branding_probe = None
    command = ["docker", "compose", "-p", project, "-f", str(COMPOSE)]

    def run(
        parts: list[str], *, check: bool = True, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            parts, cwd=ROOT, env=env, input=stdin, capture_output=True, text=True, timeout=1200
        )
        if check and result.returncode:
            output = redact(result.stdout + result.stderr, secrets)
            raise RuntimeError(f"Command failed ({parts[0]}):\n{output[-12000:]}")
        return result

    def compose(*parts: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run([*command, *parts], check=check)

    with tempfile.TemporaryDirectory(prefix=project + "-", ignore_cleanup_errors=True) as temporary:
        directory = Path(temporary)
        try:
            sys.path.insert(0, str(ROOT))
            from scripts.ci.branding_volume_probe import BrandingVolumeProbe
            from scripts.operations.init_local_secrets import initialize_secrets

            branding_probe = BrandingVolumeProbe(
                project=project, command=command, directory=directory, run=run, secrets=secrets
            )

            secret_dir = directory / "secrets"
            initialize_secrets(secret_dir, include_admin=True)
            values = {p.stem: p.read_text().strip() for p in secret_dir.iterdir()}
            secrets.extend(values.values())
            branding_probe.prepare_restore_secret(values["database_url"])
            restore_file = secret_dir / "restore_url.txt"
            restore_file.write_text(
                values["database_url"].rsplit("/", 1)[0] + "/ocwp_restore_test\n"
            )
            restore_file.chmod(0o600)
            secrets.append(restore_file.read_text().strip())
            backup_dir = directory / "backups"
            backup_dir.mkdir(mode=0o700)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env.update(
                OCWP_SECRETS_DIR=str(secret_dir),
                OCWP_BACKUP_DIR=str(backup_dir),
                OCWP_HTTP_PORT=str(port),
                OCWP_IMAGE_TAG=project,
            )
            base = f"http://127.0.0.1:{port}"
            evidence["git_sha"] = run(["git", "rev-parse", "HEAD"]).stdout.strip()
            evidence["docker_version"] = run(
                ["docker", "version", "--format", "{{.Server.Version}}"]
            ).stdout.strip()
            evidence["compose_version"] = compose("version", "--short").stdout.strip()
            evidence["architecture"] = run(
                ["docker", "info", "--format", "{{.Architecture}}"]
            ).stdout.strip()
            config = json.loads(
                compose(
                    "--profile",
                    "bootstrap",
                    "--profile",
                    "operations",
                    "config",
                    "--format",
                    "json",
                ).stdout
            )
            validate_config(config)
            checks.append("resolved_compose_private_ports_migration_dependency_and_networks")
            compose("build", "api", "edge", "operations")
            run(["docker", "pull", PG_IMAGE])
            # Discover image uid/gid, never assume a host account or chmod secrets
            # world-readable. Only this disposable directory is mounted/changed.
            pg_uid = run(
                ["docker", "run", "--rm", "--entrypoint", "id", PG_IMAGE, "-u", "postgres"]
            ).stdout.strip()
            pg_gid = run(
                ["docker", "run", "--rm", "--entrypoint", "id", PG_IMAGE, "-g", "postgres"]
            ).stdout.strip()
            assert pg_uid.isdecimal() and pg_gid.isdecimal()
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--user",
                    "0",
                    "--mount",
                    f"type=bind,source={directory},target=/state",
                    "--entrypoint",
                    "sh",
                    PG_IMAGE,
                    "-ec",
                    "chown 10001:10001 /state/secrets/database_url.txt "
                    "/state/secrets/auth_secret.txt "
                    "/state/secrets/admin_password.txt /state/secrets/restore_url.txt "
                    "/state/secrets/branding_restore_url.txt "
                    "/state/backups; "
                    f"chown {pg_uid}:{pg_gid} /state/secrets/postgres_password.txt "
                    "/state/secrets/postgres_admin_password.txt",
                ]
            )
            lan = json.loads(
                compose(
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--env",
                    "OCWP_LAN_HOST=workshop.example.test",
                    "edge",
                    "caddy",
                    "adapt",
                    "--config",
                    "/etc/caddy/Caddyfile.lan",
                    "--adapter",
                    "caddyfile",
                ).stdout
            )
            listeners = [
                listener
                for server in lan["apps"]["http"]["servers"].values()
                for listener in server["listen"]
            ]
            assert ":8443" in listeners
            assert ":8080" not in listeners
            checks.append("lan_caddy_configuration_parses_without_installing_trust")
            compose("up", "-d")
            wait_ready(base)
            assert compose("ps", "-a", "--format", "json").returncode == 0
            migration_id = compose("ps", "-a", "-q", "migrate").stdout.strip()
            assert (
                run(
                    ["docker", "inspect", "--format", "{{.State.ExitCode}}", migration_id]
                ).stdout.strip()
                == "0"
            )
            checks.append("fresh_volume_secret_backed_migration_and_readiness")
            for name in ("api", "worker"):
                assert compose("exec", "-T", name, "id", "-u").stdout.strip() == "10001"
            assert compose("exec", "-T", "edge", "id", "-u").stdout.strip() == "10001"
            # Prove NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION on the live role.
            flags = compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-Atc",
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication "
                "FROM pg_roles WHERE rolname='ocwp'",
            ).stdout.strip()
            assert flags == "f|f|f|f"
            checks.append("nonroot_processes_and_restricted_database_role")
            bootstrap = json.loads(compose("run", "--rm", "-T", "bootstrap").stdout)
            assert bootstrap["created"] is True
            assert compose("run", "--rm", "-T", "bootstrap", check=False).returncode != 0
            login_payload = {
                "organization_id": bootstrap["organization_id"],
                "username": "admin",
                "password": values["admin_password"],
            }
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(
                base,
                "/api/v1/customers",
                token=token,
                payload={
                    "location_id": bootstrap["location_id"],
                    "display_name": "Disposable runtime customer",
                },
            )
            assert code == 201
            customer_id = json.loads(body)["customer_id"]
            # Historical REST data predates activation; do not fabricate a cache.
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            assert code == 200 and json.loads(body)["snapshot_protocol"] is None
            activated = json.loads(
                compose(
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "api",
                    "ocwpctl",
                    "cutover",
                    "activate",
                    "--organization-id",
                    bootstrap["organization_id"],
                ).stdout
            )
            original_incarnation = activated["dataset_incarnation"]
            assert activated["changed"] is True and activated["minimum_write_protocol"] == 1
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            advertised = json.loads(body)
            assert code == 200 and advertised["snapshot_protocol"] == "baseline-v1"
            assert advertised["dataset_incarnation"] == original_incarnation
            assert advertised["policy_revision"] == "ocwp-access-baseline-2"
            evidence["cutover_fixture"] = "generated project only, floor 1, baseline-v1"
            checks.append("first_admin_bootstrap_guard_login_and_customer_creation")
            # Separate literal-grant fixture, before browser admission; bootstrap
            # remains the original location-bound wildcard-only actor.
            branding_probe.seed(
                base=base, bootstrap=bootstrap, token=token, password=values["admin_password"]
            )
            code, headers, html = request(base, "/")
            assert code == 200 and b'<div id="root">' in html
            assert headers["cache-control"] == "no-cache"
            assert request(base, "/workshop/deep/link")[2] == html
            asset = re.search(rb'src="(/assets/[^\"]+\.js)"', html)
            assert asset
            assert "immutable" in request(base, asset[1].decode())[1]["cache-control"]
            assert request(base, "/assets/missing.js")[0] == 404
            for path in ("/api", "/api/not-a-route", "/health/not-a-route"):
                code, headers, body = request(base, path)
                assert code == 404 and "application/json" in headers["content-type"]
                assert b'<div id="root">' not in body
            for path in ("/sw.js", "/manifest.webmanifest"):
                code, headers, body = request(base, path)
                assert code == 200 and body and headers["cache-control"] == "no-cache"
            checks.append("pwa_static_delivery_cache_policy_and_backend_404_isolation")
            if args.browser:
                browser = BrowserSmoke(
                    ["node", "scripts/ci/local_runtime_browser_smoke.mjs"], env=env
                )
                browser.send(
                    {
                        "base": base,
                        "organizationId": bootstrap["organization_id"],
                        "locationId": bootstrap["location_id"],
                        "userId": bootstrap["user_id"],
                        "password": values["admin_password"],
                        "datasetIncarnation": original_incarnation,
                        "historicalCustomerId": customer_id,
                    }
                )
                browser.expect("ready_for_backup")
                checks.append("caddy_pwa_offline_reload_queue_reconnect_two_browser_convergence")
            else:
                evidence["browser"] = "not run (pass --browser to require it)"
                evidence["authenticated_recovery"] = "not run (requires --browser)"
            restart_cycles: list[dict[str, object]] = []
            evidence["api_restart_cycles"] = restart_cycles
            restart_diagnostics = RestartDiagnostics(command, env=env, secrets=secrets).capture
            qualify_api_restarts(
                compose,
                base,
                branding_probe.verify_restart,
                restart_cycles,
                diagnostics=restart_diagnostics,
            )
            checks.append("backend_outage_returns_502_without_spa_fallback")
            # The backup/restore drill uses only a fresh, dedicated DB in this
            # generated Compose project; it cannot target an existing installation.
            compose("run", "--rm", "-T", "operations", "backup", "/backups/generation-1")
            compose("run", "--rm", "-T", "operations", "verify", "/backups/generation-1")
            branding_probe.backup()
            if browser is not None:
                browser.send({"phase": "backup_verified"})
                browser.expect("pending_preserved")
            # No fixture writer may access either DB during restored maintenance.
            compose("stop", "edge", "api", "worker")
            # An additional isolated API probes a different fresh DB and named
            # asset volume, without changing the browser recovery handshake.
            branding_probe.restore_and_probe()
            captured_logs = compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
            compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "CREATE DATABASE ocwp_restore_test OWNER ocwp",
            )
            restore_args = (
                "run",
                "--rm",
                "-T",
                "--volume",
                f"{restore_file}:/run/secrets/restore_url:ro",
                "--env",
                "OCWP_RESTORE_DATABASE_URL_FILE=/run/secrets/restore_url",
                "operations",
                "restore",
                "/backups/generation-1",
                "--confirm-empty-target",
            )
            compose(*restore_args)
            assert compose(*restore_args, check=False).returncode != 0

            def restored_history() -> str:
                # Hash exact restored records, not merely counts. Only synthetic
                # digests are retained; no user/password/session row is printed.
                return compose(
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "ocwp_restore_test",
                    "-At",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "SELECT 'customers', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY id), '')) FROM customers t "
                    "UNION ALL SELECT 'receipts', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY mutation_id), '')) "
                    "FROM sync_mutation_receipts t "
                    "UNION ALL SELECT 'changes', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY cursor), '')) FROM sync_changes t "
                    "UNION ALL SELECT 'families', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY reference_hash), '')) "
                    "FROM sync_baseline_families t "
                    "UNION ALL SELECT 'original_audit', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY id), '')) FROM identity_audit_events t "
                    "WHERE action <> 'organization.dataset_recovered'",
                ).stdout

            history_before = restored_history()
            maintenance = (
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--volume",
                f"{restore_file}:/run/secrets/restore_url:ro",
                "--env",
                "OCWP_DATABASE_URL_FILE=/run/secrets/restore_url",
                "api",
                "ocwpctl",
            )
            recovered = json.loads(
                compose(
                    *maintenance,
                    "cutover",
                    "recover",
                    "--organization-id",
                    bootstrap["organization_id"],
                    "--expected-incarnation",
                    original_incarnation,
                ).stdout
            )
            assert recovered["changed"] is True and recovered["minimum_write_protocol"] == 1
            assert recovered["dataset_incarnation"] != original_incarnation
            status = json.loads(
                compose(
                    *maintenance,
                    "cutover",
                    "status",
                    "--organization-id",
                    bootstrap["organization_id"],
                ).stdout
            )
            audit = status["latest_maintenance_audit"]
            assert status["dataset_incarnation"] == recovered["dataset_incarnation"]
            assert audit["action"] == "organization.dataset_recovered"
            assert audit["before"]["dataset_incarnation"] == original_incarnation
            assert audit["after"]["dataset_incarnation"] == recovered["dataset_incarnation"]
            assert restored_history() == history_before
            # This file contains only a mounted secret-file path, never its URL.
            override = directory / "restored-api.json"
            override.write_text(json.dumps(restored_api_override(restore_file)))
            reopened_command = [*command, "-f", str(override)]
            run([*reopened_command, "up", "-d", "--no-deps", "--force-recreate", "api", "edge"])
            wait_ready(base)
            # Worker remains stopped and cannot write to the original or restored DB.
            worker_id = compose("ps", "-a", "-q", "worker").stdout.strip()
            assert (
                run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", worker_id]
                ).stdout.strip()
                == "false"
            )
            if browser is not None:
                browser.send(
                    {
                        "phase": "restored_api_ready",
                        "datasetIncarnation": recovered["dataset_incarnation"],
                    }
                )
                browser.expect("recovery_verified")
                browser.finish()
                evidence["authenticated_recovery"] = (
                    "passed: old-token 401, backed-up checkpoint 409 with fresh token, "
                    "unchanged journal recovery hold, hidden overlay, fresh same-user work"
                )
            checks.append("pg18_backup_restore_schema_counts_and_nonempty_target_refusal")
            # The unmodified base command returns to the ORIGINAL database, proving
            # its persisted data/auth independently of the reopened restored target.
            captured_logs += compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
            compose("down")  # Deliberately no --volumes: preserve deployment state.
            compose("up", "-d")
            wait_ready(base)
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(base, f"/api/v1/customers/{customer_id}", token=token)
            assert code == 200 and json.loads(body)["display_name"] == "Disposable runtime customer"
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            assert code == 200 and json.loads(body)["dataset_incarnation"] == original_incarnation
            checks.append("down_up_retains_database_and_authentication")
            evidence["branding_named_volume"] = branding_probe.verify_source_return(token)
            captured_logs += compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
            checks.append("container_logs_do_not_contain_generated_credentials")
            evidence["image_ids"] = compose("images", "--format", "json").stdout.strip()
            evidence["status"] = "passed"
        except Exception as exc:
            evidence["error"] = redact(str(exc), secrets)
            print(evidence["error"], file=sys.stderr)
            try:
                evidence["failure_diagnostics"] = failure_diagnostics(
                    command, env=env, secrets=secrets
                )
            except Exception:
                # Diagnostic failure must not replace the first failure or prevent cleanup.
                evidence["failure_diagnostics"] = {"status": "unavailable"}
        finally:
            if browser is not None:
                browser.close()
            evidence["checks"] = checks
            if branding_probe is not None:
                try:
                    branding_probe.cleanup()
                except Exception:
                    evidence["status"] = "failed"
                    evidence["branding_cleanup"] = (
                        "Label-bound cleanup failed; inspect disposable project " + project
                    )
            try:
                # The random project is created by this test, never an operator's
                # project. Its synthetic data/volumes are intentionally disposable.
                compose(
                    "--profile",
                    "bootstrap",
                    "--profile",
                    "operations",
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    check=False,
                )
            except Exception:
                evidence["cleanup"] = f"Inspect and remove disposable project {project} manually"
            if hasattr(os, "getuid"):
                try:
                    run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "--network",
                            "none",
                            "--user",
                            "0",
                            "--mount",
                            f"type=bind,source={directory},target=/state",
                            "--entrypoint",
                            "chown",
                            PG_IMAGE,
                            "-R",
                            f"{os.getuid()}:{os.getgid()}",
                            "/state",
                        ]
                    )
                except Exception:
                    evidence["temporary_files_cleanup"] = "Inspect disposable directory " + str(
                        directory
                    )
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
