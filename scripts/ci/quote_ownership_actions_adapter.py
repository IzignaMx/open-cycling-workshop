"""Public metadata adapter for the one-shot guard. Imports never perform IO.

No token, proxy, redirect, retry or measurement execution is supported here.
The dedicated workflow also enforces an external timeout around this CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import time
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

from scripts.ci import quote_ownership_actions_guard as guard

GuardRefusal = guard.GuardRefusal
ACTIVE_STATES = ("in_progress", "queued", "requested", "waiting", "pending")
PHASE_NS = 45_000_000_000
SETUP_NS = 65_000_000_000
ROOT = Path(__file__).resolve().parents[2]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise GuardRefusal()


def _open(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open(
        request, timeout=timeout
    )


def _allowed(url: str) -> bool:
    if url == guard.API_ROOT or url == f"{guard.API_ROOT}/git/ref/heads/main":
        return True
    suffix = url.removeprefix(guard.API_ROOT)
    return (
        url.startswith(guard.API_ROOT + "/")
        and re.fullmatch(
            r"/(?:actions/runs/[1-9][0-9]{0,19}|actions/workflows/[1-9][0-9]{0,19}"
            r"(?:/runs\?per_page=100&page=1)?|git/commits/[0-9a-f]{40}|"
            r"actions/runs\?status=(?:in_progress|queued|requested|waiting|pending)&per_page=100&page=1)",
            suffix,
        )
        is not None
    )


def _remaining(deadline_ns: int, clock_ns: Callable[[], int]) -> float:
    now = clock_ns()
    guard._require(type(now) is int and type(deadline_ns) is int and now < deadline_ns)
    return min(5.0, (deadline_ns - now) / 1_000_000_000)


def fetch_response(
    url: str,
    deadline_ns: int,
    *,
    open_request: Callable[..., Any] = _open,
    clock_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    """Read one allowlisted response, bounded before JSON decode; no retries."""
    try:
        guard._require(type(url) is str and _allowed(url))
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ocwp-owned-measurement-once",
                "Accept-Encoding": "identity",
            },
        )
        with open_request(request, timeout=_remaining(deadline_ns, clock_ns)) as response:
            _remaining(deadline_ns, clock_ns)
            guard._equal(response.status, 200)
            guard._equal(response.geturl(), url)
            headers = response.headers
            guard._require(sum(len(k) + len(v) for k, v in headers.raw_items()) <= 16384)
            for key in (
                "Content-Type",
                "Content-Length",
                "Content-Encoding",
                "Transfer-Encoding",
                "Link",
                "Location",
            ):
                guard._require(len(headers.get_all(key, [])) <= 1)
            content_type = headers.get("Content-Type", "")
            guard._require(content_type.split(";", 1)[0].strip().lower() == "application/json")
            guard._require(headers.get("Content-Encoding", "identity").lower() == "identity")
            guard._require(headers.get("Location") is None)
            length = headers.get("Content-Length")
            transfer = headers.get("Transfer-Encoding")
            guard._require(transfer is None or (transfer.lower() == "chunked" and length is None))
            expected_length = None
            if length is not None:
                guard._require(re.fullmatch(r"0|[1-9][0-9]{0,5}", length) is not None)
                expected_length = int(length)
                guard._require(expected_length <= guard.MAX_RESPONSE_BYTES)
            chunks = bytearray()
            while True:
                _remaining(deadline_ns, clock_ns)
                chunk = response.read1(min(4096, guard.MAX_RESPONSE_BYTES + 1 - len(chunks)))
                _remaining(deadline_ns, clock_ns)
                guard._require(type(chunk) is bytes)
                if not chunk:
                    break
                guard._require(len(chunks) + len(chunk) <= guard.MAX_RESPONSE_BYTES)
                chunks.extend(chunk)
            guard._require(expected_length is None or len(chunks) == expected_length)
            result = dict(
                url=url,
                status=200,
                content_type="application/json",
                link=headers.get("Link", ""),
                body=bytes(chunks),
            )
        _remaining(deadline_ns, clock_ns)
        return result
    except Exception:
        raise GuardRefusal() from None


def _decimal(value: str) -> int:
    guard._require(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None)
    return int(value)


def _context(env: Mapping[str, str]) -> tuple[dict[str, object], dict[str, object]]:
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_REPOSITORY": guard.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(guard.REPOSITORY_ID),
        "GITHUB_JOB": "ownership-measurement",
        "GITHUB_REF": guard.REF,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_NUMBER": "1",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": f"{guard.REPOSITORY}/{guard.WORKFLOW_PATH}@{guard.REF}",
    }.items():
        guard._equal(env[name], value)
    pins = dict(
        workflow_id=_decimal(env["OCWP_EXPECTED_WORKFLOW_ID"]),
        source_sha=env["OCWP_EXPECTED_SOURCE_SHA"],
        tree_sha=env["OCWP_EXPECTED_TREE_SHA"],
    )
    guard._sha(pins["source_sha"])
    guard._sha(pins["tree_sha"])
    guard._equal(env["GITHUB_SHA"], pins["source_sha"])
    guard._equal(env["GITHUB_WORKFLOW_SHA"], pins["source_sha"])
    context = dict(
        repository=env["GITHUB_REPOSITORY"],
        ref=env["GITHUB_REF"],
        sha=env["GITHUB_SHA"],
        workflow_ref=env["GITHUB_WORKFLOW_REF"],
        workflow_sha=env["GITHUB_WORKFLOW_SHA"],
        event_name=env["GITHUB_EVENT_NAME"],
        run_id=_decimal(env["GITHUB_RUN_ID"]),
        run_number=1,
        run_attempt=1,
        authorization_id=guard.PROPOSAL_SHA256,
    )
    return context, pins


def setup_wrapper_budget(
    env: Mapping[str, str], *, clock_ns: Callable[[], int] = time.monotonic_ns
) -> tuple[str, str]:
    """TERM and KILL windows together never renew the original setup deadline."""
    try:
        now = clock_ns()
        deadline = _decimal(env["OCWP_OWNERSHIP_SETUP_DEADLINE_NS"])
        guard._require(now < deadline <= now + SETUP_NS)
        milliseconds = (deadline - now) // 1_000_000
        guard._require(milliseconds >= 2)
        kill = min(5000, milliseconds // 2)
        soft = min(45000, milliseconds - kill)
        return f"{soft // 1000}.{soft % 1000:03d}", f"{kill // 1000}.{kill % 1000:03d}"
    except Exception:
        raise GuardRefusal() from None


def collect_guard(
    env: Mapping[str, str],
    phase: str,
    *,
    fetcher: Callable[[str, int], dict[str, object]] = fetch_response,
    clock_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    try:
        guard._require(phase in ("prebuild", "setup"))
        context, pins = _context(env)
        now = clock_ns()
        deadline = now + PHASE_NS
        if phase == "setup":
            setup = _decimal(env["OCWP_OWNERSHIP_SETUP_DEADLINE_NS"])
            guard._require(now < setup <= now + SETUP_NS)
            deadline = min(deadline, setup)

        def get(url: str) -> dict[str, object]:
            _remaining(deadline, clock_ns)
            value = fetcher(url, deadline)
            _remaining(deadline, clock_ns)
            return value

        repo = guard._response(get(guard.API_ROOT), guard.API_ROOT)
        for key, value in {
            "id": guard.REPOSITORY_ID,
            "full_name": guard.REPOSITORY,
            "private": False,
            "visibility": "public",
            "archived": False,
            "disabled": False,
            "default_branch": "main",
        }.items():
            guard._equal(repo[key], value)
        workflow_url = f"{guard.API_ROOT}/actions/workflows/{pins['workflow_id']}"
        data: dict[str, object] = dict(
            context=context,
            pins=pins,
            current_run=get(f"{guard.API_ROOT}/actions/runs/{context['run_id']}"),
            workflow=get(workflow_url),
            commit=get(f"{guard.API_ROOT}/git/commits/{pins['source_sha']}"),
        )
        for state in ACTIVE_STATES:
            url = f"{guard.API_ROOT}/actions/runs?status={state}&per_page=100&page=1"
            page = guard._response(get(url), url)
            guard._equal(page["total_count"], 1 if state == "in_progress" else 0)
            runs = page["workflow_runs"]
            guard._require(type(runs) is list and len(runs) == (1 if state == "in_progress" else 0))
            if state == "in_progress":
                guard._run(runs[0], context, pins)
        data["main_ref"] = get(f"{guard.API_ROOT}/git/ref/heads/main")
        data["history_pages"] = [get(f"{workflow_url}/runs?per_page=100&page=1")]
        binding = guard.validate_guard(**data)
        _remaining(deadline, clock_ns)
        return binding
    except Exception:
        raise GuardRefusal() from None


def _directory_fd(path: Path, *, create: bool) -> int:
    """Walk every component without symlinks; caller owns returned descriptor."""
    guard._require(path.is_absolute() and ".." not in path.parts)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for component in path.parts[1:]:
            if create:
                with suppress(FileExistsError):
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _same_root(path: Path, descriptor: int) -> None:
    observed = _directory_fd(path, create=False)
    try:
        expected_stat, actual_stat = os.fstat(descriptor), os.fstat(observed)
        guard._require(
            (expected_stat.st_dev, expected_stat.st_ino) == (actual_stat.st_dev, actual_stat.st_ino)
        )
    finally:
        os.close(observed)


def _write_at(descriptor: int, name: str, value: dict[str, object]) -> tuple[int, int]:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    guard._require(len(encoded) <= 16384)
    file_descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor
    )
    with os.fdopen(file_descriptor, "wb") as output:
        output.write(encoded)
        observed = os.fstat(output.fileno())
        return observed.st_dev, observed.st_ino


def run_phase(
    env: Mapping[str, str],
    phase: str,
    evidence_root: Path,
    *,
    fetcher: Callable[[str, int], dict[str, object]] = fetch_response,
    clock_ns: Callable[[], int] = time.monotonic_ns,
) -> int:
    try:
        guard._require(phase in ("prebuild", "setup"))
        descriptor = _directory_fd(evidence_root, create=True)
    except Exception:
        return 1
    try:
        target = f"guard-{phase}.json"
        pending: dict[str, object] = dict(schema=1, phase=phase, status="unknown_spent")
        pending_identity = _write_at(descriptor, target, pending)
        try:
            binding = collect_guard(env, phase, fetcher=fetcher, clock_ns=clock_ns)
            result = dict(schema=1, phase=phase, status="passed", binding=binding)
            code = 0
        except Exception:
            result = dict(
                schema=1, phase=phase, status="refused_spent", reason="ownership_guard_refused"
            )
            code = 1
        _same_root(evidence_root, descriptor)
        observed = os.stat(target, dir_fd=descriptor, follow_symlinks=False)
        guard._require(
            stat.S_ISREG(observed.st_mode)
            and (observed.st_dev, observed.st_ino) == pending_identity
        )
        replacement = f"guard-{phase}.final.tmp"
        _write_at(descriptor, replacement, result)
        os.replace(replacement, target, src_dir_fd=descriptor, dst_dir_fd=descriptor)
        _same_root(evidence_root, descriptor)
        return code
    except Exception:
        return 1
    finally:
        os.close(descriptor)


def write_missing_guard_receipts(evidence_root: Path) -> int:
    """Always-step fallback: never overwrite an existing record or follow links."""
    try:
        descriptor = _directory_fd(evidence_root, create=True)
    except Exception:
        return 1
    try:
        for phase in ("prebuild", "setup"):
            _same_root(evidence_root, descriptor)
            name = f"guard-{phase}.json"
            try:
                observed = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                guard._require(stat.S_ISREG(observed.st_mode))
            except FileNotFoundError:
                _write_at(
                    descriptor,
                    name,
                    dict(schema=1, phase=phase, status="unknown_spent", reason="guard_not_started"),
                )
        _same_root(evidence_root, descriptor)
        return 0
    except Exception:
        return 1
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixed public once-only metadata guard")
    parser.add_argument("--phase", choices=("prebuild", "setup"))
    parser.add_argument("--evidence")
    parser.add_argument("--write-missing-guard-evidence", action="store_true")
    args = parser.parse_args()
    if args.write_missing_guard_evidence:
        if args.phase is not None or args.evidence is not None:
            return 1
        return write_missing_guard_receipts(ROOT / "artifacts/quote-ownership")
    if args.phase is None:
        return 1
    if args.evidence != f"artifacts/quote-ownership/guard-{args.phase}.json":
        return 1
    return run_phase(os.environ, args.phase, ROOT / "artifacts/quote-ownership")


if __name__ == "__main__":
    raise SystemExit(main())
