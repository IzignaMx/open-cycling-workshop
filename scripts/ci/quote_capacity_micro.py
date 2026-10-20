"""Fixed contained CI workloads; no arbitrary selector or maximum-capacity mode."""

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

FULL_SPOOL_LIMIT = 1024 * 1024
FULL_BUILD_SPOOL_LIMIT = 1024 * 1024
FULL_RECORD_LIMIT = 4 * 1024 * 1024
FULL_SECONDS = 900
FULL_OUTER_SECONDS = 1020
FULL_CPU_SECONDS = 2060
FULL_SHM_BYTES = 64 * 1024 * 1024
FULL_TMPFS = {
    "worker": {
        "/tmp": "rw,noexec,nosuid,nodev,size=64m,nr_inodes=16384,mode=1777",
        "/tmp/ocwp-tests": (
            "rw,exec,nosuid,nodev,size=64m,nr_inodes=16384,uid=10001,gid=10001,mode=0700"
        ),
        "/tmp/ocwp-proof": (
            "rw,noexec,nosuid,nodev,size=16m,nr_inodes=32,uid=10001,gid=10001,mode=0700"
        ),
    },
    "db": {
        "/tmp": "rw,noexec,nosuid,nodev,size=64m,nr_inodes=16384,mode=1777",
        "/var/lib/postgresql": "rw,noexec,nosuid,nodev,size=512m,nr_inodes=32768,mode=1777",
        "/var/run/postgresql": "rw,noexec,nosuid,nodev,size=16m,nr_inodes=128,mode=1777",
    },
}


class ProofFailure(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        returncode: int | None = None,
        check: str | None = None,
        scratch: object = None,
    ) -> None:
        super().__init__(reason)
        self.returncode = returncode
        self.check = check
        self.scratch = scratch


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


def run(args: list[str], *, timeout: float = 5) -> str:
    """Bound Docker/Git client output on disk and never echo raw errors."""
    with tempfile.TemporaryFile() as output:
        try:
            with subprocess.Popen(
                args, stdout=output, stderr=output, start_new_session=True, preexec_fn=output_limit
            ) as child:
                started = time.monotonic()
                try:
                    while child.poll() is None:
                        if time.monotonic() - started > timeout:
                            raise ProofFailure("command_timeout")
                        if os.fstat(output.fileno()).st_size >= LIMIT:
                            raise ProofFailure("output_limit")
                        time.sleep(0.02)
                finally:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=2)
                if time.monotonic() - started >= timeout:
                    raise ProofFailure("command_timeout")
                if child.returncode or os.fstat(output.fileno()).st_size >= LIMIT:
                    raise ProofFailure("command_failed", returncode=child.returncode)
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


def cancellation_canary(cid: str, execute: Callable[..., str] | None = None) -> dict[str, int]:
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
                time.sleep(0.05)
        os.killpg(client.pid, signal.SIGKILL)
        client.wait(timeout=2)
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
            client.wait(timeout=2)


def inspect_owned(cid: str, image: str, label: str, network: str) -> None:
    fields = run(
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
    mounts = run(
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


def supervise(
    worker_image: str,
    pg_image: str,
    commit: str,
    evidence: Path,
    owned: Path,
    *,
    single_record: bool = False,
) -> None:
    started = time.monotonic()
    command_deadline = started + 900
    micro_deadline = started  # Expired until the fixed workload actually starts.

    def execute(args: list[str], *, timeout: float = 5) -> str:
        remaining = command_deadline - time.monotonic()
        if remaining <= 0:
            raise ProofFailure("wall_budget")
        return run(args, timeout=min(timeout, remaining))

    ids: list[str] = []
    creation_uncertain = False
    report: dict[str, object] = {
        "schema": 1,
        "commit": commit,
        "mode": "single_record_feasibility" if single_record else "micro_only",
        "maximum_capacity_qualified": False,
        "status": "failed",
        "phase": "setup_and_containment",
    }

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
                    "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic@127.0.0.1:5432/ocwp_quote_micro_test",
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
                canary_resources = cancellation_canary(cid, execute)
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
                if time.monotonic() >= deadline:
                    raise ProofFailure("database_readiness") from None
                time.sleep(0.2)
        report["setup_seconds"] = round(time.monotonic() - started, 3)
        report["command_stage"] = "microfixture"
        report["phase"] = "micro_with_pytest_bootstrap"
        # Only now may pytest import the fixed three-operation specimen.
        before = {role: data["cpu_usec"] for role, data in snapshots.items()}
        previous = before
        with tempfile.TemporaryFile() as output:
            micro_deadline = time.monotonic() + 20
            command_deadline = micro_deadline
            child = subprocess.Popen(
                [
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
            micro_started = time.monotonic()
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
                    cpu_delta(previous, current, 600)
                    cpu_delta(dict.fromkeys(current, 0), current, 600)
                    previous = current
                    time.sleep(0.1)
                if time.monotonic() >= command_deadline:
                    raise ProofFailure("wall_budget")
                if child.returncode or os.fstat(output.fileno()).st_size >= LIMIT:
                    raise ProofFailure("micro_failed", returncode=child.returncode)
                report["micro_wall_seconds"] = round(time.monotonic() - micro_started, 3)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=2)
        command_deadline = started + 900
        # Containers remain alive: read final cgroup events after workload exit.
        final = {
            role: parse_probe(execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids)
            for cid, role, memory, pids in [(ids[0], "db", 768, 128), (ids[1], "worker", 512, 64)]
        }
        cpu_delta(previous, {role: value["cpu_usec"] for role, value in final.items()}, 600)
        final_cpu = {role: value["cpu_usec"] for role, value in final.items()}
        lifetime_cpu = cpu_delta(dict.fromkeys(final_cpu, 0), final_cpu, 600)
        report["lifetime_cpu_usec"] = lifetime_cpu
        if lifetime_cpu + canary_resources["cpu_usec"] > 600_000_000:
            raise ProofFailure("cpu_budget")
        report["observed_workload_cpu_usec"] = cpu_delta(before, final_cpu, 600)
        report["containers"] = final
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
        try:
            for role in ("canary", "db", "worker"):
                cidfile = owned.with_suffix(f".{role}.cid")
                if cidfile.exists():
                    cid = identifier(cidfile.read_text().strip())
                    if cid not in ids:
                        ids.append(cid)
            if owned.with_suffix(".owner.json").exists():
                for cid in reconcile_owned(owned):
                    if cid not in ids:
                        ids.append(cid)
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
    if report["status"] != "micro_passed_not_capacity":
        raise ProofFailure("micro_unqualified")


def full_preparation_diagnostic(
    output,
    directory: Path,
    stage: str,
    failure: str | None,
    returncode: int | None,
    reaped: bool,
    *,
    spool_limit: int = LIMIT,
) -> None:
    """Preparation-only client evidence; never a workload or build-cleanup proof."""
    from scripts.ci.verify_v01 import write_full_python_json

    if spool_limit not in {LIMIT, FULL_BUILD_SPOOL_LIMIT} or (
        spool_limit != LIMIT and stage != "image_build"
    ):
        raise ProofFailure("preparation_diagnostic_scope")
    tail = spool_limit == FULL_BUILD_SPOOL_LIMIT
    directory.mkdir(parents=True, exist_ok=True)
    raw = b""
    size = None
    if output is not None and reaped:
        size = os.fstat(output.fileno()).st_size
        output.seek(max(0, size - LIMIT) if tail else 0)
        raw = output.read(LIMIT)
    (directory / "preparation.txt").write_bytes(raw)
    write_full_python_json(
        directory / "preparation.json",
        {
            "schema": 2,
            "kind": "ocwp.full_python.preparation_client",
            "status": "unqualified",
            "expected_commit": os.environ.get("GITHUB_SHA", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "stage": stage,
            "failure": failure,
            "returncode": returncode,
            "client_reaped": reaped,
            "available": size is not None,
            "observed_bytes": size,
            "retained_bytes": len(raw),
            "limit_bytes": LIMIT,
            "spool_limit_bytes": spool_limit,
            "capture": "tail" if tail else "prefix",
            "dropped_prefix_bytes": None
            if size is None
            else max(0, size - len(raw))
            if tail
            else 0,
            "retention_truncated": None if size is None else size > len(raw),
            "at_spool_limit": None if size is None else size >= spool_limit,
            "at_limit_or_truncated": None if size is None else size >= LIMIT,
            "build_resource_cleanup": "not_assessed",
            "qualification": "not_a_receipt",
        },
    )


def full_client(
    args: list[str],
    *,
    timeout: float = 5,
    limit: int = LIMIT,
    abort: Callable[[], None] | None = None,
    preparation: tuple[Path, str] | None = None,
) -> str:
    """Bound a full-route control client without an implicit Popen wait.

    The workload and record readers supply stop-before-reap through abort.
    RLIMIT_FSIZE belongs to this host client, never the container subprocess.
    """
    if limit not in {LIMIT, FULL_BUILD_SPOOL_LIMIT, FULL_RECORD_LIMIT} or not 0 < timeout <= 660:
        raise ProofFailure("client_budget")
    build_output = (
        preparation is not None
        and preparation[1] == "image_build"
        and args[:3] == ["docker", "build", "--progress=plain"]
        and abort is None
        and limit == FULL_BUILD_SPOOL_LIMIT
    )
    if limit == FULL_BUILD_SPOOL_LIMIT and not build_output:
        raise ProofFailure("preparation_diagnostic_scope")
    if preparation is not None and (
        (limit != LIMIT and not build_output)
        or abort is not None
        or preparation[1]
        not in {"source_tree", "image_build", "postgres_pull", "worker_image", "postgres_image"}
    ):
        raise ProofFailure("preparation_diagnostic_scope")

    def cap() -> None:
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

    with tempfile.TemporaryFile() as output:
        failure = "preparation_failed"
        reaped = False
        if preparation is not None:
            full_preparation_diagnostic(
                None, *preparation, "unfinished", None, False, spool_limit=limit
            )
        try:
            child = subprocess.Popen(
                args, stdout=output, stderr=output, start_new_session=True, preexec_fn=cap
            )
        except BaseException as error:
            if preparation is not None:
                failure = (
                    "interrupted" if isinstance(error, KeyboardInterrupt) else "tool_unavailable"
                )
                full_preparation_diagnostic(
                    None, *preparation, failure, None, False, spool_limit=limit
                )
            raise
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                if time.monotonic() >= deadline:
                    raise ProofFailure("command_timeout")
                if os.fstat(output.fileno()).st_size >= limit:
                    raise ProofFailure("output_limit")
                time.sleep(0.02)
            if time.monotonic() >= deadline:
                raise ProofFailure("command_timeout")
            if child.returncode or os.fstat(output.fileno()).st_size >= limit:
                raise ProofFailure("command_failed", returncode=child.returncode)
            output.seek(0)
            result = output.read(limit).decode("utf-8", errors="strict").strip()
            failure = None
            return result
        except BaseException as error:
            if isinstance(error, ProofFailure) and str(error) in {
                "command_timeout",
                "command_failed",
                "output_limit",
            }:
                failure = str(error)
            elif isinstance(error, OSError):
                failure = "tool_unavailable"
            elif isinstance(error, KeyboardInterrupt):
                failure = "interrupted"
            if abort is not None:
                abort()
            raise
        finally:
            # abort first attempts verified stop and bounded owned reconciliation.
            # If both fail, client hygiene is still bounded; that attempt cannot pass.
            try:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
                reaped = True
            finally:
                if preparation is not None:
                    if not reaped and failure is None:
                        failure = "client_reap_unverified"
                    full_preparation_diagnostic(
                        output,
                        *preparation,
                        failure,
                        child.returncode if reaped else None,
                        reaped,
                        spool_limit=limit,
                    )


def full_stop_worker(cid: str, execute: Callable[..., str] = full_client) -> None:
    """A killed Docker client is not evidence that its container children stopped."""
    identifier(cid)
    command = ["docker", "inspect", "--format", "{{.State.Running}}|{{.State.Pid}}", cid]
    state = execute(command)
    if state == "false|0":
        return
    if not re.fullmatch(r"true\|[1-9][0-9]*", state):
        raise ProofFailure("worker_stop_unverified")
    try:
        execute(["docker", "kill", "--signal", "KILL", cid], timeout=10)
    finally:
        if execute(command) != "false|0":
            raise ProofFailure("worker_stop_unverified")


def full_inspect(
    cid: str, image: str, token: str, network: str, role: str, execute: Callable[..., str]
) -> None:
    from scripts.ci.verify_v01 import read_full_python_value

    raw = execute(
        [
            "docker",
            "inspect",
            "--format",
            '{"id":{{json .Id}},"image":{{json .Image}},'
            '"token":{{json (index .Config.Labels "ocwp.quote-micro")}},'
            '"user":{{json .Config.User}},"host":{{json .HostConfig}},'
            '"mounts":{{json .Mounts}}}',
            cid,
        ]
    )
    value = read_full_python_value(raw)
    host = value.get("host")
    if (
        set(value) != {"id", "image", "token", "user", "host", "mounts"}
        or value["id"] != cid
        or value["image"] != image
        or value["token"] != token
        or value["user"] != ("postgres" if role == "db" else "10001:10001")
        or type(host) is not dict
    ):
        raise ProofFailure("container_identity", check="identity")
    expected = FULL_TMPFS["db" if role == "db" else "worker"]
    memory, pids = (1024, 128) if role == "db" else (512, 64)
    fixed = {
        "NetworkMode": network,
        "Privileged": False,
        "ReadonlyRootfs": True,
        "Memory": memory * 1024 * 1024,
        "MemorySwap": memory * 1024 * 1024,
        "NanoCpus": 1_000_000_000,
        "PidsLimit": pids,
        "ShmSize": FULL_SHM_BYTES,
        "CgroupnsMode": "private",
        "CapDrop": ["ALL"],
        "IpcMode": "private",
        "PidMode": "",
        "UTSMode": "",
        "PublishAllPorts": False,
        "SecurityOpt": ["no-new-privileges:true"],
        "Tmpfs": expected,
    }
    for key, expected_value in fixed.items():
        if type(host.get(key)) is not type(expected_value) or host[key] != expected_value:
            raise ProofFailure("container_boundary", check=key)
    if host.get("Binds") or host.get("Devices") or host.get("CapAdd"):
        raise ProofFailure("container_boundary", check="attachments")
    if host.get("Mounts") not in (None, []):
        raise ProofFailure("unexpected_mount", check="HostConfig.Mounts")
    if host.get("LogConfig") != {"Type": "none", "Config": {}}:
        raise ProofFailure("container_boundary", check="LogConfig")
    mounts = value["mounts"]
    # Docker's --tmpfs map is separate from inspect's MountPoints-derived Mounts.
    # The exact map above and post-start kernel checks prove the scratch mounts.
    if type(mounts) is not list or mounts:
        raise ProofFailure("unexpected_mount", check="Mounts")


def full_scratch(cid: str, role: str, execute: Callable[..., str]) -> None:
    """Verify kernel allocation and flags, not only requested Docker options."""
    expected = FULL_TMPFS["db" if role == "db" else "worker"]
    paths = [*expected, "/dev/shm"]
    # The pinned Debian image resolves /var/run through its /run symlink.
    # Observe only these fixed destinations; never trust arbitrary resolved paths.
    canonical = {
        path: "/run/postgresql" if path == "/var/run/postgresql" else path for path in paths
    }
    command = "set -eu; " + "".join(
        f"stat -f -c '{path}|%T|%S|%b|%f|%c|%d' {path}; stat -c '{path}|%u|%g|%a' {path}; "
        f"printf '{path}|'; readlink -e -- {path}; "
        for path in paths
    )
    command += (
        "printf '%s\\n' '---mounts---'; awk '"
        + " || ".join(f'$5 == "{path}"' for path in canonical.values())
        + "' /proc/self/mountinfo"
    )
    raw = execute(["docker", "exec", cid, "sh", "-c", command])

    def refuse(reason: str, check: str, path: str | None, wanted: object, observed: object) -> None:
        raise ProofFailure(
            reason,
            check=check,
            scratch={"path": path, "check": check, "expected": wanted, "observed": observed},
        )

    try:
        stats, mount_rows = raw.split("\n---mounts---\n")
        lines = stats.splitlines()
        mounts = [line.split() for line in mount_rows.splitlines()]
        if len(lines) != 3 * len(paths):
            refuse("scratch_readback", "scratch_stat_rows", None, 3 * len(paths), len(lines))
        if len(mounts) != len(paths):
            refuse("scratch_readback", "scratch_mount_rows", None, len(paths), len(mounts))
        for index, path in enumerate(paths):
            values = lines[3 * index].split("|")
            ownership = lines[3 * index + 1].split("|")
            if lines[3 * index + 2].split("|") != [path, canonical[path]]:
                refuse("scratch_readback", "scratch_realpath", path, canonical[path], "mismatch")
            if len(values) != 7 or values[:2] != [path, "tmpfs"]:
                raise ProofFailure("scratch_readback", check="scratch_stat_shape")
            block, blocks, free, inodes, ifree = map(integer, values[2:])
            options = dict(
                option.split("=", 1) if "=" in option else (option, "")
                for option in expected.get(path, "size=64m,mode=1777").split(",")
            )
            size = int(options["size"][:-1]) * 1024 * 1024
            if block * blocks != size:
                refuse("scratch_allocation", "scratch_bytes", path, size, block * blocks)
            if not 0 < free <= blocks:
                refuse("scratch_allocation", "scratch_free_blocks", path, [1, blocks], free)
            if not 0 < ifree <= inodes:
                refuse("scratch_allocation", "scratch_free_inodes", path, [1, inodes], ifree)
            if "nr_inodes" in options and inodes != int(options["nr_inodes"]):
                refuse(
                    "scratch_allocation", "scratch_inodes", path, int(options["nr_inodes"]), inodes
                )
            wanted_ownership = [
                path,
                options.get("uid", "0"),
                options.get("gid", "0"),
                options["mode"].lstrip("0"),
            ]
            if ownership != wanted_ownership:
                if len(ownership) != 4:
                    refuse("scratch_allocation", "scratch_ownership_shape", path, 4, len(ownership))
                if ownership[0] != path:
                    refuse(
                        "scratch_allocation", "scratch_ownership_identity", path, path, "mismatch"
                    )
                for field, wanted, observed in zip(
                    ("scratch_uid", "scratch_gid", "scratch_mode"),
                    wanted_ownership[1:],
                    ownership[1:],
                    strict=True,
                ):
                    if observed != wanted:
                        number = (
                            int(observed) if re.fullmatch(r"0|[1-9][0-9]{0,38}", observed) else None
                        )
                        refuse("scratch_allocation", field, path, int(wanted), number)
            matching = [row for row in mounts if len(row) > 9 and row[4] == canonical[path]]
            if len(matching) != 1:
                refuse("scratch_mount", "scratch_mount_identity", path, 1, len(matching))
            row = matching[0]
            flags = set(row[5].split(","))
            if row[row.index("-") + 1] != "tmpfs":
                refuse("scratch_mount", "scratch_mount_type", path, "tmpfs", "mismatch")
            for flag in ("rw", "nosuid", "nodev"):
                if flag not in flags:
                    refuse("scratch_mount", "scratch_mount_" + flag, path, True, False)
            if ("noexec" in flags) != (path != "/tmp/ocwp-tests"):
                refuse(
                    "scratch_mount",
                    "scratch_mount_noexec",
                    path,
                    path != "/tmp/ocwp-tests",
                    "noexec" in flags,
                )
    except (ValueError, IndexError, KeyError) as error:
        raise ProofFailure("scratch_readback", check="scratch_format") from error


def full_reconcile(owned: Path, execute: Callable[..., str]) -> None:
    """Only exact manifest-owned names/images may be removed, even after ambiguous create."""
    ids = []
    for role in ("canary", "db", "worker"):
        path = owned.with_suffix(f".{role}.cid")
        if path.exists():
            ids.append(identifier(path.read_text().strip()))
    present = execute(["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"])
    all_ids = [identifier(value) for value in present.splitlines()]
    found = reconcile_owned(owned, execute) if owned.with_suffix(".owner.json").exists() else []
    if not set(ids).intersection(all_ids).issubset(found):
        raise ProofFailure("owned_identity_reconciliation")
    remove_owned(found, execute)


def full_identity(commit: str, worker_image: str, pg_image: str, execute: Callable[..., str]):
    from scripts.ci.verify_v01 import full_python_identity

    if source_query("head", execute) != commit or source_query("status", execute):
        raise ProofFailure("source_not_exact_clean_commit")
    tree = source_query("tree", execute)
    images = [
        execute(["docker", "image", "inspect", "--format", "{{.Id}}", name])
        for name in (worker_image, pg_image)
    ]
    if images != [
        os.environ.get("OCWP_FULL_PYTHON_IMAGE_ID"),
        os.environ.get("OCWP_FULL_PYTHON_PG_IMAGE_ID"),
    ]:
        raise ProofFailure("image_identity")
    if (
        execute(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                '{{index .Config.Labels "ocwp.source-tree"}}',
                images[0],
            ]
        )
        != tree
    ):
        raise ProofFailure("image_source_mismatch")
    return full_python_identity(
        commit=commit,
        tree=tree,
        image_id=images[0],
        pg_image_id=images[1],
        nonce=os.environ.get("OCWP_FULL_PYTHON_NONCE", ""),
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    )


def full_capture_record(cid: str, name: str, execute: Callable[..., str]):
    from scripts.ci.verify_v01 import read_full_python_value

    if name not in {"collection", "result"}:
        raise ProofFailure("record_name")
    reader = (
        "from pathlib import Path; import json; "
        "from scripts.ci.verify_v01 import read_full_python_json; "
        f"p=Path('/tmp/ocwp-proof/{name}.json'); "
        "v=read_full_python_json(p) if p.exists() else {'pending':True}; "
        "print(json.dumps(v,sort_keys=True,separators=(',',':')))"
    )
    raw = execute(
        ["docker", "exec", cid, "/app/.venv/bin/python", "-c", reader],
        limit=FULL_RECORD_LIMIT,
    )
    value = read_full_python_value(raw)
    return None if set(value) == {"pending"} and value["pending"] is True else value


def full_save_diagnostic(output, evidence: Path) -> None:
    """Retain only the already-hosted bounded spool after candidate stop/reap."""
    from scripts.ci.verify_v01 import write_full_python_json

    size = os.fstat(output.fileno()).st_size
    output.seek(0)
    raw = output.read(FULL_SPOOL_LIMIT)
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".ocwp-diagnostic-", dir=evidence.parent)
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(raw)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, evidence.parent / "diagnostic.txt")
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)
    write_full_python_json(
        evidence.parent / "diagnostic.json",
        {
            "schema": 1,
            "available": True,
            "retained_bytes": len(raw),
            "at_limit_or_truncated": size >= FULL_SPOOL_LIMIT,
        },
    )


def full_preflight_diagnostic(
    evidence: Path, identity: object, stage: str, role: str | None, error: BaseException
) -> None:
    """Retain only fixed preflight identifiers; never raw inspect/config output."""
    from scripts.ci.verify_v01 import write_full_python_json

    codes = {
        "source_not_exact_clean_commit",
        "image_identity",
        "image_source_mismatch",
        "owner_already_exists",
        "container_identity",
        "container_boundary",
        "unexpected_mount",
        "scratch_readback",
        "scratch_allocation",
        "scratch_mount",
        "effective_privileges_unavailable",
        "effective_privilege_boundary",
        "cgroup_unavailable",
        "limits_not_enforced",
        "memory_counter_invalid",
        "counter_invalid",
        "cpu_unavailable",
        "memory_events_unavailable",
        "pids_events_unavailable",
        "resource_pressure",
        "probe_invalid",
        "canary_readiness",
        "canary_process_observer",
        "canary_descendants_missing",
        "canary_cpu_budget",
        "cpu_budget",
        "cpu_counter_regressed",
        "command_timeout",
        "command_failed",
        "output_limit",
        "wall_budget",
        "interrupted",
        "database_readiness",
        "cleanup_failed",
    }
    fields = {
        "identity",
        "NetworkMode",
        "Privileged",
        "ReadonlyRootfs",
        "Memory",
        "MemorySwap",
        "NanoCpus",
        "PidsLimit",
        "ShmSize",
        "CgroupnsMode",
        "CapDrop",
        "IpcMode",
        "PidMode",
        "UTSMode",
        "PublishAllPorts",
        "SecurityOpt",
        "Tmpfs",
        "attachments",
        "LogConfig",
        "HostConfig.Mounts",
        "Mounts",
        "scratch_stat_rows",
        "scratch_mount_rows",
        "scratch_realpath",
        "scratch_stat_shape",
        "scratch_bytes",
        "scratch_free_blocks",
        "scratch_free_inodes",
        "scratch_inodes",
        "scratch_ownership_shape",
        "scratch_ownership_identity",
        "scratch_uid",
        "scratch_gid",
        "scratch_mode",
        "scratch_mount_identity",
        "scratch_mount_type",
        "scratch_mount_rw",
        "scratch_mount_nosuid",
        "scratch_mount_nodev",
        "scratch_mount_noexec",
        "scratch_format",
    }
    stages = {
        "identity",
        "ownership",
        "create",
        "inspect",
        "start",
        "privileges",
        "scratch",
        "probe",
        "canary",
        "database_readiness",
    }
    code = str(error) if isinstance(error, ProofFailure) else "invalid_evidence"
    check = error.check if isinstance(error, ProofFailure) else None
    returncode = error.returncode if isinstance(error, ProofFailure) else None
    value = {
        "schema": 1,
        "kind": "ocwp.full_python.preflight_failure",
        "status": "unqualified",
        "qualification": "not_a_receipt",
        "identity": identity,
        "stage": stage if stage in stages else "unavailable",
        "role": role if role in {"canary", "db", "worker"} else None,
        "failure": code if code in codes else "invalid_evidence",
        "failed_field": check if check in fields else None,
        "returncode": returncode
        if type(returncode) is int and -(2**31) <= returncode < 2**31
        else None,
    }
    detail = error.scratch if isinstance(error, ProofFailure) else None
    fixed_paths = {None, *FULL_TMPFS["worker"], *FULL_TMPFS["db"], "/dev/shm"}
    fixed_values = {"mismatch", "tmpfs", "/run/postgresql"} | (fixed_paths - {None})

    def scalar(item: object) -> bool:
        return (
            type(item) is bool
            or (type(item) is int and 0 <= item < 2**128)
            or (type(item) is str and item in fixed_values)
        )

    if (
        type(detail) is dict
        and set(detail) == {"path", "check", "expected", "observed"}
        and (detail["path"] is None or type(detail["path"]) is str)
        and detail["path"] in fixed_paths
        and detail["check"] == check
        and type(check) is str
        and check in fields
        and check.startswith("scratch_")
        and (detail["observed"] is None or scalar(detail["observed"]))
    ):
        wanted = detail["expected"]
        if scalar(wanted) or (
            check in {"scratch_free_blocks", "scratch_free_inodes"}
            and type(wanted) is list
            and len(wanted) == 2
            and all(type(item) is int and 0 <= item < 2**128 for item in wanted)
            and wanted[0] <= wanted[1]
        ):
            value["scratch"] = detail
    if len(json.dumps(value, sort_keys=True).encode("utf-8")) + 1 >= LIMIT:
        raise ProofFailure("preflight_diagnostic_limit")
    write_full_python_json(evidence.parent / "diagnostic.json", value)


def supervise_python(
    worker_image: str, pg_image: str, commit: str, evidence: Path, owned: Path
) -> None:
    from scripts.ci.verify_v01 import (
        FULL_FAILURE_CODES,
        FULL_POLICY,
        FULL_PYTHON_ARGS,
        FullPythonEvidenceError,
        validate_full_python_collection,
        validate_full_python_result,
        write_full_python_json,
    )

    started = time.monotonic()
    outer_deadline = started + FULL_OUTER_SECONDS
    deadline = outer_deadline - 900 - 55  # At most 65 seconds for contained setup.
    worker = None
    business = False
    child = None
    creation_uncertain = False
    stage = "identity"
    role = None
    report = {
        "schema": 1,
        "kind": "ocwp.full_python.receipt",
        "identity": None,
        "policy": FULL_POLICY,
        "status": "failed",
        "failure": "unrun",
        "collection": None,
        "result": None,
        "containment": None,
        "primary_cleanup": "pending",
        "independent_cleanup": "pending",
    }
    containment = {
        "canary": "pending",
        "worker_exit": None,
        "deadline": "unfinished",
        "stdout_bytes": 0,
        "source_read_only": False,
        "closed_network": False,
        "scratch_verified": False,
        "worker_stopped": False,
        "creation_uncertain": False,
        "resource_samples": {"worker": 0, "db": 0},
        "pressure_events": {"worker": 0, "db": 0},
        "final_probe": "pending",
    }
    report["containment"] = containment

    def stop() -> None:
        if worker is not None and not containment["worker_stopped"]:
            stop_deadline = min(outer_deadline, time.monotonic() + 20)

            def control(args, *, timeout=5):
                remaining = stop_deadline - time.monotonic()
                if remaining <= 0:
                    raise ProofFailure("worker_stop_unverified")
                return full_client(args, timeout=min(timeout, remaining))

            try:
                full_stop_worker(worker, control)
                containment["worker_stopped"] = True
            except (ProofFailure, OSError):
                # Later absence may clean up, but cannot prove the missed cutoff.
                report["failure"] = "worker_stop_unverified"
                with suppress(ProofFailure, OSError, ValueError):
                    full_reconcile(owned, control)
                raise ProofFailure("worker_stop_unverified") from None

    def execute(args, *, timeout=5, limit=LIMIT):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProofFailure("wall_budget")
        result = full_client(
            args,
            timeout=min(timeout, remaining),
            limit=limit,
            abort=stop if business and args[:2] == ["docker", "exec"] else None,
        )
        if time.monotonic() >= deadline:
            raise ProofFailure("wall_budget")
        return result

    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        raise ProofFailure("interrupted")

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    evidence.parent.mkdir(parents=True, exist_ok=True)
    write_full_python_json(evidence, report)  # Never reuse a previous receipt.
    try:
        identity = full_identity(commit, worker_image, pg_image, execute)
        report["identity"] = identity
        token = uuid4().hex
        images = {
            "db": identity["pg_image_id"],
            "worker": identity["image_id"],
            "canary": identity["image_id"],
        }
        stage = "ownership"
        if owned.with_suffix(".owner.json").exists():
            raise ProofFailure("owner_already_exists")
        owned.with_suffix(".owner.json").write_text(json.dumps({"token": token, "images": images}))
        containers = {}
        before = {}
        for role in ("canary", "db", "worker"):
            memory, pids = (1024, 128) if role == "db" else (512, 64)
            network = f"container:{containers['db']}" if role == "worker" else "none"
            args = [
                "docker",
                "create",
                "--name",
                f"ocwp-quote-{token}-{role}",
                "--cidfile",
                str(owned.with_suffix(f".{role}.cid")),
                "--label",
                f"ocwp.quote-micro={token}",
                "--pull",
                "never",
                "--cgroupns",
                "private",
                "--ipc",
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
                "--memory",
                f"{memory}m",
                "--memory-swap",
                f"{memory}m",
                "--pids-limit",
                str(pids),
                "--network",
                network,
                "--shm-size",
                "64m",
            ]
            for path, options in FULL_TMPFS["db" if role == "db" else "worker"].items():
                args.extend(["--tmpfs", f"{path}:{options}"])
            if role == "db":
                args.extend(
                    [
                        "--user",
                        "postgres",
                        "--env",
                        "POSTGRES_PASSWORD=ocwp-synthetic",
                        "--env",
                        "POSTGRES_USER=ocwp",
                        "--env",
                        "POSTGRES_DB=ocwp_quote_full_test",
                        images[role],
                        "-c",
                        "max_connections=20",
                        "-c",
                        "shared_buffers=64MB",
                    ]
                )
            else:
                args.extend(
                    [
                        "--user",
                        "10001:10001",
                        "--workdir",
                        "/app",
                        "--entrypoint",
                        "/app/.venv/bin/python",
                        images[role],
                        "-c",
                        "import time; time.sleep(1200)",
                    ]
                )
            creation_uncertain = True
            stage = "create"
            cid = identifier(execute(args))
            creation_uncertain = False
            containers[role] = cid
            if role == "worker":
                worker = cid
            stage = "inspect"
            full_inspect(cid, images[role], token, network, role, execute)
            stage = "start"
            execute(["docker", "start", cid])
            stage = "privileges"
            effective_privileges(cid, role != "db", execute)
            stage = "scratch"
            full_scratch(cid, role, execute)
            stage = "probe"
            resources = parse_probe(
                execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids
            )
            if role == "canary":
                stage = "canary"
                canary = cancellation_canary(cid, execute)
                cpu_delta({"canary": resources["cpu_usec"]}, {"canary": canary["cpu_usec"]}, 10)
                containment["canary"] = "passed"
                owned.with_suffix(".canary.cid").unlink()
            else:
                before[role] = resources["cpu_usec"]
                containment["resource_samples"][role] += 1
        stage = "database_readiness"
        role = "db"
        while True:
            try:
                execute(
                    [
                        "docker",
                        "exec",
                        containers["db"],
                        "pg_isready",
                        "-U",
                        "ocwp",
                        "-d",
                        "ocwp_quote_full_test",
                    ],
                    timeout=2,
                )
                break
            except ProofFailure:
                if time.monotonic() >= deadline:
                    raise ProofFailure("database_readiness") from None
                time.sleep(0.1)
        containment.update(source_read_only=True, closed_network=True, scratch_verified=True)
        business = True
        deadline = min(time.monotonic() + FULL_SECONDS, outer_deadline - 55)
        environment = [
            "PATH=/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME=/tmp/ocwp-tests",
            "TMPDIR=/tmp/ocwp-tests",
            "PYTHONDONTWRITEBYTECODE=1",
            "PYTHONUNBUFFERED=1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "OCWP_FULL_PYTHON=contained",
            "OCWP_FULL_PYTHON_IDENTITY="
            + json.dumps(identity, sort_keys=True, separators=(",", ":")),
            "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic@127.0.0.1:5432/ocwp_quote_full_test",
            "OCWP_INVENTORY_READ_EVIDENCE_DIR=/tmp/ocwp-tests/evidence",
        ]

        def cap_output() -> None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (FULL_SPOOL_LIMIT, FULL_SPOOL_LIMIT))

        def sample() -> None:
            current = {}
            for role in ("db", "worker"):
                memory, pids = (1024, 128) if role == "db" else (512, 64)
                resources = parse_probe(
                    execute(["docker", "exec", containers[role], "sh", "-c", PROBE]), memory, pids
                )
                full_scratch(containers[role], role, execute)
                containment["resource_samples"][role] += 1
                current[role] = resources["cpu_usec"]
            cpu_delta(before, current, FULL_CPU_SECONDS)
            cpu_delta(dict.fromkeys(current, 0), current, FULL_CPU_SECONDS)
            if sum(current.values()) + canary["cpu_usec"] > FULL_CPU_SECONDS * 1_000_000:
                raise ProofFailure("cpu_budget")
            before.update(current)

        with tempfile.TemporaryFile() as output:
            child = subprocess.Popen(
                [
                    "docker",
                    "exec",
                    worker,
                    "env",
                    "-i",
                    *environment,
                    "/app/.venv/bin/python",
                    "-m",
                    "pytest",
                    *FULL_PYTHON_ARGS,
                ],
                stdout=output,
                stderr=output,
                start_new_session=True,
                preexec_fn=cap_output,
            )
            try:
                while child.poll() is None:
                    if time.monotonic() >= deadline:
                        raise ProofFailure("wall_budget")
                    containment["stdout_bytes"] = os.fstat(output.fileno()).st_size
                    if containment["stdout_bytes"] >= FULL_SPOOL_LIMIT:
                        raise ProofFailure("output_limit")
                    sample()
                    if report["collection"] is None:
                        collection = full_capture_record(worker, "collection", execute)
                        if collection is not None:
                            validate_full_python_collection(collection, identity)
                            report["collection"] = collection
                    time.sleep(min(1, max(0, deadline - time.monotonic())))
                containment["worker_exit"] = child.returncode
                containment["stdout_bytes"] = os.fstat(output.fileno()).st_size
                if child.returncode or containment["stdout_bytes"] >= FULL_SPOOL_LIMIT:
                    raise ProofFailure("python_failed")
                sample()
                for name in ("collection", "result"):
                    record = full_capture_record(worker, name, execute)
                    if name == "collection":
                        validate_full_python_collection(record, identity)
                    report[name] = record
                validate_full_python_result(report["result"], identity, report["collection"])
                sample()  # Include record-reader resource use in the final observation.
                if time.monotonic() >= deadline:
                    raise ProofFailure("wall_budget")
                containment.update(deadline="completed", final_probe="passed")
                report["failure"] = "independent_cleanup_pending"
            finally:
                # Never let Popen.__exit__ wait while candidate descendants remain live.
                try:
                    stop()
                finally:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=2)
                    if containment["worker_stopped"]:
                        full_save_diagnostic(output, evidence)
                    else:
                        write_full_python_json(
                            evidence.parent / "diagnostic.json",
                            {
                                "schema": 1,
                                "available": False,
                                "retained_bytes": 0,
                                "at_limit_or_truncated": False,
                            },
                        )
    except (
        ProofFailure,
        FullPythonEvidenceError,
        ValueError,
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        if not business:
            with suppress(ProofFailure, OSError, ValueError):
                full_preflight_diagnostic(evidence, report["identity"], stage, role, error)
        code = (
            str(error)
            if isinstance(error, (ProofFailure, FullPythonEvidenceError))
            else "invalid_evidence"
        )
        aliases = {
            "source_not_exact_clean_commit": "source_identity",
            "image_identity": "source_identity",
            "image_source_mismatch": "source_identity",
            "python_failed": "worker_failed",
            "creation_outcome_uncertain": "creation_uncertain",
        }
        code = aliases.get(code, code)
        report["failure"] = code if code in FULL_FAILURE_CODES else "containment_failed"
    finally:
        containment["creation_uncertain"] = creation_uncertain
        try:
            stop()
        except (ProofFailure, OSError):
            report["failure"] = "worker_stop_unverified"
        cleanup_deadline = min(outer_deadline, time.monotonic() + 55)

        def cleanup_execute(args, *, timeout=5):
            remaining = cleanup_deadline - time.monotonic()
            if remaining <= 0:
                raise ProofFailure("cleanup_deadline")
            return full_client(args, timeout=min(timeout, remaining))

        try:
            full_reconcile(owned, cleanup_execute)
            report["primary_cleanup"] = "verified_absent"
            if child is not None:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
        except (ProofFailure, ValueError, OSError):
            report["primary_cleanup"] = "failed"
            report["failure"] = "cleanup_failed"
        finally:
            if child is not None:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
        if creation_uncertain:
            report["failure"] = "creation_uncertain"
        write_full_python_json(evidence, report)
    if report["failure"] != "independent_cleanup_pending":
        raise ProofFailure("full_python_unqualified")


def finalize_python(worker_image: str, pg_image: str, commit: str, evidence: Path, owned: Path):
    from scripts.ci.verify_v01 import (
        FullPythonEvidenceError,
        read_full_python_json,
        validate_full_python_receipt,
        write_full_python_json,
    )

    deadline = time.monotonic() + 55

    def execute(args, *, timeout=5):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProofFailure("independent_cleanup_deadline")
        return full_client(args, timeout=min(timeout, remaining))

    report = None
    cleanup = {
        "schema": 1,
        "kind": "ocwp.full_python.independent_cleanup",
        "status": "unqualified",
        "expected_commit": commit,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "scope": "manifest_owned_canary_database_worker",
        "owner_manifest_present": owned.with_suffix(".owner.json").exists(),
        "outcome": "unfinished",
        "build_resource_cleanup": "not_assessed",
        "qualification": "not_a_receipt",
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    cleanup_path = evidence.parent / "independent-cleanup.json"
    write_full_python_json(cleanup_path, cleanup)
    try:
        full_reconcile(owned, execute)
        cleanup["outcome"] = (
            "verified_absent" if cleanup["owner_manifest_present"] else "no_ownership_manifest"
        )
        write_full_python_json(cleanup_path, cleanup)
        if not cleanup["owner_manifest_present"]:
            raise ProofFailure("ownership_unrecorded")
        identity = full_identity(commit, worker_image, pg_image, execute)
        report = read_full_python_json(evidence)
        validate_full_python_receipt(report, identity, allow_pending_cleanup=True)
        report.update(status="passed", failure=None, independent_cleanup="verified_absent")
        validate_full_python_receipt(report, identity)
        if time.monotonic() >= deadline:
            raise ProofFailure("independent_cleanup_deadline")
        write_full_python_json(evidence, report)
    except (ProofFailure, FullPythonEvidenceError, ValueError, OSError):
        if cleanup["outcome"] == "unfinished":
            cleanup["outcome"] = "failed"
        if report is not None:
            report["status"] = "failed"
            report["independent_cleanup"] = (
                "verified_absent" if cleanup["outcome"] == "verified_absent" else "failed"
            )
            if (
                report.get("failure") is None
                or report.get("failure") == "independent_cleanup_pending"
            ):
                report["failure"] = "invalid_evidence"
            write_full_python_json(evidence, report)
        raise ProofFailure("full_python_unqualified") from None
    finally:
        write_full_python_json(cleanup_path, cleanup)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--pg-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--owned", type=Path, required=True)
    parser.add_argument("--single-record-feasibility", action="store_true")
    parser.add_argument("--full-python", action="store_true")
    parser.add_argument("--finalize-full-python", action="store_true")
    args = parser.parse_args()
    try:
        if sum((args.single_record_feasibility, args.full_python, args.finalize_full_python)) > 1:
            raise ProofFailure("mode_conflict")
        if args.full_python or args.finalize_full_python:
            operation = finalize_python if args.finalize_full_python else supervise_python
            operation(args.worker_image, args.pg_image, args.commit, args.evidence, args.owned)
            return
        supervise(
            args.worker_image,
            args.pg_image,
            args.commit,
            args.evidence,
            args.owned,
            single_record=args.single_record_feasibility,
        )
    except ProofFailure:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
