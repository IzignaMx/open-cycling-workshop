"""One fixed repair proposal from frozen source copies; no host-source application."""

from __future__ import annotations

import difflib
import os
import re
import resource
import selectors
import signal
import stat
import subprocess
import time
from pathlib import Path

import pytest

from scripts.ci.quote_static_repair import (
    BEFORE_HASHES,
    BEFORE_SIZES,
    CONFIG_HASH,
    FILE_LIMIT,
    INPUT_ROOT,
    MARKER,
    MAX_DIAGNOSTICS,
    PATHS,
    REPORT_PATH,
    RULES,
    SOURCE_TOTAL_LIMIT,
    TARGET_COMMIT,
    TARGET_TREE,
    TOOL_OUTPUT_LIMIT,
    digest,
    encode_receipt,
)

RUFF = "/app/.venv/bin/ruff"
TOOL_SECONDS = 3


class RepairToolFailure(RuntimeError):
    pass


def _file_limit() -> None:
    # Ruff must rewrite files larger than 16 KiB; its pipe has a separate 16 KiB cap.
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))


def _read_source(path: Path) -> bytes:
    status = path.lstat()
    if not stat.S_ISREG(status.st_mode) or not 0 < status.st_size <= FILE_LIMIT:
        raise RepairToolFailure("source_shape")
    with path.open("rb") as handle:
        value = handle.read(FILE_LIMIT + 1)
    if len(value) != status.st_size or not value.endswith(b"\n") or b"\x00" in value:
        raise RepairToolFailure("source_bytes")
    value.decode("utf-8", errors="strict")
    return value


def _sources(root: Path) -> list[bytes]:
    values = [_read_source(root / path) for path in PATHS]
    if sum(map(len, values)) > SOURCE_TOTAL_LIMIT:
        raise RepairToolFailure("source_total")
    if digest(_read_source(root / "ruff.toml")) != CONFIG_HASH:
        raise RepairToolFailure("config_changed")
    return values


def _run(root: Path, arguments: tuple[str, ...]) -> tuple[int, bytes]:
    """A fixed Ruff invocation; bounded pipe reads, lifetime, kill and direct reap."""
    captured = bytearray()
    child = subprocess.Popen(
        (RUFF, *arguments), cwd=root, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
        start_new_session=True, preexec_fn=_file_limit,
        env={
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
            "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1", "RAYON_NUM_THREADS": "1",
        },
    )
    deadline = time.monotonic() + TOOL_SECONDS
    try:
        if child.stdout is None:
            raise RepairToolFailure("pipe_missing")
        os.set_blocking(child.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while selector.get_map() or child.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RepairToolFailure("tool_timeout")
                for key, _events in selector.select(timeout=min(0.05, remaining)):
                    data = os.read(key.fd, min(4096, TOOL_OUTPUT_LIMIT - len(captured)))
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    captured.extend(data)
                    if len(captured) >= TOOL_OUTPUT_LIMIT:
                        raise RepairToolFailure("tool_output_cap")
            if time.monotonic() >= deadline:
                raise RepairToolFailure("tool_timeout")
        returncode = child.wait(timeout=1)
        if returncode not in (0, 1):
            raise RepairToolFailure("tool_exit")
        return returncode, bytes(captured)
    except BaseException:
        # Kill the group even if the direct child exited but a descendant holds
        # its stdout pipe. A kill/reap failure propagates as a failing protocol.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=1)
        raise
    finally:
        if child.stdout is not None:
            child.stdout.close()


def _diagnostics(tool: int, returncode: int, output: bytes, root: Path) -> dict[str, object]:
    records: list[list[int]] = []
    seen: set[tuple[int, int, int]] = set()
    unsupported, unparsed = 0, 0
    remaining: int | None = None
    for text in output.decode("utf-8", errors="replace").splitlines():
        if not text:
            continue
        path, number, rule = "", "0", ""
        if tool in (0, 2):
            match = re.fullmatch(r"(.+):([0-9]+):[0-9]+: ([A-Z]+[0-9]+) .+", text)
            if match:
                path, number, rule = match.groups()
            elif text == "All checks passed!":
                remaining = 0
                continue
            elif match := re.fullmatch(r"Found ([0-9]+) errors?\.", text):
                remaining = int(match[1]) if len(match[1]) <= 4 else MAX_DIAGNOSTICS + 1
                continue
            elif match := re.fullmatch(
                r"Found [0-9]+ errors? \([0-9]+ fixed, ([0-9]+) remaining\)\.", text,
            ):
                remaining = int(match[1]) if len(match[1]) <= 4 else MAX_DIAGNOSTICS + 1
                continue
            else:
                unparsed += 1
                continue
        elif text.startswith("Would reformat: "):
            path, rule = text.removeprefix("Would reformat: "), "format"
        elif re.fullmatch(r"[0-9]+ files? (?:left unchanged|already formatted|reformatted)(?:, [0-9]+ files? left unchanged)?", text):
            continue
        else:
            unparsed += 1
            continue
        path = path.removeprefix(str(root) + "/")
        line = int(number) if len(number) <= 7 else -1
        if path not in PATHS or rule not in RULES or not 0 <= line <= 1_000_000:
            unsupported += 1
            continue
        record = (PATHS.index(path), line, RULES.index(rule))
        if record not in seen:
            seen.add(record)
            records.append(list(record))
    if len(records) > MAX_DIAGNOSTICS or (remaining is not None and remaining > MAX_DIAGNOSTICS):
        raise RepairToolFailure("diagnostic_count_cap")
    if tool in (1, 3) and returncode == 0:
        remaining = 0
    complete = remaining == len(records) and unsupported == 0
    return {
        "tool": tool, "returncode": returncode, "output_bytes": len(output),
        "diagnostics": records, "unsupported_lines": unsupported,
        "unparsed_lines": unparsed, "diagnostics_complete": complete,
        "reported_remaining": remaining,
    }


def _invoke(state: dict[str, object], tool: int, arguments: tuple[str, ...]) -> None:
    assert len(state["tools"]) == tool
    root = state["root"]
    returncode, output = _run(root, arguments)
    state["tools"].append(_diagnostics(tool, returncode, output, root))
    _sources(root)


@pytest.fixture(scope="module")
def repair_state(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    if (Path.cwd() != Path("/app")
            or os.environ.get("OCWP_QUOTE_SERVICE_INITIAL") != "contained"):
        pytest.fail("repair_context", pytrace=False)
    return {"root": tmp_path_factory.mktemp("fixed-static-repair"), "before": [], "tools": []}


def test_copy_frozen_sources(repair_state: dict[str, object]) -> None:
    root = repair_state["root"]
    values = _sources(INPUT_ROOT)
    assert [digest(data) for data in values] == list(BEFORE_HASHES)
    assert [len(data) for data in values] == list(BEFORE_SIZES)
    for path, data in zip(PATHS, values, strict=True):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data)
    (root / "ruff.toml").write_bytes(_read_source(INPUT_ROOT / "ruff.toml"))
    repair_state["before"] = values
    assert _sources(root) == values


def test_record_safe_ruff_fixes(repair_state: dict[str, object]) -> None:
    assert len(repair_state["before"]) == 19
    _invoke(repair_state, 0, (
        "check", "--config", "ruff.toml", "--no-cache", "--output-format", "concise",
        "--fix", "--no-unsafe-fixes", *PATHS,
    ))


def test_record_ruff_formatting(repair_state: dict[str, object]) -> None:
    _invoke(repair_state, 1, ("format", "--config", "ruff.toml", "--no-cache", *PATHS))
    assert repair_state["tools"][1]["returncode"] == 0


def test_record_post_repair_lint(repair_state: dict[str, object]) -> None:
    _invoke(repair_state, 2, (
        "check", "--config", "ruff.toml", "--no-cache", "--output-format", "concise", *PATHS,
    ))


def test_record_post_repair_format(repair_state: dict[str, object]) -> None:
    _invoke(repair_state, 3, ("format", "--config", "ruff.toml", "--no-cache", "--check", *PATHS))


def test_export_patch_then_require_clean_final_checks(
    repair_state: dict[str, object], capfd: pytest.CaptureFixture[str],
) -> None:
    assert len(repair_state["tools"]) == 4
    after = _sources(repair_state["root"])
    hunks = []
    for path, old, new in zip(PATHS, repair_state["before"], after, strict=True):
        if old != new:
            hunks.extend(difflib.unified_diff(
                old.decode("utf-8").splitlines(keepends=True),
                new.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{path}", tofile=f"b/{path}", n=3,
            ))
    patch = "".join(hunks)
    value = {
        "schema": 1, "scope": "repair_proposal_only", "target_commit": TARGET_COMMIT,
        "target_tree": TARGET_TREE, "before_sha256": list(BEFORE_HASHES),
        "after_sha256": [digest(data) for data in after], "after_bytes": [len(data) for data in after],
        "tools": repair_state["tools"], "patch": patch, "patch_sha256": digest(patch.encode("utf-8")),
    }
    envelope = encode_receipt(value)
    Path(REPORT_PATH).write_bytes(envelope + b"\n")
    clean = all(repair_state["tools"][index]["returncode"] == 0 for index in (2, 3))
    if not clean:
        try:
            with capfd.disabled():
                os.write(1, b"\n" + MARKER + envelope + b"\n")
        except OSError:
            pass
    # Export first so a still-red result yields a reviewable proposal. Both final
    # checks are mandatory; neither a completed capture nor safe-fix exit 1 is clean.
    assert clean, "repair_proposal_has_remaining_findings"
