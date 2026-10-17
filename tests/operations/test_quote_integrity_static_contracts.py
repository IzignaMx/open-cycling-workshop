"""Six real static/contract commands; run only inside the reviewed contained selection."""

from __future__ import annotations

import base64
import json
import os
import resource
import signal
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest

from scripts.ci.quote_capacity_micro import (
    LIMIT,
    STATIC_FAILURE_LIMIT,
    STATIC_FAILURE_MARKER,
    STATIC_PATHS,
)

ROOT = Path(__file__).resolve().parents[2]
PYTHON = "/app/.venv/bin/python"
RUFF = "/app/.venv/bin/ruff"
MYPY = "/app/.venv/bin/mypy"
COMMANDS = (
    (PYTHON, "scripts/ci/verify_repository.py"),
    (
        RUFF,
        "check",
        "--config",
        "ruff.toml",
        "--no-cache",
        "--output-format",
        "concise",
        *STATIC_PATHS,
        "scripts/ci/quote_integration_checks.py",
        "scripts/ci/quote_integrity_checks.py",
        "scripts/ci/quote_integrity_postgres.py",
        "tests/operations/test_quote_integrity_static_contracts.py",
        "tests/operations/test_quote_integrity_selection.py",
    ),
    (
        RUFF,
        "format",
        "--config",
        "ruff.toml",
        "--check",
        "--diff",
        "--no-cache",
        *STATIC_PATHS,
        "scripts/ci/quote_integration_checks.py",
        "scripts/ci/quote_integrity_checks.py",
        "scripts/ci/quote_integrity_postgres.py",
        "tests/operations/test_quote_integrity_static_contracts.py",
        "tests/operations/test_quote_integrity_selection.py",
    ),
    (
        MYPY,
        "--config-file",
        "mypy.ini",
        "--cache-dir",
        "/dev/null",
        "--no-incremental",
        "--no-pretty",
        "--no-color-output",
        "--show-column-numbers",
        "--no-error-summary",
        "--show-error-codes",
        *(path for path in STATIC_PATHS if path.startswith("services/platform/src/")),
    ),
    (PYTHON, "scripts/contracts/export_openapi.py", "--check"),
    (PYTHON, "scripts/contracts/generate_ts_client.py", "--check"),
)
# Per-command ceilings, not an additive allocation: the outer 20 seconds includes all six.
TOOL_SECONDS = (2, 3, 3, 12, 6, 2)


def _limit_output() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))


def _check(tool: int, capfd: pytest.CaptureFixture[str]) -> None:
    if Path("/app") != ROOT or os.environ.get("OCWP_QUOTE_SERVICE_INITIAL") != "contained":
        pytest.fail("static_tool_context", pytrace=False)
    kind, returncode = 1, None
    with tempfile.TemporaryFile() as output:
        try:
            child = subprocess.Popen(
                COMMANDS[tool],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
                start_new_session=True,
                preexec_fn=_limit_output,
                env={
                    "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "NO_COLOR": "1",
                    "RAYON_NUM_THREADS": "1",
                },
            )
        except OSError:
            kind = 4
        else:
            try:
                returncode = child.wait(timeout=TOOL_SECONDS[tool])
            except subprocess.TimeoutExpired:
                kind = 2
                with suppress(ProcessLookupError):
                    os.killpg(child.pid, signal.SIGKILL)
                # A reap failure propagates as a failing protocol. The outer container
                # guard still owns descendants, cancellation and absence verification.
                returncode = child.wait(timeout=1)
        size = os.fstat(output.fileno()).st_size
        output.seek(0)
        captured = output.read(LIMIT)
    if size >= LIMIT:
        kind = 3
    if kind == 1 and returncode == 0:
        return
    value = {
        "schema": 2,
        "tool": tool,
        "kind": kind,
        "returncode": returncode,
        "output_bytes": len(captured),
        "output_truncated": size >= LIMIT,
        "output_base64": base64.b64encode(captured).decode("ascii"),
    }
    marker = (
        STATIC_FAILURE_MARKER
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )
    if len(marker) <= STATIC_FAILURE_LIMIT:
        # Retain public-source tool bytes only in the bounded marker, not pytest logs.
        with suppress(OSError), capfd.disabled():
            os.write(1, b"\n" + marker)
    pytest.fail("static_tool_failed", pytrace=False)


def test_repository_contract(capfd: pytest.CaptureFixture[str]) -> None:
    _check(0, capfd)


def test_python_lint(capfd: pytest.CaptureFixture[str]) -> None:
    _check(1, capfd)


def test_python_format(capfd: pytest.CaptureFixture[str]) -> None:
    _check(2, capfd)


def test_production_types(capfd: pytest.CaptureFixture[str]) -> None:
    _check(3, capfd)


def test_openapi_contract(capfd: pytest.CaptureFixture[str]) -> None:
    _check(4, capfd)


def test_generated_client_contract(capfd: pytest.CaptureFixture[str]) -> None:
    _check(5, capfd)
