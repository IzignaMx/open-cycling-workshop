"""Quote-only containment, plus one separately gated fixed online-profile trial."""

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


class OnlineGate:
    """Host-owned clocks for the single reviewed 39-step quote trial."""

    def __init__(self, end: float, now: float) -> None:
        self.end = end
        self.deadline = min(end, now + 20)
        self.ordinal = 0
        self.state = "bootstrap"
        self.complete = False
        self.operation_started = now
        self.completed_seconds: list[float] = []

    def observe(self, raw: str, now: float) -> str | None:
        if not math.isfinite(now) or now >= self.deadline:
            raise ProofFailure("online_operation_deadline")
        value = json.loads(raw)
        if (
            type(value) is not dict
            or set(value) != {"ordinal", "state"}
            or type(value["ordinal"]) is not int
            or type(value["state"]) is not str
        ):
            raise ProofFailure("online_handshake")
        ordinal, state = value["ordinal"], value["state"]
        if (ordinal, state) == (self.ordinal, self.state):
            return None
        if (
            state == "ready"
            and self.state in {"bootstrap", "done"}
            and ordinal == self.ordinal + 1
            and ordinal <= 39
        ):
            self.ordinal, self.state = ordinal, state
            self.operation_started = now
            self.deadline = min(self.end, now + 20)
            return f"grant:{ordinal}"
        if state == "done" and self.state == "ready" and ordinal == self.ordinal:
            self.completed_seconds.append(round(now - self.operation_started, 6))
            self.state = state
            self.complete = ordinal == 39
            self.deadline = min(self.end, now + 20)
            return f"ack:{ordinal}"
        raise ProofFailure("online_handshake")


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


def online_result(raw: str) -> dict[str, object]:
    value = json.loads(raw)
    fixed = dict(
        new_operations=33,
        revisions=32,
        decisions=1,
        lines_per_revision=100,
        target_edges=1000,
        service_order_state="DIAGNOSIS",
        service_order_version=1,
        lock_timeout_ms=15000,
        statement_timeout_ms=20000,
        maximum_capacity_qualified=False,
        revision33_rejected=True,
        exact_retries=3,
    )
    fields = set(fixed) | {
        "operation_seconds",
        "process_cpu_seconds",
        "record_bytes",
        "history_bytes",
        "raw_request_bytes",
    }
    if type(value) is not dict or set(value) != fields:
        raise ProofFailure("online_result_shape")
    if any(type(value[k]) is not type(v) or value[k] != v for k, v in fixed.items()):
        raise ProofFailure("online_result_value")
    for key, count, limit in (("record_bytes", 33, 262144), ("raw_request_bytes", 33, 131072)):
        sizes = value[key]
        if (
            type(sizes) is not list
            or len(sizes) != count
            or any(type(n) is not int or not 0 < n <= limit for n in sizes)
        ):
            raise ProofFailure("online_result_bytes")
    if (
        type(value["history_bytes"]) is not int
        or value["history_bytes"] != sum(value["record_bytes"]) + 34
        or not 0 < value["history_bytes"] <= 8650786
    ):
        raise ProofFailure("online_result_framing")
    durations = value["operation_seconds"]
    if (
        type(durations) is not list
        or len(durations) != 39
        or any(
            type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n < 20
            for n in durations
        )
    ):
        raise ProofFailure("online_result_timings")
    cpu = value["process_cpu_seconds"]
    if type(cpu) not in (int, float) or not math.isfinite(cpu) or not 0 <= cpu < 80:
        raise ProofFailure("online_result_cpu")
    return value


def supervise(
    worker_image: str,
    pg_image: str,
    commit: str,
    evidence: Path,
    owned: Path,
    *,
    single_record: bool = False,
    online_once: bool = False,
) -> None:
    started = time.monotonic()
    command_deadline = started + (20 if online_once else 900)
    online_gate: OnlineGate | None = None
    cpu_budget = 240 if online_once else 600
    interrupted = False
    online_started = False
    final_deadline = started + 120
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
        "mode": "online_32_plus_1_once"
        if online_once
        else "single_record_feasibility"
        if single_record
        else "micro_only",
        "maximum_capacity_qualified": False,
        "status": "failed",
        "phase": "setup_and_containment",
    }

    def interrupt(_signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = True
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
            inspect_owned(cid, image, label, network, execute)
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
        deadline = min(time.monotonic() + 30, command_deadline)
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
            micro_deadline = (
                min(started + 100, time.monotonic() + 80) if online_once else time.monotonic() + 20
            )
            if online_once:
                execute(
                    [
                        "docker",
                        "exec",
                        ids[1],
                        "sh",
                        "-c",
                        'printf \'%s\' \'{"ordinal":0,"state":"bootstrap"}\' '
                        "> /tmp/quote-online-state.json",
                    ]
                )
                online_gate = OnlineGate(micro_deadline, time.monotonic())
            command_deadline = (
                min(micro_deadline, online_gate.deadline) if online_gate else micro_deadline
            )
            online_started = online_once
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
                        "services/platform/tests/quotes/test_quote_online_once_postgres.py"
                        if online_once
                        else (
                            "services/platform/tests/quotes/"
                            "test_quote_record_feasibility_postgres.py"
                        )
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
                    if time.monotonic() >= command_deadline:
                        raise ProofFailure("wall_budget")
                    if os.fstat(output.fileno()).st_size >= LIMIT:
                        raise ProofFailure("output_limit")
                    if online_gate:
                        observed = execute(
                            ["docker", "exec", ids[1], "cat", "/tmp/quote-online-state.json"]
                        )
                        grant = online_gate.observe(observed, time.monotonic())
                        command_deadline = min(micro_deadline, online_gate.deadline)
                        report["online_progress"] = {
                            "ordinal": online_gate.ordinal,
                            "state": online_gate.state,
                        }
                        report["host_operation_seconds"] = list(online_gate.completed_seconds)
                        if grant:
                            execute(
                                [
                                    "docker",
                                    "exec",
                                    ids[1],
                                    "sh",
                                    "-c",
                                    f"printf '%s' '{grant}' > /tmp/quote-online-permit.tmp && "
                                    "mv /tmp/quote-online-permit.tmp /tmp/quote-online-permit",
                                ]
                            )
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
                    cpu_delta(previous, current, cpu_budget)
                    cpu_delta(dict.fromkeys(current, 0), current, cpu_budget)
                    previous = current
                    time.sleep(0.1)
                if time.monotonic() >= command_deadline:
                    raise ProofFailure("wall_budget")
                if child.returncode or os.fstat(output.fileno()).st_size >= LIMIT:
                    raise ProofFailure("micro_failed", returncode=child.returncode)
                if online_gate and not online_gate.complete:
                    raise ProofFailure("online_incomplete")
                report["micro_wall_seconds"] = round(time.monotonic() - micro_started, 3)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=2)
        if online_once:
            final_deadline = min(started + 120, time.monotonic() + 20)
        command_deadline = final_deadline if online_once else started + 900
        # Containers remain alive: read final cgroup events after workload exit.
        final = {
            role: parse_probe(execute(["docker", "exec", cid, "sh", "-c", PROBE]), memory, pids)
            for cid, role, memory, pids in [(ids[0], "db", 768, 128), (ids[1], "worker", 512, 64)]
        }
        cpu_delta(previous, {role: value["cpu_usec"] for role, value in final.items()}, cpu_budget)
        final_cpu = {role: value["cpu_usec"] for role, value in final.items()}
        lifetime_cpu = cpu_delta(dict.fromkeys(final_cpu, 0), final_cpu, cpu_budget)
        report["lifetime_cpu_usec"] = lifetime_cpu
        if lifetime_cpu + canary_resources["cpu_usec"] > cpu_budget * 1_000_000:
            raise ProofFailure("cpu_budget")
        report["observed_workload_cpu_usec"] = cpu_delta(before, final_cpu, cpu_budget)
        report["containers"] = final
        raw_result = execute(["docker", "exec", ids[1], "cat", "/tmp/quote-micro-result.json"])
        micro = (
            online_result(raw_result)
            if online_once
            else micro_result(raw_result, single_record=single_record)
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
        # After workload failure or termination, only identity reconciliation/removal runs.
        if online_once:
            command_deadline = (
                min(started + 150, time.monotonic() + 30)
                if interrupted
                else min(final_deadline, time.monotonic() + 20)
            )
        if online_started and report["status"] != "micro_passed_not_capacity":
            # Client death does not stop in-container Python or an active SQL statement.
            # Stop both already-validated exact IDs before any owner reconciliation.
            stopped = True
            for cid in reversed(ids[:2]):
                try:
                    execute(["docker", "kill", "--signal", "KILL", cid], timeout=5)
                except (ProofFailure, OSError, ValueError):
                    stopped = False
            for cid in reversed(ids[:2]):
                try:
                    if (
                        execute(["docker", "inspect", "--format", "{{.State.Running}}", cid])
                        != "false"
                    ):
                        stopped = False
                except (ProofFailure, OSError, ValueError):
                    stopped = False
            report["workload_stop"] = "verified_not_running" if stopped else "failed_or_unverified"
        try:
            for role in ("canary", "db", "worker"):
                cidfile = owned.with_suffix(f".{role}.cid")
                if cidfile.exists():
                    cid = identifier(cidfile.read_text().strip())
                    if cid not in ids:
                        ids.append(cid)
            if owned.with_suffix(".owner.json").exists():
                for cid in reconcile_owned(owned, execute if online_once else None):
                    if cid not in ids:
                        ids.append(cid)
            if online_once:
                remove_owned(ids, execute)
            else:
                remove_owned(ids)
            if creation_uncertain:
                raise ProofFailure("creation_outcome_uncertain")
            if online_once and time.monotonic() >= started + 120:
                report["status"] = "failed"
            report["cleanup"] = "verified_absent"
        except (ProofFailure, OSError, ValueError):
            report["cleanup"] = "failed"
            report["status"] = "failed"
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(report, sort_keys=True) + "\n")
    if report["status"] != "micro_passed_not_capacity":
        raise ProofFailure("micro_unqualified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--pg-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--owned", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--single-record-feasibility", action="store_true")
    mode.add_argument("--online-once", action="store_true")
    args = parser.parse_args()
    try:
        supervise(
            args.worker_image,
            args.pg_image,
            args.commit,
            args.evidence,
            args.owned,
            single_record=args.single_record_feasibility,
            online_once=args.online_once,
        )
    except ProofFailure:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
