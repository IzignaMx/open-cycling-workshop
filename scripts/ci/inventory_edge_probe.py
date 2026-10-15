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
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, check=True
    )
    return result.stdout + result.stderr


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
    data.mkdir(mode=0o700)
    root_ca = data / "caddy/pki/authorities/local/root.crt"
    upstream: ThreadingHTTPServer | None = ThreadingHTTPServer(
        ("127.0.0.1", 8000), SyntheticUpstream
    )
    upstream.daemon_threads = True
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    started = time.monotonic()
    try:
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
        while time.monotonic() - started < 30:
            try:
                if config.endswith(".lan"):
                    if not root_ca.is_file():
                        time.sleep(0.1)
                        continue
                    tls = ssl.create_default_context(cafile=str(root_ca))
                if request("/health", tls=tls)[0] == 200:
                    ready = True
                    break
            except (OSError, ssl.SSLError, http.client.HTTPException):
                pass
            time.sleep(0.1)
        assert ready, "Caddy did not become ready under its actual supported config"
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
        for path, canary in zip(paths, canaries, strict=True):
            status, headers, _ = request(path + "?before=" + canary, tls=tls)
            assert status in (502, 503) and headers.get("Cache-Control") == "no-store"
        status, _, _ = request("/api/v1/inventory-other?marker=" + UNRELATED, tls=tls)
        assert status in (502, 503)
        logs = docker("logs", name)
        proof = check_logs(logs, canaries, UNRELATED, paths)
        return {
            "configuration": config,
            "version": version,
            "normal_forwarding_unchanged": True,
            "isolated_ca_verified": tls is not None,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **proof,
        }
    finally:
        if upstream is not None:
            upstream.shutdown()
            upstream.server_close()
            thread.join(timeout=5)
        docker("rm", "--force", name, timeout=30)


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
    with tempfile.TemporaryDirectory(prefix="ocwp-inventory-edge-") as temporary:
        for config in ("Caddyfile", "Caddyfile.lan"):
            evidence["cases"].append(probe(config, Path(temporary)))
            destination.write_text(json.dumps(evidence, indent=2) + "\n")
    evidence["status"] = "complete"
    destination.write_text(json.dumps(evidence, indent=2) + "\n")
    print("Both Caddy configurations preserved forwarding and removed private error-log queries.")


if __name__ == "__main__":
    main()
