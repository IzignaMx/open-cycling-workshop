"""Six real static/contract commands; run only inside the reviewed contained selection."""

from __future__ import annotations

import json
import os
import re
import resource
import signal
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest

from scripts.ci.quote_capacity_micro import (
    LIMIT,
    STATIC_ALLOWED_PATHS,
    STATIC_ALLOWED_RULES,
    STATIC_FAILURE_LIMIT,
    STATIC_FAILURE_MARKER,
    STATIC_PATHS,
    STATIC_RUFF_CODE_PATTERN,
    STATIC_RUFF_FAILURE_LIMIT,
    STATIC_RUFF_MESSAGE_LIMIT,
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
    ),
    (RUFF, "format", "--config", "ruff.toml", "--check", "--no-cache", *STATIC_PATHS),
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
        *STATIC_PATHS[:6],
    ),
    (PYTHON, "scripts/contracts/export_openapi.py", "--check"),
    (PYTHON, "scripts/contracts/generate_ts_client.py", "--check"),
)
# Per-command ceilings, not an additive allocation: the outer 20 seconds includes all six.
TOOL_SECONDS = (2, 3, 3, 12, 3, 2)


def _limit_output() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))


def _summarize(tool: int, output: bytes) -> tuple[list[dict[str, object]], int, int, int | None]:
    """Retain source-bound Ruff messages; other tools keep their closed summaries."""
    rows: list[dict[str, object]] = []
    if tool == 1:
        seen_ruff: set[tuple[str, int, int, str, str]] = set()
        unparsed, duplicates = 0, 0
        reported = None
        lines = output.split(b"\n")
        if lines[-1]:
            unparsed += 1  # A partial trailing line is not a complete diagnostic.
        for raw in lines[:-1]:
            if not raw:
                continue
            try:
                text = raw.decode("utf-8", errors="strict")
            except UnicodeError:
                unparsed += 1
                continue
            summary = re.fullmatch(r"Found ([0-9]{1,5}) errors?\.", text)
            if summary:
                count = int(summary[1])
                if reported is not None or not 1 <= count <= LIMIT:
                    unparsed += 1
                else:
                    reported = count
                continue
            match = re.fullmatch(r"(.+):([0-9]{1,7}):([0-9]{1,7}): ([^ :]{1,64}):? (.+)", text)
            if match is None:
                unparsed += 1
                continue
            path, number, column_number, rule, message = match.groups()
            path = path.removeprefix("/app/")
            line, column = int(number), int(column_number)
            if (
                path not in STATIC_PATHS
                or not 1 <= line <= 1_000_000
                or not 1 <= column <= 1_000_000
                or re.fullmatch(STATIC_RUFF_CODE_PATTERN, rule) is None
                or not message.isprintable()
                or not 1 <= len(message.encode("utf-8")) <= STATIC_RUFF_MESSAGE_LIMIT
            ):
                unparsed += 1
                continue
            key = (path, line, column, rule, message)
            if key in seen_ruff:
                duplicates += 1
                continue
            seen_ruff.add(key)
            rows.append(
                {"path": path, "line": line, "column": column, "rule": rule, "message": message}
            )
        return rows, duplicates, unparsed, reported

    seen: set[tuple[str, int, str]] = set()
    unparsed = 0
    for text in output.decode("utf-8", errors="replace").splitlines():
        if not text:
            continue
        path, line, rule = "", 0, ""
        if tool == 0:
            if text.startswith("  - "):
                path, rule = text[4:], "missing"
            elif text == "LICENSE does not contain GNU AGPL text":
                path, rule = "LICENSE", "license"
        elif tool == 2 and text.startswith("Would reformat: "):
            path, rule = text.removeprefix("Would reformat: "), "format"
        elif tool == 3:
            match = re.fullmatch(r"(.+):([0-9]+):[0-9]+: error: .*\[([a-z-]+)\]", text)
            if match:
                path, number, rule = match.groups()
                line = int(number) if len(number) <= 7 else -1
        elif tool == 4 and text == (
            "OpenAPI drift detected: regenerate packages/api-client/openapi.json"
        ):
            path, rule = "packages/api-client/openapi.json", "contract"
        elif tool == 5 and text == "TypeScript API client drift detected: regenerate generated.ts":
            path, rule = "packages/api-client/src/generated.ts", "contract"
        path = path.removeprefix("/app/")
        if (
            path not in STATIC_ALLOWED_PATHS[tool]
            or rule not in STATIC_ALLOWED_RULES[tool]
            or not 0 <= line <= 1_000_000
        ):
            unparsed += 1
            continue
        key = (path, line, rule)
        if key not in seen:
            seen.add(key)
            if len(rows) < 12:
                rows.append({"path": path, "line": line, "rule": rule})
    return rows, max(0, len(seen) - len(rows)), unparsed, None


def _check(tool: int, capfd: pytest.CaptureFixture[str]) -> None:
    if ROOT != Path("/app") or os.environ.get("OCWP_QUOTE_SERVICE_INITIAL") != "contained":
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
    rows, omitted, unparsed, reported = _summarize(tool, captured)
    value = {
        "schema": 1,
        "tool": tool,
        "kind": kind,
        "returncode": returncode,
        "output_bytes": min(size, LIMIT),
        "omitted": omitted,
        "unparsed_lines": unparsed,
        "diagnostics": rows,
    }
    marker_limit = STATIC_FAILURE_LIMIT
    if tool == 1:
        marker_limit = STATIC_RUFF_FAILURE_LIMIT
        # Reserve 1 KiB for all fixed keys, bounded counters, reasons and framing.
        # Keep a whole-row prefix; serialized escaping is included in the budget.
        retained: list[dict[str, object]] = []
        row_bytes = 2  # JSON array brackets.
        for row in rows:
            encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("ascii")
            needed = len(encoded) + (1 if retained else 0)
            if row_bytes + needed > marker_limit - 1024:
                value["omitted"] += len(rows) - len(retained)
                break
            retained.append(row)
            row_bytes += needed
        value["diagnostics"] = retained
        value["reported_diagnostics"] = reported
        reasons = []
        if kind != 1 or returncode != 1:
            reasons.append("tool_status")
        if value["output_bytes"] == LIMIT:
            reasons.append("output_limit")
        if unparsed:
            reasons.append("unparsed_lines")
        if value["omitted"]:
            reasons.append("omitted_rows")
        if reported is None or reported != len(retained) + value["omitted"]:
            reasons.append("summary_mismatch")
        value["complete"] = not reasons
        value["incomplete_reasons"] = reasons
    marker = (
        STATIC_FAILURE_MARKER
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )
    if len(marker) <= marker_limit:
        # Emit this closed marker only. Never release captured tool/pytest output.
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
