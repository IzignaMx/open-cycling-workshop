"""Real Uvicorn protocol/formatter privacy, not fabricated log qualification."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from cycling_workshop.api.middleware import configure_logging

ROOT = Path(__file__).resolve().parents[4]
CANARY = "private-quote-query-canary"
HEADER_CANARY = "private-quote-header-canary"


def test_quote_log_filter_installation_is_idempotent_and_preserves_logger() -> None:
    logger = logging.getLogger("uvicorn.access")
    before = (list(logger.handlers), logger.propagate, logger.disabled, logger.level)
    configure_logging()
    configure_logging()
    filters = [item for item in logger.filters if type(item).__name__ == "QuoteAccessFilter"]
    assert len(filters) == 1
    assert (list(logger.handlers), logger.propagate, logger.disabled, logger.level) == before


def test_actual_uvicorn_quote_queries_and_error_context_remain_private(tmp_path: Path) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    path = tmp_path / "uvicorn.log"
    with path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "services.platform.tests.quotes.logging_probe_app:app",
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
                    assert process.poll() is None, "Uvicorn startup failed"
                    try:
                        if client.get("/health/live").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    assert time.monotonic() < deadline, "Uvicorn readiness deadline exceeded"
                    time.sleep(0.05)
                roots = [
                    "/api/v1/quotes",
                    "/api/v1/service-orders/order-a/quotes",
                    "/api/v1/%71uotes",
                    "/api%2Fv1%2Fquotes",
                    "/api/v1/service-orders/order%20a/%71uotes",
                    "/api/v1/service-orders/order%3Fa/quotes",
                    "/api/v1/service-orders/order%23a/quotes",
                    "/api/v1/service-orders/order%252Fa/quotes",
                ]
                for root in roots:
                    # Body proves untouched forwarding; redact only the access record.
                    response = client.get(
                        root + "/_logging/scope?note=" + CANARY,
                        headers={"X-Request-ID": HEADER_CANARY},
                    )
                    assert response.status_code == 200
                    assert response.json() == {"query": "note=" + CANARY}
                    for suffix, status in [
                        ("/missing", 404),
                        ("/_logging/internal", 500),
                        ("/_logging/http", 403),
                        ("/_logging/api", 409),
                    ]:
                        response = client.get(
                            root + suffix + "?" + CANARY + "=" + CANARY,
                            headers={"X-Request-ID": HEADER_CANARY},
                        )
                        assert response.status_code == status
                        assert response.headers.get("cache-control") == "no-store"
                        assert response.headers["x-request-id"].startswith("req-")
                        assert CANARY not in response.text and HEADER_CANARY not in str(
                            response.headers
                        )
                response = client.get("/api/v1/quotes-other?note=ordinary-quote-query")
                assert response.json() == {"query": "note=ordinary-quote-query"}
                assert "cache-control" not in response.headers
                # A double-encoded fixed prefix is NOT a quote namespace after one ASGI decode.
                response = client.get("/api/v1/%2571uotes?note=ordinary-double-encoded-query")
                assert response.status_code == 404 and "cache-control" not in response.headers
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    logs = path.read_text()
    assert CANARY not in logs
    assert HEADER_CANARY not in logs
    assert "private-quote-exception-canary" not in logs
    assert "quote request failed" in logs
    assert "ordinary-quote-query" in logs and "ordinary-double-encoded-query" in logs
    assert "Traceback" not in logs
