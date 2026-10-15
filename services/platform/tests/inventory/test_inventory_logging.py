"""Exercise the actual Uvicorn formatter and HTTP protocol, never fake access logs."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from cycling_workshop.api.middleware import configure_logging
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.security import SessionTokenService

ROOT = Path(__file__).resolve().parents[4]
NAMESPACE = "/api/v1/inventory"
PRODUCT = "00000000-0000-7000-8000-0000000003e9"
CANARY = "private-inventory-query-canary"


def bearer(capabilities: list[str]) -> dict[str, str]:
    token = SessionTokenService(secret="inventory-api-test-secret-long-enough").issue(
        Principal(
            user_id="writer",
            organization_id="org-1",
            location_id="loc-1",
            capabilities=frozenset(capabilities),
        )
    )
    return {"Authorization": "Bearer " + token, "X-Request-ID": "private-request-id-canary"}


def test_logging_filter_installation_is_idempotent_and_preserves_logger_setup() -> None:
    logger = logging.getLogger("uvicorn.access")
    before_handlers = list(logger.handlers)
    before_propagate = logger.propagate
    before_disabled = logger.disabled
    configure_logging()
    configure_logging()
    filters = [item for item in logger.filters if type(item).__name__ == "InventoryAccessFilter"]
    assert len(filters) == 1
    assert logger.handlers == before_handlers
    assert logger.propagate == before_propagate
    assert logger.disabled == before_disabled


def test_actual_uvicorn_inventory_access_and_error_logs_hide_queries(tmp_path: Path) -> None:
    # Real loopback HTTP and Uvicorn's default AccessFormatter. File output avoids
    # pipe backpressure masking long query regressions. All data is synthetic.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = tmp_path / "uvicorn.log"
    with log_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "services.platform.tests.inventory.logging_probe_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-use-colors",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT / 'services/platform/src'}"},
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False
            ) as client:
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        pytest.fail("Uvicorn failed to start:\n" + log_path.read_text())
                    try:
                        if client.get("/health/live").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    if time.monotonic() >= deadline:
                        pytest.fail("Uvicorn readiness deadline exceeded")
                    time.sleep(0.05)
                reader = bearer(["inventory.read"])
                cases = [
                    (f"{NAMESPACE}/products?location_id=loc-1&unused={CANARY}", reader, 200),
                    (f"{NAMESPACE}/products?location_id=loc-1&unused={CANARY}", {}, 401),
                    (f"{NAMESPACE}/products?location_id=loc-1&unused={CANARY}", bearer([]), 403),
                    (f"{NAMESPACE}/products?location_id=loc-1&limit={CANARY}", reader, 422),
                    (f"{NAMESPACE}/products/{PRODUCT}/movements?before={CANARY}", reader, 422),
                    (f"{NAMESPACE}/products/{PRODUCT}/movements?{CANARY}=value", reader, 422),
                    (
                        f"{NAMESPACE}/products/{PRODUCT}/movements?before={CANARY}&before=again",
                        reader,
                        422,
                    ),
                    (
                        f"{NAMESPACE}/products/{PRODUCT}/movements?before={CANARY + 'x' * 2049}",
                        reader,
                        422,
                    ),
                    (f"{NAMESPACE}/_logging/internal-error?before={CANARY}", reader, 500),
                    (f"{NAMESPACE}/_logging/database-error?before={CANARY}", reader, 503),
                    (f"{NAMESPACE}/_logging/budget-error?before={CANARY}", reader, 503),
                    (f"{NAMESPACE}?before={CANARY}", reader, 404),
                    (f"{NAMESPACE}/?before={CANARY}", reader, 404),
                    (f"{NAMESPACE}/missing?before={CANARY}", reader, 404),
                ]
                # Query redaction must not mutate ASGI query bytes or validation.
                response = client.get(f"{NAMESPACE}/_logging/scope?before={CANARY}", headers=reader)
                assert response.json() == {"query": "before=" + CANARY}
                statuses = []
                for path, headers, expected in cases:
                    response = client.get(path, headers=headers)
                    statuses.append((response.status_code, expected))
                    assert response.headers.get("cache-control") == "no-store"
                    assert "private-request-id-canary" not in str(response.headers) + response.text
                unrelated = client.get("/api/v1/inventory-other?before=ordinary-query-canary")
                assert unrelated.json() == {"query": "before=ordinary-query-canary"}
                assert "cache-control" not in unrelated.headers
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    logs = log_path.read_text(encoding="utf-8")
    assert CANARY not in logs, logs
    for forbidden in (
        "private-request-id-canary",
        "private-driver-error-canary",
        "private-sql-parameter-canary",
    ):
        assert forbidden not in logs
    assert "GET /api/v1/inventory-other?before=ordinary-query-canary HTTP/1.1" in logs
    assert "inventory request failed" in logs and "RuntimeError" in logs
    for status in (200, 401, 403, 404, 422, 500, 503):
        assert f'HTTP/1.1" {status}' in logs
    assert statuses == [(expected, expected) for _, expected in statuses]
