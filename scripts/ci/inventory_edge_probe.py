"""Actual Caddy 2.11.7 private-query proof for both supported edge configs.

Requires local Docker. Uses only synthetic requests, disposable containers and an
isolated internal CA; no trust-store installation or disabled TLS verification.
Only the bounded evidence JSON is publishable. Raw logs and CA are temporary.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import selectors
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "caddy:2.11.7-alpine"
PRIVATE = "inventory-edge-private-canary"
UNRELATED = "inventory-edge-unrelated-canary"
MAX_COMMAND_OUTPUT = 64 * 1024


class CommandFailure(RuntimeError):
    """Never retain subprocess output/arguments in an exception or traceback."""

    def __init__(self, reason: str, exit_code: int | None = None) -> None:
        super().__init__("edge command failed: " + reason)
        self.reason = reason
        self.exit_code = exit_code


class EdgeProbeFailure(RuntimeError):
    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__("edge probe failed; see bounded safe evidence")
        self.evidence = evidence


def run_bounded_command(arguments: list[str], *, timeout: float) -> str:
    """Cap combined output while reading, and reap the child on every exit."""
    try:
        process = subprocess.Popen(
            arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    except OSError:
        raise CommandFailure("start") from None
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        assert process.stdout is not None
        with process.stdout, selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CommandFailure("timeout")
                if not selector.select(remaining):
                    raise CommandFailure("timeout")
                block = os.read(process.stdout.fileno(), 4096)
                if not block:
                    break
                if len(output) + len(block) > MAX_COMMAND_OUTPUT:
                    raise CommandFailure("output_limit")
                output.extend(block)
            try:
                code = process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise CommandFailure("timeout") from None
        if code != 0:
            raise CommandFailure("exit", code)
        return output.decode("utf-8", errors="replace")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def safe_error(error: Exception) -> dict[str, Any]:
    if isinstance(error, CommandFailure):
        return {"error": "command", "reason": error.reason, "exit_code": error.exit_code}
    category = (
        "assertion"
        if isinstance(error, AssertionError)
        else "tls_error"
        if isinstance(error, ssl.SSLError)
        else "http_error"
        if isinstance(error, http.client.HTTPException)
        else "connection_refused"
        if isinstance(error, ConnectionRefusedError)
        else "timeout"
        if isinstance(error, TimeoutError)
        else "os_error"
        if isinstance(error, OSError)
        else "unexpected_error"
    )
    return {"error": category}


def container_state(name: str) -> dict[str, Any]:
    # Do not request Config/Env, mounts, raw State.Error or container logs.
    template = (
        '{"status":{{json .State.Status}},"exit_code":{{.State.ExitCode}},'
        '"oom_killed":{{.State.OOMKilled}}}'
    )
    try:
        state = json.loads(docker("inspect", "--format", template, name, timeout=5))
        if (
            not isinstance(state, dict)
            or set(state) != {"status", "exit_code", "oom_killed"}
            or state["status"]
            not in {"created", "running", "paused", "restarting", "removing", "exited", "dead"}
            or type(state["exit_code"]) is not int
            or not 0 <= state["exit_code"] <= 255
            or type(state["oom_killed"]) is not bool
        ):
            return {"status": "unavailable"}
        return state
    except Exception:
        return {"status": "unavailable"}


def startup_log_hints(name: str) -> dict[str, Any]:
    """Fixed hints only, called before any private synthetic query is sent."""
    try:
        logs = docker("logs", name, timeout=5).lower()
    except Exception as error:
        return {"status": "unavailable", **safe_error(error)}
    categories = []
    if any(
        value in logs
        for value in ("adapting config", "parsing caddyfile", "unrecognized directive")
    ):
        categories.append("config_error")
    if "permission denied" in logs:
        categories.append("permission_denied")
    if "address already in use" in logs:
        categories.append("address_in_use")
    if "listen tcp" in logs or "listen udp" in logs:
        categories.append("bind_listen_error")
    if "dial tcp" in logs and "connection refused" in logs:
        categories.append("upstream_connection_refused")
    return {"status": "captured", "categories": categories}


def check_logs(
    logs: str, private: list[str], unrelated: str, expected_paths: list[str]
) -> dict[str, Any]:
    assert all(canary not in logs for canary in private), "private inventory query was logged"
    errors = []
    for line in logs.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(row, dict)
            and isinstance(row.get("request"), dict)
            and row.get("level") == "error"
            and row.get("logger") == "http.log.error"
        ):
            errors.append(row)
    for path in expected_paths:
        matching = [row for row in errors if row["request"].get("uri") == path]
        assert matching, "missing actual inventory error log"
        assert all(
            row["request"].get("method") == "GET" and row.get("status") in (502, 503)
            for row in matching
        )
    assert any(unrelated in row["request"].get("uri", "") for row in errors), (
        "unrelated query was suppressed"
    )
    return {
        "inventory_errors": len(expected_paths),
        "unrelated_query_preserved": True,
        "private_queries_absent": True,
    }


class SyntheticUpstream(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"target": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *args: object) -> None:
        pass


def docker(*args: str, timeout: int = 120) -> str:
    return run_bounded_command(["docker", *args], timeout=timeout)


def request(target: str, *, tls: ssl.SSLContext | None) -> tuple[int, dict[str, str], bytes]:
    connection: http.client.HTTPConnection
    if tls is None:
        connection = http.client.HTTPConnection("127.0.0.1", 8080, timeout=5)
    else:
        connection = http.client.HTTPSConnection("localhost", 8443, context=tls, timeout=5)
    try:
        connection.request("GET", target)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read(8192)
    finally:
        connection.close()


def probe(config: str, base: Path) -> dict[str, Any]:
    name = "ocwp-inventory-edge-" + uuid.uuid4().hex
    data = base / config
    root_ca = data / "caddy/pki/authorities/local/root.crt"
    upstream: ThreadingHTTPServer | None = None
    thread: threading.Thread | None = None
    thread_started = False
    started = time.monotonic()
    phase = "setup"
    last_health: dict[str, Any] = {"error": "not_attempted"}
    failure: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    cleanup: dict[str, Any] = {}
    try:
        data.mkdir(mode=0o700)
        upstream = ThreadingHTTPServer(("127.0.0.1", 8000), SyntheticUpstream)
        upstream.daemon_threads = True
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        thread_started = True
        phase = "start"
        docker(
            "run",
            "--detach",
            "--name",
            name,
            "--network",
            "host",
            "--add-host",
            "api:127.0.0.1",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            "/config:rw,nosuid,nodev,mode=1777",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,mode=1777",
            "--env",
            "OCWP_LAN_HOST=localhost",
            "--env",
            "XDG_DATA_HOME=/data",
            "--volume",
            f"{ROOT / 'infra/edge' / config}:/etc/caddy/Caddyfile:ro",
            "--volume",
            f"{ROOT / 'infra/edge/routes.caddy'}:/etc/caddy/routes.caddy:ro",
            "--volume",
            f"{data}:/data",
            IMAGE,
            "caddy",
            "run",
            "--config",
            "/etc/caddy/Caddyfile",
            "--adapter",
            "caddyfile",
        )
        tls = None
        ready = False
        phase = "readiness"
        while time.monotonic() - started < 30:
            try:
                if config.endswith(".lan"):
                    if not root_ca.is_file():
                        time.sleep(0.1)
                        continue
                    tls = ssl.create_default_context(cafile=str(root_ca))
                status = request("/health", tls=tls)[0]
                last_health = {"status": status}
                if status == 200:
                    ready = True
                    break
            except (OSError, ssl.SSLError, http.client.HTTPException) as error:
                last_health = safe_error(error)
            time.sleep(0.1)
        assert ready, "Caddy did not become ready under its actual supported config"
        phase = "version"
        version = docker("exec", name, "caddy", "version").strip()
        assert version.startswith("v2.11.7 "), "unexpected Caddy version"
        paths = [
            "/api/v1/inventory",
            "/api/v1/inventory/",
            "/api/v1/inventory/products/p/movements",
            "/%61pi/v1/inventory/products",
            "/api/v1/inventory%2Fproducts",
        ]
        # HTTP proxy absolute-form targets reach the same private backend path.
        paths.append(("https://localhost:8443" if tls else "http://127.0.0.1:8080") + paths[2])
        canaries = [f"{PRIVATE}-{i}" for i in range(len(paths))]
        phase = "forwarding"
        for path, canary in zip(paths, canaries, strict=True):
            target = path + "?before=" + canary + "&limit=50"
            status, headers, body = request(target, tls=tls)
            assert status == 200 and headers.get("Cache-Control") == "no-store"
            # Reverse proxy converts absolute-form to origin-form, preserving the
            # actual private query. Logging must not change the forwarded request.
            expected_target = target[target.index("/api/") :] if "://" in target else target
            assert json.loads(body)["target"] == expected_target
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)
        upstream = None
        phase = "error_responses"
        for path, canary in zip(paths, canaries, strict=True):
            status, headers, _ = request(path + "?before=" + canary, tls=tls)
            assert status in (502, 503) and headers.get("Cache-Control") == "no-store"
        status, _, _ = request("/api/v1/inventory-other?marker=" + UNRELATED, tls=tls)
        assert status in (502, 503)
        phase = "log_privacy"
        logs = docker("logs", name)
        proof = check_logs(logs, canaries, UNRELATED, paths)
        result = {
            "configuration": config,
            "version": version,
            "normal_forwarding_unchanged": True,
            "isolated_ca_verified": tls is not None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **proof,
        }
    except Exception as error:
        failure = {
            "configuration": config,
            "phase": phase,
            **safe_error(error),
            "last_health": last_health,
            "container": container_state(name),
        }
        if phase in {"start", "readiness", "version"}:
            failure["startup_log_hints"] = startup_log_hints(name)
    finally:
        upstream_errors = {}
        if upstream is not None:
            # shutdown waits for serve_forever; it deadlocks before a thread starts.
            actions = [("close", upstream.server_close)]
            if thread_started:
                actions.insert(0, ("shutdown", upstream.shutdown))
            if thread_started and thread is not None:
                actions.append(("join", lambda: thread.join(timeout=5)))
            for stage, action in actions:
                try:
                    action()
                except Exception as error:
                    upstream_errors[stage] = safe_error(error)
        cleanup["upstream"] = not upstream_errors
        if upstream_errors:
            cleanup["upstream_errors"] = upstream_errors
        try:
            docker("rm", "--force", name, timeout=30)
            cleanup["container"] = True
        except Exception as error:
            cleanup.update(container=False, container_error=safe_error(error))
    if failure is None and not (cleanup["upstream"] and cleanup["container"]):
        failure = {"configuration": config, "phase": "cleanup", "error": "cleanup_failed"}
    if failure is not None:
        failure["cleanup"] = cleanup
        raise EdgeProbeFailure(failure) from None
    assert result is not None
    return result


def main() -> None:
    destination = ROOT / "artifacts/inventory-read/edge-runtime-evidence.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, Any] = {
        "status": "incomplete",
        "run_id": uuid.uuid4().hex,
        "started_at": datetime.now(UTC).isoformat(),
        "image": IMAGE,
        "source_sha256": {},
        "cases": [],
    }
    # Invalidate prior success even if a required source cannot be read.
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    for name in (
        "infra/edge/Caddyfile",
        "infra/edge/Caddyfile.lan",
        "infra/edge/routes.caddy",
        "scripts/ci/inventory_edge_probe.py",
    ):
        evidence["source_sha256"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    if shutil.which("docker") is None:
        raise SystemExit(
            "BLOCKED: actual inventory edge proof requires Docker; no runtime result claimed"
        )
    docker("info", "--format", "{{.ServerVersion}}")
    docker("pull", IMAGE)
    failure: dict[str, Any] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="ocwp-inventory-edge-") as temporary:
            try:
                for config in ("Caddyfile", "Caddyfile.lan"):
                    evidence["cases"].append(probe(config, Path(temporary)))
                    destination.write_text(json.dumps(evidence, indent=2) + "\n")
            except EdgeProbeFailure as error:
                # Preserve the original before TemporaryDirectory.__exit__ can fail.
                failure = error.evidence
            except Exception as error:
                failure = {"phase": "probe_or_evidence", **safe_error(error)}
    except Exception as error:
        if failure is None:
            failure = {"phase": "temporary_directory", **safe_error(error)}
        failure.setdefault("cleanup", {}).update(
            temporary_directory=False, temporary_directory_error=safe_error(error)
        )
    if failure is not None:
        failure.setdefault("cleanup", {}).setdefault("temporary_directory", True)
        evidence.update(status="failed", failure=failure)
        destination.write_text(json.dumps(evidence, indent=2) + "\n")
        raise SystemExit("Actual Caddy proof failed; see bounded safe failure evidence") from None
    evidence["status"] = "complete"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Both Caddy configurations preserved forwarding and removed private error-log queries.")


if __name__ == "__main__":
    main()
