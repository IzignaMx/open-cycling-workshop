"""Finite, quote-only hosted containment preflight. There is no maximum mode."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import resource
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from types import FrameType
from typing import cast
from uuid import uuid4

LIMIT = 16 * 1024
FIELDS = (
    "memory.max",
    "memory.swap.max",
    "cpu.max",
    "pids.max",
    "memory.current",
    "memory.peak",
    "cpu.stat",
    "memory.events",
    "pids.events",
)
PROBE = "set -eu; cat /proc/self/cgroup; " + "".join(
    f"printf '\\n---{field}---\\n'; cat /sys/fs/cgroup/{field}; " for field in FIELDS
)


class ProofFailure(RuntimeError):
    def __init__(self, reason: str, *, returncode: int | None = None) -> None:
        super().__init__(reason)
        self.returncode = returncode


def identifier(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ProofFailure("container_identity")
    return value


def integer(value: str) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ProofFailure("counter_invalid")
    return int(value)


def parse_probe(raw: str, memory_mib: int, pids: int) -> dict[str, int]:
    try:
        sections = re.split(r"\n---([a-z.]+)---\n", raw.strip())
        if sections[0].strip() != "0::/" or sections[1::2] != list(FIELDS):
            raise ProofFailure("cgroup_unavailable")
        values = dict(zip(sections[1::2], (v.strip() for v in sections[2::2]), strict=True))
        maximum = memory_mib * 1024 * 1024
        if (
            values["memory.max"] != str(maximum)
            or values["memory.swap.max"] != "0"
            or values["cpu.max"] != "100000 100000"
            or values["pids.max"] != str(pids)
        ):
            raise ProofFailure("limits_not_enforced")
        peak = integer(values["memory.peak"])
        if not 0 <= integer(values["memory.current"]) <= peak <= maximum:
            raise ProofFailure("memory_counter_invalid")
        counters = {}
        for field in ("cpu.stat", "memory.events", "pids.events"):
            pairs = [line.split() for line in values[field].splitlines()]
            if any(len(pair) != 2 for pair in pairs) or len({p[0] for p in pairs}) != len(pairs):
                raise ProofFailure("counter_invalid")
            counters[field] = {key: integer(value) for key, value in pairs}
        if not {"usage_usec", "user_usec", "system_usec"} <= counters["cpu.stat"].keys():
            raise ProofFailure("cpu_unavailable")
        if not {"oom", "oom_kill", "max"} <= counters["memory.events"].keys():
            raise ProofFailure("memory_events_unavailable")
        if "max" not in counters["pids.events"]:
            raise ProofFailure("pids_events_unavailable")
        if any(
            value
            for field in ("memory.events", "pids.events")
            for value in counters[field].values()
        ):
            raise ProofFailure("resource_pressure")
        return {"cpu_usec": counters["cpu.stat"]["usage_usec"], "memory_peak": peak}
    except (ValueError, KeyError, IndexError) as error:
        raise ProofFailure("probe_invalid") from error


def cpu_delta(before: dict[str, int], after: dict[str, int], seconds: int) -> int:
    if any(type(v) is not int or v < 0 for v in (*before.values(), *after.values())):
        raise ProofFailure("counter_invalid")
    if before.keys() != after.keys() or any(after[k] < before[k] for k in before):
        raise ProofFailure("cpu_counter_regressed")
    delta = sum(after[k] - before[k] for k in before)
    if delta > seconds * 1_000_000:
        raise ProofFailure("cpu_budget")
    return delta


def output_limit() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))


def run(
    args: list[str],
    *,
    timeout: float = 5,
    before_reap: Callable[[], None] | None = None,
    deadline: float | None = None,
) -> str:
    """Bound output and client lifetime; service failure cancels containers before reaping."""
    with tempfile.TemporaryFile() as output:
        try:
            child = subprocess.Popen(
                args, stdout=output, stderr=output, start_new_session=True, preexec_fn=output_limit
            )
            started = time.monotonic()
            try:
                while child.poll() is None:
                    if time.monotonic() - started > timeout:
                        raise ProofFailure("command_timeout")
                    if os.fstat(output.fileno()).st_size >= LIMIT:
                        raise ProofFailure("output_limit")
                    time.sleep(0.02)
                if time.monotonic() - started >= timeout:
                    raise ProofFailure("command_timeout")
                if child.returncode or os.fstat(output.fileno()).st_size >= LIMIT:
                    raise ProofFailure("command_failed", returncode=child.returncode)
            except (ProofFailure, OSError):
                if before_reap is not None:
                    before_reap()
                raise
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    reap_seconds = (
                        2 if deadline is None else max(0, min(2, deadline - time.monotonic()))
                    )
                    try:
                        child.wait(timeout=reap_seconds)
                    except subprocess.TimeoutExpired:
                        raise ProofFailure("client_reap_unverified") from None
        except OSError as error:
            raise ProofFailure("tool_unavailable") from error
        output.seek(0)
        return output.read(LIMIT).decode("utf-8", errors="strict").strip()


def source_query(kind: str, execute: Callable[..., str] | None = None) -> str:
    queries = {
        "head": ["rev-parse", "HEAD"],
        "status": ["status", "--porcelain"],
        "tree": ["rev-parse", "HEAD^{tree}"],
    }
    return (execute or run)(["git", "--no-optional-locks", *queries[kind]])


def remove_owned(ids: list[str], execute: Callable[..., str] | None = None) -> None:
    execute = execute or run
    for cid in ids:
        identifier(cid)
    failed = False
    for cid in reversed(ids):
        try:
            execute(["docker", "rm", "--force", cid], timeout=10)
        except ProofFailure:
            failed = True
    # Successful daemon listing, not an inspect error, proves absence.
    present = execute(["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"]).splitlines()
    for cid in present:
        identifier(cid)
    if any(cid in present for cid in ids) or failed:
        raise ProofFailure("cleanup_failed")


def reconcile_owned(owned: Path, execute: Callable[..., str] | None = None) -> list[str]:
    """Discover only exact predeclared names, images and random ownership label."""
    execute = execute or run
    try:
        raw = owned.with_suffix(".owner.json").read_text()
        if len(raw) >= LIMIT:
            raise ProofFailure("owner_manifest")
        manifest = json.loads(raw)
        if type(manifest) is not dict or set(manifest) != {"token", "images"}:
            raise ProofFailure("owner_manifest")
        token, images = manifest["token"], manifest["images"]
        if (
            type(token) is not str
            or not re.fullmatch(r"[0-9a-f]{32}", token)
            or type(images) is not dict
            or set(images) != {"db", "worker", "canary"}
            or any(
                type(image) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)
                for image in images.values()
            )
        ):
            raise ProofFailure("owner_manifest")
    except (ValueError, OSError) as error:
        raise ProofFailure("owner_manifest") from error
    rows = execute(
        [
            "docker",
            "ps",
            "--all",
            "--no-trunc",
            "--filter",
            f"label=ocwp.quote-micro={token}",
            "--format",
            "{{.ID}}",
        ]
    ).splitlines()
    for cid in rows:
        identifier(cid)
        identity = execute(
            [
                "docker",
                "inspect",
                "--format",
                '{{.Image}}|{{index .Config.Labels "ocwp.quote-micro"}}|{{.Name}}',
                cid,
            ]
        )
        if identity not in {
            f"{image}|{token}|/ocwp-quote-{token}-{role}" for role, image in images.items()
        }:
            raise ProofFailure("owner_identity_mismatch")
    return rows


def effective_privileges(
    cid: str, worker: bool, execute: Callable[..., str] | None = None
) -> dict[str, object]:
    execute = execute or run
    raw = execute(
        ["docker", "exec", cid, "sh", "-c", "grep -E '^(Uid|CapEff|NoNewPrivs):' /proc/self/status"]
    )
    try:
        if len(raw.splitlines()) != 3:
            raise ProofFailure("effective_privileges_unavailable")
        entries = dict(line.split(":", 1) for line in raw.splitlines())
        uids = [integer(value) for value in entries["Uid"].split()]
        if (
            set(entries) != {"Uid", "CapEff", "NoNewPrivs"}
            or len(uids) != 4
            or len(set(uids)) != 1
            or not uids[0]
            or (worker and uids[0] != 10001)
            or entries["CapEff"].strip() != "0000000000000000"
            or entries["NoNewPrivs"].strip() != "1"
        ):
            raise ProofFailure("effective_privilege_boundary")
        return {"uid": uids[0], "effective_capabilities": 0, "no_new_privileges": True}
    except (ValueError, KeyError) as error:
        raise ProofFailure("effective_privileges_unavailable") from error


def cancellation_canary(
    cid: str, execute: Callable[..., str] | None = None, *, aggregate_deadline: float | None = None,
) -> dict[str, int]:
    """Three sleeping Python generations; terminate client before container cleanup."""
    execute = execute or run
    grandchild = (
        "from pathlib import Path; import time; Path('/tmp/canary-ready').touch(); time.sleep(60)"
    )
    child = (
        f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
        "time.sleep(60)"
    )
    parent = (
        f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "time.sleep(60)"
    )
    client = subprocess.Popen(
        ["docker", "exec", cid, "/app/.venv/bin/python", "-c", parent],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 10
    if aggregate_deadline is not None:
        deadline = min(deadline, aggregate_deadline)
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProofFailure("canary_readiness")
            try:
                execute(
                    ["docker", "exec", cid, "test", "-f", "/tmp/canary-ready"],
                    timeout=min(2, remaining),
                )
                break
            except ProofFailure:
                if time.monotonic() >= deadline:
                    raise ProofFailure("canary_readiness") from None
                time.sleep(min(0.05, deadline - time.monotonic()))
        os.killpg(client.pid, signal.SIGKILL)
        try:
            client.wait(timeout=2 if aggregate_deadline is None else max(
                0, min(2, aggregate_deadline - time.monotonic())
            ))
        except subprocess.TimeoutExpired:
            raise ProofFailure("canary_client_reap_unverified") from None
        # Prove the exec client's death did not itself clean up the descendants.
        rows = execute(["docker", "top", cid, "-eo", "pid,ppid"]).splitlines()
        if not rows or rows[0].split() != ["PID", "PPID"]:
            raise ProofFailure("canary_process_observer")
        try:
            parents = {
                integer(pid): integer(ppid) for pid, ppid in (line.split() for line in rows[1:])
            }
        except ValueError as error:
            raise ProofFailure("canary_process_observer") from error
        if 0 in parents or len(parents) != len(rows) - 1 or not 3 <= len(parents) <= 64:
            raise ProofFailure("canary_process_observer")
        if not any(parent in parents and parents[parent] in parents for parent in parents.values()):
            raise ProofFailure("canary_descendants_missing")
        resources = parse_probe(execute(["docker", "exec", cid, "sh", "-c", PROBE]), 512, 64)
        if resources["cpu_usec"] > 10_000_000:
            raise ProofFailure("canary_cpu_budget")
        remove_owned([cid], execute)
        return resources | {"observed_processes": len(parents)}
    finally:
        if client.poll() is None:
            os.killpg(client.pid, signal.SIGKILL)
            try:
                client.wait(timeout=2 if aggregate_deadline is None else max(
                    0, min(2, aggregate_deadline - time.monotonic())
                ))
            except subprocess.TimeoutExpired:
                raise ProofFailure("canary_client_reap_unverified") from None


def inspect_owned(
    cid: str, image: str, label: str, network: str, execute: Callable[..., str] | None = None
) -> None:
    execute = execute or run
    fields = execute(
        [
            "docker",
            "inspect",
            "--format",
            '{{.Id}}|{{.Image}}|{{index .Config.Labels "ocwp.quote-micro"}}|'
            "{{.HostConfig.NetworkMode}}|{{.HostConfig.Privileged}}|"
            "{{len .Mounts}}|{{.HostConfig.ReadonlyRootfs}}",
            cid,
        ]
    ).split("|")
    # Only Docker-managed tmpfs mounts are admitted, checked separately below.
    if (
        len(fields) != 7
        or fields[:5] != [cid, image, label, network, "false"]
        or fields[6:] != ["true"]
    ):
        raise ProofFailure("container_identity")
    mounts = execute(
        [
            "docker",
            "inspect",
            "--format",
            "{{range .Mounts}}{{.Type}} {{.Destination}}\n{{end}}",
            cid,
        ]
    ).splitlines()
    if any(
        line not in ("tmpfs /tmp", "tmpfs /var/lib/postgresql", "tmpfs /var/run/postgresql")
        for line in mounts
    ):
        raise ProofFailure("unexpected_mount")


def record_diagnostic(raw: str) -> dict[str, object]:
    value = json.loads(raw)
    stages = {
        "setup_sql",
        "input_text",
        "create_decode",
        "create_apply",
        "revision_bytes",
        "revision_totals",
        "decision_decode",
        "decision_load",
        "decision_apply",
        "decision_bytes",
        "decision_pricing",
        "history_bytes",
        "fresh_load",
        "exact_retry",
        "result_write",
        "complete",
    }
    kinds = {
        None,
        "assertion",
        "value_error",
        "request_error",
        "quote_conflict",
        "quote_integrity",
        "database_error",
        "unexpected",
    }
    fields = {
        "raw_create_bytes",
        "raw_decision_bytes",
        "revision_logical_bytes",
        "decision_logical_bytes",
        "two_record_history_bytes",
    }
    if type(value) is not dict or set(value) != {"stage", "failure_type", "byte_counts"}:
        raise ProofFailure("record_diagnostic_shape")
    if type(value["stage"]) is not str or value["stage"] not in stages:
        raise ProofFailure("record_diagnostic_stage")
    kind = value["failure_type"]
    if kind is not None and (type(kind) is not str or kind not in kinds):
        raise ProofFailure("record_diagnostic_failure")
    counts = value["byte_counts"]
    if (
        type(counts) is not dict
        or not set(counts) <= fields
        or any(type(v) is not int or not 0 <= v <= 16 * 1024 * 1024 for v in counts.values())
    ):
        raise ProofFailure("record_diagnostic_bytes")
    return value


def micro_result(raw: str, *, single_record: bool = False) -> dict[str, object]:
    value = json.loads(raw)
    expected = {
        "new_operations": 2 if single_record else 3,
        "revisions": 1 if single_record else 2,
        "decisions": 1,
        "lines_per_revision": 100 if single_record else 4,
        "lock_timeout_ms": 15000,
        "statement_timeout_ms": 20000,
        "maximum_capacity_qualified": False,
    }
    fields = set(expected) | {"operation_seconds", "process_cpu_seconds"}
    if single_record:
        fields.add("record_feasibility")
    if type(value) is not dict or set(value) != fields:
        raise ProofFailure("micro_evidence_shape")
    for key, wanted in expected.items():
        if type(value[key]) is not type(wanted) or value[key] != wanted:
            raise ProofFailure("micro_evidence_value")
    timings = value["operation_seconds"]
    timing_fields = {"create", "decision", "fresh_load", "exact_retry"}
    if not single_record:
        timing_fields.add("revise")
    if type(timings) is not dict or set(timings) != timing_fields:
        raise ProofFailure("micro_evidence_timings")
    for seconds in (*timings.values(), value["process_cpu_seconds"]):
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds < 20:
            raise ProofFailure("micro_evidence_budget")
    if single_record:
        metrics = value["record_feasibility"]
        fixed = dict(
            target_edges=1000,
            labor_lines=80,
            discount_lines=10,
            tax_lines=10,
            approved_charges=80,
            discount_allocations=500,
            tax_targets=500,
            description_codepoints=500,
            description_utf8_bytes=500,
            note_codepoints=2000,
            note_utf8_bytes=2000,
            source_reference_codepoints=200,
            source_reference_utf8_bytes=200,
            subtotal_minor=800000,
            discount_minor=500,
            tax_minor=499500,
            total_minor=1299000,
        )
        bounds = dict(
            raw_create_bytes=128 * 1024,
            raw_decision_bytes=128 * 1024,
            revision_logical_bytes=256 * 1024,
            decision_logical_bytes=256 * 1024,
            two_record_history_bytes=16 * 1024 * 1024,
        )
        if type(metrics) is not dict or set(metrics) != fixed.keys() | bounds.keys():
            raise ProofFailure("feasibility_evidence_shape")
        if any(type(v) is not int for v in metrics.values()):
            raise ProofFailure("feasibility_evidence_value")
        if any(metrics[k] != v for k, v in fixed.items()) or any(
            not 0 < metrics[k] <= limit for k, limit in bounds.items()
        ):
            raise ProofFailure("feasibility_evidence_value")
        if metrics["two_record_history_bytes"] != (
            metrics["revision_logical_bytes"] + metrics["decision_logical_bytes"] + 3
        ):
            raise ProofFailure("feasibility_byte_accounting")
    return value


SERVICE_NODES = (
    "tests/operations/test_quote_service_static_contracts.py::test_repository_contract",
    "tests/operations/test_quote_service_static_contracts.py::test_python_lint",
    "tests/operations/test_quote_service_static_contracts.py::test_python_format",
    "tests/operations/test_quote_service_static_contracts.py::test_production_types",
    "tests/operations/test_quote_service_static_contracts.py::test_openapi_contract",
    "tests/operations/test_quote_service_static_contracts.py::test_generated_client_contract",
)

# Fixed public source scope; non-Ruff tools retain their closed diagnostic vocabulary.
STATIC_PATHS = (
    "services/platform/src/cycling_workshop/quotes/effects.py",
    "services/platform/src/cycling_workshop/quotes/reconstruction.py",
    "services/platform/src/cycling_workshop/quotes/repository.py",
    "services/platform/src/cycling_workshop/quotes/responses.py",
    "services/platform/src/cycling_workshop/quotes/service.py",
    "services/platform/src/cycling_workshop/sync/writes.py",
    "services/platform/tests/quotes/test_quote_application_service.py",
    "services/platform/tests/quotes/test_quote_atomic_effects.py",
    "services/platform/tests/quotes/test_quote_command_response.py",
    "services/platform/tests/quotes/test_quote_driver_budgets.py",
    "services/platform/tests/quotes/test_quote_reconstruction.py",
    "services/platform/tests/quotes/test_quote_result_codec_once.py",
    "services/platform/tests/quotes/test_quote_single_pass.py",
    "scripts/ci/quote_capacity_micro.py",
    "scripts/ci/quote_collection_regression.py",
    "scripts/ci/quote_guard_bootstrap.py",
    "tests/operations/test_quote_capacity_micro.py",
    "tests/operations/test_quote_service_collection.py",
    "tests/operations/test_quote_service_static_contracts.py",
)
STATIC_REPOSITORY_PATHS = (
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "ARCHITECTURE.md",
    "package.json",
    "pnpm-workspace.yaml",
    "pyproject.toml",
    "tsconfig.base.json",
    ".python-version",
    ".nvmrc",
    "apps/web",
    "services/platform",
    "packages/ui",
    "packages/api-client",
    "packages/plugin-sdk",
    "packages/branding",
    "infra/compose",
    "fixtures/minimal",
    "fixtures/demo-workshop",
    "fixtures/load",
)
# Ruff emits ordinary lint codes and lowercase hyphenated syntax-diagnostic codes.
STATIC_RUFF_CODE_PATTERN = r"(?:[A-Z]+[0-9]+|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)"
STATIC_RUFF_FAILURE_LIMIT = 12 * 1024
STATIC_RUFF_MESSAGE_LIMIT = 1024
STATIC_MYPY_RULES = frozenset(
    [
        "abstract",
        "annotation-unchecked",
        "arg-type",
        "assert-type",
        "assignment",
        "attr-defined",
        "await-not-async",
        "call-arg",
        "call-overload",
        "comparison-overlap",
        "deprecated",
        "dict-item",
        "empty-body",
        "exhaustive-match",
        "exit-return",
        "explicit-any",
        "explicit-override",
        "func-returns-value",
        "has-type",
        "ignore-without-code",
        "import",
        "import-not-found",
        "import-untyped",
        "index",
        "list-item",
        "literal-required",
        "maybe-unrecognized-str-typeform",
        "metaclass",
        "method-assign",
        "misc",
        "mutable-override",
        "name-defined",
        "name-match",
        "narrowed-type-not-subtype",
        "no-any-return",
        "no-any-unimported",
        "no-overload-impl",
        "no-redef",
        "no-untyped-call",
        "no-untyped-def",
        "nonetype-type",
        "operator",
        "overload-cannot-match",
        "overload-overlap",
        "override",
        "possibly-undefined",
        "prop-decorator",
        "redundant-cast",
        "redundant-expr",
        "redundant-self",
        "return",
        "return-value",
        "safe-super",
        "str-bytes-safe",
        "str-format",
        "str-unpack",
        "syntax",
        "top-level-await",
        "truthy-bool",
        "truthy-function",
        "truthy-iterable",
        "type-abstract",
        "type-arg",
        "type-var",
        "typeddict-item",
        "typeddict-readonly-mutated",
        "typeddict-unknown-key",
        "unimported-reveal",
        "union-attr",
        "unreachable",
        "untyped-decorator",
        "unused-awaitable",
        "unused-coroutine",
        "unused-ignore",
        "used-before-def",
        "valid-newtype",
        "valid-type",
        "var-annotated",
    ]
)
STATIC_ALLOWED_PATHS = (
    STATIC_REPOSITORY_PATHS,
    STATIC_PATHS,
    STATIC_PATHS,
    STATIC_PATHS[:6],
    ("packages/api-client/openapi.json",),
    ("packages/api-client/src/generated.ts",),
)
STATIC_ALLOWED_RULES = (
    frozenset({"missing", "license"}),
    frozenset(),  # Ruff uses the bounded generic grammar, not a rule catalog.
    frozenset({"format"}),
    STATIC_MYPY_RULES,
    frozenset({"contract"}),
    frozenset({"contract"}),
)
STATIC_FAILURE_MARKER = b"OCWP_STATIC_FAILURE_V1:"
STATIC_FAILURE_LIMIT = 4096
SERVICE_REPORT = "/tmp/quote-service-initial-result.json"
SERVICE_FAILURE_MARKER = b"OCWP_SERVICE_FAILURE_V1:"
SERVICE_FAILURE_LIMIT = 512


def service_argv(cid: str) -> list[str]:
    """One closed selection; env -i drops inherited pytest/application/PG settings."""
    return [
        "docker",
        "exec",
        identifier(cid),
        "env",
        "-i",
        "PATH=/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME=/tmp",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        "OCWP_QUOTE_SERVICE_INITIAL=contained",
        "/app/.venv/bin/python",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        "-p",
        "scripts.ci.quote_capacity_micro",
        "--tb=no",
        "--show-capture=no",
        "--capture=fd",
        "--maxfail=1",
        "--basetemp=/tmp/quote-service-initial",
        "-W",
        "error::pytest.PytestUnhandledThreadExceptionWarning",
        "-W",
        "error::pytest.PytestUnraisableExceptionWarning",
        *SERVICE_NODES,
    ]


def strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProofFailure("service_duplicate_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise ProofFailure("service_nonfinite")


def service_result(raw: str) -> dict[str, object]:
    """Accept only six complete successful protocols, never six call-only passes."""
    if len(raw.encode("utf-8")) >= LIMIT:
        raise ProofFailure("service_report_limit")
    value = json.loads(raw, object_pairs_hook=strict_object, parse_constant=reject_constant)
    expected = {
        "schema": 1,
        "collection_count": 6,
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "session_finished": True,
        "session_exitstatus": 0,
    }
    if type(value) is not dict or set(value) != set(expected) | {"nodes", "reports"}:
        raise ProofFailure("service_report_shape")
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in expected.items()):
        raise ProofFailure("service_report_outcome")
    if value["nodes"] != list(SERVICE_NODES):
        raise ProofFailure("service_selection")
    reports = value["reports"]
    if type(reports) is not list or len(reports) != 18:
        raise ProofFailure("service_report_count")
    wanted = [(node, when) for node in SERVICE_NODES for when in ("setup", "call", "teardown")]
    for row, (node, when) in zip(reports, wanted, strict=True):
        if type(row) is not dict or set(row) != {"node", "when", "outcome", "seconds"}:
            raise ProofFailure("service_report_shape")
        if row["node"] != node or row["when"] != when or row["outcome"] != "passed":
            raise ProofFailure("service_report_outcome")
        seconds = row["seconds"]
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds < 20:
            raise ProofFailure("service_report_duration")
    return value


def service_failure_diagnostic(raw: bytes, *, returncode: int) -> dict[str, int]:
    """Validate a numeric marker; supervisor spool reads require verified stop/reap."""
    if (
        type(raw) is not bytes
        or len(raw) >= LIMIT
        or type(returncode) is not int
        or not 1 <= returncode <= 5
        or raw.count(SERVICE_FAILURE_MARKER) != 1
    ):
        raise ProofFailure("service_diagnostic_invalid")
    lines = [line for line in raw.split(b"\n")[:-1] if line.startswith(SERVICE_FAILURE_MARKER)]
    if len(lines) != 1 or len(lines[0]) + 1 > SERVICE_FAILURE_LIMIT:
        raise ProofFailure("service_diagnostic_invalid")
    payload = lines[0][len(SERVICE_FAILURE_MARKER) :]
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise ProofFailure("service_diagnostic_invalid") from error
    bounds = {
        "schema": (1, 1),
        "stage": (0, 4),
        "session_exitstatus": (returncode, returncode),
        "collection_count": (0, 100),
        "collection_errors": (0, 100),
        "unhandled_errors": (0, 100),
        "protocol_errors": (0, 100),
        "report_count": (0, 18),
        "setup_reports": (0, 18),
        "call_reports": (0, 18),
        "teardown_reports": (0, 18),
        "failed_reports": (0, 18),
        "skipped_reports": (0, 18),
    }
    if type(value) is not dict or set(value) != set(bounds):
        raise ProofFailure("service_diagnostic_invalid")
    if any(
        type(value[k]) is not int or not low <= value[k] <= high
        for k, (low, high) in bounds.items()
    ):
        raise ProofFailure("service_diagnostic_invalid")
    if (
        value["report_count"]
        != sum(value[f"{when}_reports"] for when in ("setup", "call", "teardown"))
        or value["failed_reports"] + value["skipped_reports"] > value["report_count"]
        or json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii") != payload
    ):
        raise ProofFailure("service_diagnostic_invalid")
    return value


def static_failure_diagnostic(raw: bytes, *, failure: dict[str, int]) -> dict[str, object]:
    """One bounded source-only diagnostic, bound to the first failed tool protocol."""
    if type(raw) is not bytes or len(raw) >= LIMIT or raw.count(STATIC_FAILURE_MARKER) != 1:
        raise ProofFailure("static_diagnostic_invalid")
    lines = [line for line in raw.split(b"\n")[:-1] if line.startswith(STATIC_FAILURE_MARKER)]
    if len(lines) != 1 or len(lines[0]) + 1 > STATIC_RUFF_FAILURE_LIMIT:
        raise ProofFailure("static_diagnostic_invalid")
    payload = lines[0][len(STATIC_FAILURE_MARKER) :]
    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise ProofFailure("static_diagnostic_invalid") from error
    bounds = {
        "schema": (1, 1),
        "tool": (0, 5),
        "kind": (1, 4),
        "output_bytes": (0, LIMIT),
        "omitted": (0, LIMIT),
        "unparsed_lines": (0, LIMIT),
    }
    if type(value) is not dict:
        raise ProofFailure("static_diagnostic_invalid")
    ruff = type(value.get("tool")) is int and value["tool"] == 1
    extra = {"complete", "incomplete_reasons", "reported_diagnostics"} if ruff else set()
    if set(value) != set(bounds) | {"returncode", "diagnostics"} | extra:
        raise ProofFailure("static_diagnostic_invalid")
    if len(lines[0]) + 1 > (STATIC_RUFF_FAILURE_LIMIT if ruff else STATIC_FAILURE_LIMIT):
        raise ProofFailure("static_diagnostic_invalid")
    if any(
        type(value[k]) is not int or not low <= value[k] <= high
        for k, (low, high) in bounds.items()
    ):
        raise ProofFailure("static_diagnostic_invalid")
    tool, kind, returncode = value["tool"], value["kind"], value["returncode"]
    if returncode is not None and (type(returncode) is not int or not -127 <= returncode <= 255):
        raise ProofFailure("static_diagnostic_invalid")
    if (
        (kind != 4 and returncode is None)
        or (kind == 1 and (returncode == 0 or value["output_bytes"] == LIMIT))
        or (kind == 3 and value["output_bytes"] != LIMIT)
        or (kind == 4 and (returncode is not None or value["output_bytes"] != 0))
    ):
        raise ProofFailure("static_diagnostic_invalid")
    protocols = tool + 1
    expected = {
        "schema": 1,
        "stage": 3,
        "session_exitstatus": 1,
        "collection_count": 6,
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "report_count": protocols * 3,
        "setup_reports": protocols,
        "call_reports": protocols,
        "teardown_reports": protocols,
        "failed_reports": 1,
        "skipped_reports": 0,
    }
    if failure != expected or any(type(v) is not int for v in failure.values()):
        raise ProofFailure("static_diagnostic_protocol")
    rows = value["diagnostics"]
    if type(rows) is not list or len(rows) > (512 if ruff else 12):
        raise ProofFailure("static_diagnostic_invalid")
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        fields = {"path", "line", "rule"} | ({"column", "message"} if ruff else set())
        if (
            type(row) is not dict
            or set(row) != fields
            or type(row["path"]) is not str
            or row["path"] not in STATIC_ALLOWED_PATHS[tool]
            or type(row["line"]) is not int
            or not (1 if ruff else 0) <= row["line"] <= 1_000_000
            or type(row["rule"]) is not str
        ):
            raise ProofFailure("static_diagnostic_invalid")
        key = (row["path"], row["line"], row["rule"])
        if ruff:
            if (
                not 1 <= len(row["rule"]) <= 64
                or re.fullmatch(STATIC_RUFF_CODE_PATTERN, row["rule"]) is None
                or type(row["column"]) is not int
                or not 1 <= row["column"] <= 1_000_000
                or type(row["message"]) is not str
                or not row["message"].isprintable()
                or not 1 <= len(row["message"].encode("utf-8")) <= STATIC_RUFF_MESSAGE_LIMIT
            ):
                raise ProofFailure("static_diagnostic_invalid")
            key += (row["column"], row["message"])
        elif row["rule"] not in STATIC_ALLOWED_RULES[tool]:
            raise ProofFailure("static_diagnostic_invalid")
        if key in seen:
            raise ProofFailure("static_diagnostic_invalid")
        seen.add(key)
    if ruff:
        reported = value["reported_diagnostics"]
        if reported is not None and (type(reported) is not int or not 1 <= reported <= LIMIT):
            raise ProofFailure("static_diagnostic_invalid")
        reasons = []
        if kind != 1 or returncode != 1:
            reasons.append("tool_status")
        if value["output_bytes"] == LIMIT:
            reasons.append("output_limit")
        if value["unparsed_lines"]:
            reasons.append("unparsed_lines")
        if value["omitted"]:
            reasons.append("omitted_rows")
        if reported is None or reported != len(rows) + value["omitted"]:
            reasons.append("summary_mismatch")
        if (
            type(value["complete"]) is not bool
            or value["complete"] != (not reasons)
            or type(value["incomplete_reasons"]) is not list
            or value["incomplete_reasons"] != reasons
        ):
            raise ProofFailure("static_diagnostic_invalid")
    if (
        (kind == 4 and (rows or value["omitted"] or value["unparsed_lines"]))
        or (ruff and kind == 4 and value["reported_diagnostics"] is not None)
        or (not ruff and value["omitted"] and len(rows) != 12)
        or json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii") != payload
    ):
        raise ProofFailure("static_diagnostic_invalid")
    return value


class ServiceReportHook:
    """Small explicit pytest plugin. Retain no payload, trace, exception or captured text."""

    def __init__(self) -> None:
        # Closed stage codes: 0 bootstrap, 1 collection, 2 setup, 3 call, 4 teardown.
        self.stage = 0
        self.failure_stage: int | None = None
        self.failure_marker_attempted = False
        self.value: dict[str, object] = {
            "schema": 1,
            "nodes": [],
            "collection_count": 0,
            "collection_errors": 0,
            "unhandled_errors": 0,
            "protocol_errors": 0,
            "session_finished": False,
            "session_exitstatus": -1,
            "reports": [],
        }

    def bump(self, field: str) -> None:
        self.value[field] = min(100, cast(int, self.value[field]) + 1)
        if self.failure_stage is None:
            self.failure_stage = self.stage

    def pytest_collectreport(self, report: object) -> None:
        self.stage = 1
        if getattr(report, "outcome", None) != "passed":
            self.bump("collection_errors")

    def pytest_collection_finish(self, session: object) -> None:
        import pytest

        self.stage = 1
        nodes = [getattr(item, "nodeid", None) for item in session.items]
        self.value["collection_count"] = min(100, len(nodes))
        if nodes != list(SERVICE_NODES) or len(set(nodes)) != 6:
            self.bump("protocol_errors")
            raise pytest.UsageError("service_selection")
        self.value["nodes"] = list(SERVICE_NODES)

    def pytest_runtest_logreport(self, report: object) -> None:
        node, when = getattr(report, "nodeid", None), getattr(report, "when", None)
        outcome, seconds = getattr(report, "outcome", None), getattr(report, "duration", None)
        rows = cast(list[dict[str, object]], self.value["reports"])
        if (
            node not in SERVICE_NODES
            or when not in {"setup", "call", "teardown"}
            or outcome not in {"passed", "failed", "skipped"}
            or len(rows) >= 18
            or type(seconds) not in (int, float)
            or not math.isfinite(seconds)
            or not 0 <= seconds < 20
            or hasattr(report, "wasxfail")
        ):
            self.bump("protocol_errors")
            return
        self.stage = {"setup": 2, "call": 3, "teardown": 4}[when]
        if outcome != "passed" and self.failure_stage is None:
            self.failure_stage = self.stage
        rows.append({"node": node, "when": when, "outcome": outcome, "seconds": seconds})

    def pytest_internalerror(self) -> None:
        self.bump("unhandled_errors")

    def pytest_keyboard_interrupt(self) -> None:
        self.bump("unhandled_errors")

    def emit_failure_marker(self, session: object) -> None:
        """Best effort: emit numbers only; never flush captured output or alter failure."""
        if self.failure_marker_attempted:
            return
        self.failure_marker_attempted = True
        try:
            rows = cast(list[dict[str, object]], self.value["reports"])
            value = {
                key: self.value[key]
                for key in (
                    "schema",
                    "session_exitstatus",
                    "collection_count",
                    "collection_errors",
                    "unhandled_errors",
                    "protocol_errors",
                )
            } | {
                "stage": self.stage if self.failure_stage is None else self.failure_stage,
                "report_count": len(rows),
                **{
                    f"{when}_reports": sum(row["when"] == when for row in rows)
                    for when in ("setup", "call", "teardown")
                },
                **{
                    f"{outcome}_reports": sum(row["outcome"] == outcome for row in rows)
                    for outcome in ("failed", "skipped")
                },
            }
            marker = (
                SERVICE_FAILURE_MARKER
                + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                    "ascii"
                )
                + b"\n"
            )
            service_failure_diagnostic(marker, returncode=cast(int, value["session_exitstatus"]))
            capture = session.config.pluginmanager.getplugin("capturemanager")
            # --capture=fd otherwise hides a session hook's print. Suspend only
            # around this one bounded write; never read/release captured text.
            with capture.global_and_fixture_disabled():
                os.write(1, b"\n" + marker)
        except Exception:
            # Missing/truncated/invalid output is unavailable, never a new failure.
            return

    def pytest_sessionfinish(self, session: object, exitstatus: int) -> None:
        self.value["session_finished"] = True
        self.value["session_exitstatus"] = int(exitstatus)
        try:
            raw = json.dumps(self.value, allow_nan=False, sort_keys=True)
            if len(raw.encode("utf-8")) >= LIMIT:
                raise ProofFailure("service_report_limit")
            Path(SERVICE_REPORT).write_text(raw, encoding="utf-8")
        finally:
            if exitstatus:
                self.emit_failure_marker(session)


def pytest_configure(config: object) -> None:
    # Only the explicitly loaded plugin participates; CLI imports never import pytest.
    if os.environ.get("OCWP_QUOTE_SERVICE_INITIAL") != "contained":
        raise ProofFailure("service_hook_context")
    config.pluginmanager.register(ServiceReportHook(), "quote-service-closed-report")


def cancel_runtime(ids: list[str], execute: Callable[..., str]) -> None:
    """Caller supplies a single five-second deadline; signal both before any inspection."""
    if not ids or len(ids) > 2 or len(set(ids)) != len(ids):
        raise ProofFailure("cancellation_identity")
    for cid in ids:
        identifier(cid)
    targets = list(reversed(ids))
    # A concurrently stopped container can make kill fail. Only readback proves stopped.
    with suppress(ProofFailure):
        execute(["docker", "kill", "--signal", "KILL", *targets], timeout=2)
    rows = execute(
        ["docker", "inspect", "--format", "{{.Id}}|{{.State.Running}}", *targets], timeout=3
    ).splitlines()
    if rows != [f"{cid}|false" for cid in targets]:
        raise ProofFailure("cancellation_unverified")


def supervise(
    worker_image: str,
    pg_image: str,
    commit: str,
    evidence: Path,
    owned: Path,
    *,
    single_record: bool = False,
    service_initial: bool = False,
) -> None:
    if single_record and service_initial:
        raise ProofFailure("mode_conflict")
    started = time.monotonic()
    command_deadline = started + (30 if service_initial else 900)
    micro_deadline = started  # Expired until the fixed workload actually starts.

    def execute(args: list[str], *, timeout: float = 5) -> str:
        remaining = command_deadline - time.monotonic()
        if remaining <= 0:
            if service_initial and report["phase"] in {
            "service_with_pytest_bootstrap",
            "service_final_readback",
        }:
                cancel_workload()
            raise ProofFailure("wall_budget")
        if service_initial and report["phase"] in {
            "service_with_pytest_bootstrap",
            "service_final_readback",
        }:
            result = run(
                args,
                timeout=min(timeout, remaining),
                before_reap=cancel_workload,
                deadline=command_deadline,
            )
        elif service_initial:
            result = run(args, timeout=min(timeout, remaining), deadline=command_deadline)
        else:
            result = run(args, timeout=min(timeout, remaining))
        if service_initial and time.monotonic() >= command_deadline:
            if report["phase"] in {"service_with_pytest_bootstrap", "service_final_readback"}:
                cancel_workload()
            raise ProofFailure("wall_budget")
        return result

    ids: list[str] = []
    creation_uncertain = False
    validated_runtime_ids: list[str] = []
    cancellation_started = False
    report: dict[str, object] = {
        "schema": 2 if service_initial else 1,
        "commit": commit,
        "mode": (
            "service_initial"
            if service_initial
            else ("single_record_feasibility" if single_record else "micro_only")
        ),
        "maximum_capacity_qualified": False,
        "status": "failed",
        "phase": "setup_and_containment",
    }

    def cancel_workload() -> None:
        nonlocal cancellation_started
        if cancellation_started or not validated_runtime_ids:
            return
        cancellation_started = True
        deadline = time.monotonic() + 5

        def kill_execute(args: list[str], *, timeout: float = 5) -> str:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProofFailure("cancellation_deadline")
            result = run(args, timeout=min(timeout, remaining), deadline=deadline)
            if time.monotonic() >= deadline:
                raise ProofFailure("cancellation_deadline")
            return result

        try:
            cancel_runtime(validated_runtime_ids, kill_execute)
            report["cancellation"] = "verified_stopped"
        except (ProofFailure, ValueError, OSError):
            report["cancellation"] = "unverified"
        report["cancellation_seconds"] = round(time.monotonic() - (deadline - 5), 3)

    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        raise ProofFailure("interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        report["command_stage"] = "source_head"
        if source_query("head", execute) != commit:
            raise ProofFailure("source_not_exact_clean_commit")
        report["command_stage"] = "source_status"
        if source_query("status", execute):
            raise ProofFailure("source_not_exact_clean_commit")
        report["command_stage"] = "source_tree"
        tree = source_query("tree", execute)
        report["command_stage"] = "image_source_label"
        if (
            execute(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "ocwp.source-tree"}}',
                    worker_image,
                ]
            )
            != tree
        ):
            raise ProofFailure("image_source_mismatch")
        report["tree"] = tree
        report["command_stage"] = "image_identity"
        images = [
            execute(["docker", "image", "inspect", "--format", "{{.Id}}", image])
            for image in (pg_image, worker_image)
        ]
        if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", image) for image in images):
            raise ProofFailure("image_identity")
        label = uuid4().hex
        owned.with_suffix(".owner.json").write_text(
            json.dumps(
                {
                    "token": label,
                    "images": {"db": images[0], "worker": images[1], "canary": images[1]},
                }
            )
        )
        snapshots = {}
        identities: list[dict[str, object]] = []
        report["identities"] = identities
        canary_resources: dict[str, int] = {}
        for role, image, memory, pids in [
            ("canary", images[1], 512, 64),
            ("db", images[0], 768, 128),
            ("worker", images[1], 512, 64),
        ]:
            network = "none" if role in {"db", "canary"} else f"container:{ids[0]}"
            args = [
                "docker",
                "create",
                "--name",
                f"ocwp-quote-{label}-{role}",
                "--cidfile",
                str(owned.with_suffix(f".{role}.cid")),
                "--label",
                f"ocwp.quote-micro={label}",
            ]
            args += [
                "--pull",
                "never",
                "--cgroupns",
                "private",
                "--cpus",
                "1",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--log-driver",
                "none",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
            ]
            args += [
                "--memory",
                f"{memory}m",
                "--memory-swap",
                f"{memory}m",
                "--pids-limit",
                str(pids),
                "--network",
                network,
            ]
            if role == "db":
                args += [
                    "--user",
                    "postgres",
                    "--tmpfs",
                    "/var/lib/postgresql:rw,nosuid,mode=1777,size=256m",
                    "--tmpfs",
                    "/var/run/postgresql:rw,nosuid,mode=1777,size=16m",
                    "--env",
                    "POSTGRES_PASSWORD=ocwp-synthetic",
                    "--env",
                    "POSTGRES_USER=ocwp",
                    "--env",
                    "POSTGRES_DB=ocwp_quote_micro_test",
                ]
                args += [image, "-c", "max_connections=20", "-c", "shared_buffers=64MB"]
            else:
                args += [
                    "--user",
                    "10001:10001",
                    "--workdir",
                    "/app",
                    "--env",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "--env",
                    "OCWP_QUOTE_MICRO=contained",
                    "--env",
                    "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic"
                    "@127.0.0.1:5432/ocwp_quote_micro_test",
                    "--entrypoint",
                    "/app/.venv/bin/python",
                ]
                args += [image, "-c", "import time; time.sleep(900)"]
            report["command_stage"] = f"{role}_containment"
            creation_uncertain = True
            cid = identifier(execute(args))
            creation_uncertain = False
            ids.append(cid)
            owned.write_text(json.dumps(ids))
            if service_initial:
                inspect_owned(cid, image, label, network, execute)
                if role != "canary":
                    validated_runtime_ids.append(cid)
            else:
                inspect_owned(cid, image, label, network)
            execute(["docker", "start", cid])
            snapshots[role] = parse_probe(
                execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids
            )
            privileges = effective_privileges(cid, role != "db", execute)
            identities.append(
                {
                    "role": role,
                    "container_id": cid,
                    "image_id": image,
                    "owner_label": label,
                    "network": network,
                    "memory_max": memory * 1024 * 1024,
                    "memory_swap_max": 0,
                    "cpu_max": "100000 100000",
                    "pids_max": pids,
                    "cgroup": "0::/",
                    "events_zero": True,
                    "privileges": privileges,
                }
            )
            if role == "canary":
                canary_resources = (
                    cancellation_canary(cid, execute, aggregate_deadline=command_deadline)
                    if service_initial else cancellation_canary(cid, execute)
                )
                report["canary_resources"] = canary_resources
                cpu_delta(
                    {"canary": snapshots["canary"]["cpu_usec"]},
                    {"canary": canary_resources["cpu_usec"]},
                    10,
                )
                snapshots.pop("canary")
                ids.remove(cid)
                owned.with_suffix(".canary.cid").unlink()
                report["cancellation_canary"] = (
                    "three_generations_survived_client_kill_then_container_absent"
                )
        report["command_stage"] = "database_readiness"
        deadline = time.monotonic() + 30
        while True:
            try:
                execute(
                    [
                        "docker",
                        "exec",
                        ids[0],
                        "pg_isready",
                        "-U",
                        "ocwp",
                        "-d",
                        "ocwp_quote_micro_test",
                    ]
                )
                break
            except ProofFailure:
                if time.monotonic() >= min(deadline, command_deadline):
                    raise ProofFailure("database_readiness") from None
                time.sleep(0.2)
        if service_initial:
            # Fresh baseline separates PostgreSQL startup from the SQLite workload.
            snapshots = {
                role: parse_probe(execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids)
                for cid, role, memory, pids in [
                    (ids[0], "db", 768, 128), (ids[1], "worker", 512, 64)
                ]
            }
            if time.monotonic() >= command_deadline:
                raise ProofFailure("setup_deadline")
            cpu_delta({"db": 0, "worker": 0}, {
                role: data["cpu_usec"] for role, data in snapshots.items()
            }, 60)
            report["environment_overhead_before_workload_cpu_usec"] = {
                role: data["cpu_usec"] for role, data in snapshots.items()
            }
            report["database_role"] = "unused_postgresql_environment_overhead_sqlite_tests_only"
        report["setup_seconds"] = round(time.monotonic() - started, 3)
        report["command_stage"] = "service_initial" if service_initial else "microfixture"
        report["phase"] = (
            "service_with_pytest_bootstrap" if service_initial else "micro_with_pytest_bootstrap"
        )
        # Only now may pytest import the selected closed specimen.
        before = {role: data["cpu_usec"] for role, data in snapshots.items()}
        previous = before
        with tempfile.TemporaryFile() as output:
            micro_deadline = time.monotonic() + 20
            command_deadline = micro_deadline
            micro_started = time.monotonic()
            child = subprocess.Popen(
                service_argv(ids[1]) if service_initial else [
                    "docker",
                    "exec",
                    ids[1],
                    "/app/.venv/bin/python",
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--tb=no",
                    "--basetemp=/tmp/quote-micro",
                    (
                        "services/platform/tests/quotes/test_quote_record_feasibility_postgres.py"
                        if single_record
                        else "services/platform/tests/quotes/test_quote_capacity_micro_postgres.py"
                    ),
                ],
                stdout=output,
                stderr=output,
                start_new_session=True,
                preexec_fn=output_limit,
            )
            try:
                while child.poll() is None:
                    if time.monotonic() - micro_started > 20 or time.monotonic() - started > 900:
                        raise ProofFailure("wall_budget")
                    if os.fstat(output.fileno()).st_size >= LIMIT:
                        raise ProofFailure("output_limit")
                    current = {}
                    for cid, role, memory, pids in [
                        (ids[0], "db", 768, 128),
                        (ids[1], "worker", 512, 64),
                    ]:
                        snapshots[role] = parse_probe(
                            execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids
                        )
                        current[role] = snapshots[role]["cpu_usec"]
                    report["last_sampled_containers"] = dict(snapshots)
                    cpu_delta(previous, current, 40 if service_initial else 600)
                    cpu_delta(dict.fromkeys(current, 0), current, 60 if service_initial else 600)
                    if service_initial:
                        cpu_delta(before, current, 40)
                        if sum(current.values()) + canary_resources["cpu_usec"] > 70_000_000:
                            raise ProofFailure("cpu_budget")
                    previous = current
                    time.sleep(0.1)
                if time.monotonic() >= command_deadline:
                    raise ProofFailure("wall_budget")
                if child.returncode or os.fstat(output.fileno()).st_size >= LIMIT:
                    raise ProofFailure("micro_failed", returncode=child.returncode)
                report[
                    "workload_wall_seconds" if service_initial else "micro_wall_seconds"
                ] = round(time.monotonic() - micro_started, 3)
            except (ProofFailure, ValueError, OSError):
                if service_initial:
                    report["service_failure_diagnostic"] = "unavailable_or_invalid"
                    cancel_workload()
                raise
            finally:
                if child.poll() is None:
                    if service_initial:
                        cancel_workload()
                    os.killpg(child.pid, signal.SIGKILL)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        if service_initial:
                            report["specimen_client_reap"] = "unverified"
                        raise ProofFailure("client_reap_unverified") from None
                if service_initial:
                    if type(child.returncode) is not int:
                        raise ProofFailure("specimen_exit_unverified")
                    report["specimen_returncode"] = child.returncode
                    report["specimen_client_reap"] = "verified"
                    if child.returncode and report.get("cancellation") == "verified_stopped":
                        try:
                            # Local spool only, after whole-workload stop and client
                            # reaping. No extra Docker read or deadline extension.
                            output.seek(0)
                            failure_output = output.read(LIMIT)
                            failure_summary = service_failure_diagnostic(
                                failure_output,
                                returncode=child.returncode,
                            )
                            report["service_failure_diagnostic"] = failure_summary
                            try:
                                report["static_failure_diagnostic"] = static_failure_diagnostic(
                                    failure_output,
                                    failure=failure_summary,
                                )
                            except Exception:
                                report["static_failure_diagnostic"] = "unavailable_or_invalid"
                        except Exception:
                            report["service_failure_diagnostic"] = "unavailable_or_invalid"
        command_deadline = time.monotonic() + 5 if service_initial else started + 900
        if service_initial:
            report["phase"] = "service_final_readback"
        # Containers remain alive: read final cgroup events after workload exit.
        final = {
            role: parse_probe(execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids)
            for cid, role, memory, pids in [(ids[0], "db", 768, 128), (ids[1], "worker", 512, 64)]
        }
        cpu_delta(
            previous,
            {role: value["cpu_usec"] for role, value in final.items()},
            40 if service_initial else 600,
        )
        final_cpu = {role: value["cpu_usec"] for role, value in final.items()}
        lifetime_cpu = cpu_delta(
            dict.fromkeys(final_cpu, 0), final_cpu, 60 if service_initial else 600
        )
        report["lifetime_cpu_usec"] = lifetime_cpu
        if lifetime_cpu + canary_resources["cpu_usec"] > (
            70_000_000 if service_initial else 600_000_000
        ):
            raise ProofFailure("cpu_budget")
        report["observed_workload_cpu_usec"] = cpu_delta(
            before, final_cpu, 40 if service_initial else 600
        )
        report["containers"] = final
        if service_initial:
            report["workload_cpu_usec_by_role"] = {
                role: final_cpu[role] - before[role] for role in before
            }
            report["service"] = service_result(
                execute(["docker", "exec", ids[1], "cat", SERVICE_REPORT])
            )
            if time.monotonic() >= command_deadline:
                raise ProofFailure("final_readback_deadline")
            report["phase"] = "service_complete"
            report["status"] = "service_initial_passed_not_postgresql_or_capacity"
        else:
            micro = micro_result(
                execute(["docker", "exec", ids[1], "cat", "/tmp/quote-micro-result.json"]),
                single_record=single_record,
            )
            report["micro"] = micro
            if cast(float, micro["process_cpu_seconds"]) * 1_000_000 > final_cpu["worker"]:
                raise ProofFailure("cpu_accounting_disagrees")
            report["phase"] = "micro_complete"
            report["status"] = "micro_passed_not_capacity"
    except (ProofFailure, ValueError, OSError) as error:
        if service_initial:
            cancel_workload()
        report["failure"] = str(error) if isinstance(error, ProofFailure) else "invalid_evidence"
        if isinstance(error, ProofFailure) and error.returncode is not None:
            report["client_returncode"] = error.returncode
        if single_record and report["phase"] == "micro_with_pytest_bootstrap":
            # Even post-success validation failures cannot reuse the outer deadline.
            command_deadline = min(command_deadline, micro_deadline)
            # Diagnostic commands share the original workload deadline; never extend it.
            try:
                report["record_diagnostic"] = record_diagnostic(
                    execute(["docker", "exec", ids[1], "cat", "/tmp/quote-record-diagnostic.json"])
                )
            except (ProofFailure, ValueError, OSError):
                report["record_diagnostic"] = "unavailable_or_invalid"
            try:
                report["failure_final_containers"] = {
                    role: parse_probe(
                        execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids
                    )
                    for cid, role, memory, pids in [
                        (ids[0], "db", 768, 128),
                        (ids[1], "worker", 512, 64),
                    ]
                }
                report["failure_final_probe"] = "passed"
            except (ProofFailure, ValueError, OSError) as probe_error:
                report["failure_final_probe"] = (
                    str(probe_error)
                    if isinstance(probe_error, ProofFailure)
                    else "invalid_evidence"
                )
    finally:
        if service_initial:
            command_deadline = time.monotonic() + 35
        try:
            for role in ("canary", "db", "worker"):
                cidfile = owned.with_suffix(f".{role}.cid")
                if cidfile.exists():
                    cid = identifier(cidfile.read_text().strip())
                    if cid not in ids:
                        ids.append(cid)
            if owned.with_suffix(".owner.json").exists():
                discovered = (
                    reconcile_owned(owned, execute) if service_initial else reconcile_owned(owned)
                )
                for cid in discovered:
                    if cid not in ids:
                        ids.append(cid)
            if service_initial:
                remove_owned(ids, execute)
            else:
                remove_owned(ids)
            if creation_uncertain:
                raise ProofFailure("creation_outcome_uncertain")
            report["cleanup"] = "verified_absent"
        except (ProofFailure, OSError, ValueError):
            report["cleanup"] = "failed"
            report["status"] = "failed"
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, sort_keys=True) + "\n")
    wanted_status = (
        "service_initial_passed_not_postgresql_or_capacity"
        if service_initial
        else "micro_passed_not_capacity"
    )
    if report["status"] != wanted_status:
        raise ProofFailure("service_unqualified" if service_initial else "micro_unqualified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--pg-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--owned", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--single-record-feasibility", action="store_true")
    modes.add_argument("--service-initial", action="store_true")
    args = parser.parse_args()
    try:
        supervise(
            args.worker_image,
            args.pg_image,
            args.commit,
            args.evidence,
            args.owned,
            single_record=args.single_record_feasibility,
            service_initial=args.service_initial,
        )
    except ProofFailure:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
