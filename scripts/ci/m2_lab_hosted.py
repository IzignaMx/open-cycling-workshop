"""Prepared, bounded M2 hosted supervisor. Never invoked by imports or unit tests.

No generic workload/DSN/network selector. Publication/execution require separate
approval; this module only operates on a fresh nonce-bound synthetic laboratory.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.quote_capacity_micro import run as bounded_command

ROLES = ("db", "api", "connector")
ROOT = Path("/dev/shm")
MAX_EVIDENCE = 1024 * 1024
REASONS = {
    "clean",
    "blocked",
    "completed",
    "not_started",
    "invalid_plan",
    "identity",
    "containment",
    "command",
    "ownership",
    "cleanup",
    "filesystem",
    "evidence",
    "deadline",
    "source",
    "runtime",
    "private_input",
}


class LabFailure(RuntimeError):
    def __init__(self, reason: str = "blocked") -> None:
        self.reason = reason if reason in REASONS else "blocked"
        super().__init__(self.reason)


@dataclass(frozen=True)
class RunPlan:
    nonce: str
    commit: str
    tree: str
    image: str
    pg_image: str
    uid: int
    gid: int

    def __post_init__(self) -> None:
        values = (
            (self.nonce, r"[0-9a-f]{32}"),
            (self.commit, r"[0-9a-f]{40}"),
            (self.tree, r"[0-9a-f]{40}"),
            (self.image, r"sha256:[0-9a-f]{64}"),
            (self.pg_image, r"sha256:[0-9a-f]{64}"),
        )
        if any(
            type(value) is not str or re.fullmatch(pattern, value) is None
            for value, pattern in values
        ):
            raise LabFailure("invalid_plan")
        if any(type(value) is not int or not 0 < value < 2**31 for value in (self.uid, self.gid)):
            raise LabFailure("invalid_plan")

    @property
    def root(self) -> Path:
        return ROOT / ("ocwp-m2-" + self.nonce)

    def name(self, role: str) -> str:
        if role not in ROLES:
            raise LabFailure("invalid_plan")
        return f"ocwp-m2-{self.nonce}-{role}"

    def labels(self, role: str) -> dict[str, str]:
        self.name(role)
        return {"ocwp.m2.run": self.nonce, "ocwp.m2.role": role, "ocwp.source-tree": self.tree}

    def image_for(self, role: str) -> str:
        self.name(role)
        return self.pg_image if role == "db" else self.image


def mount_specs(plan: RunPlan, role: str) -> list[tuple[str, str, bool]]:
    root = plan.root
    if role == "db":
        return [(str(root / "pg-password"), "/run/m2-pg-password", True)]
    if role == "api":
        return [
            (str(root / "api-private"), "/run/m2-private", True),
            (str(root / "tls"), "/run/m2-tls", True),
            (str(root / "api"), "/run/m2-api", False),
            (str(root / "credential"), "/run/m2-credential", False),
        ]
    if role == "connector":
        return [
            (str(root / "api"), "/run/m2-api", True),
            (str(root / "public"), "/run/m2-public", True),
            (str(root / "credential"), "/run/m2-credential", True),
        ]
    raise LabFailure("invalid_plan")


def create_command(plan: RunPlan, role: str, db_id: str = "") -> list[str]:
    plan.name(role)
    if role == "api" and re.fullmatch(r"[0-9a-f]{64}", db_id) is None:
        raise LabFailure("identity")
    memory, cpus, pids = {
        "db": (768, "1", 128),
        "api": (512, "1", 64),
        "connector": (128, "0.5", 32),
    }[role]
    args = [
        "docker",
        "create",
        "--name",
        plan.name(role),
        "--pull",
        "never",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--cgroupns",
        "private",
        "--ipc",
        "private",
        "--log-driver",
        "none",
        "--cpus",
        cpus,
        "--memory",
        f"{memory}m",
        "--memory-swap",
        f"{memory}m",
        "--pids-limit",
        str(pids),
        "--network",
        "container:" + db_id if role == "api" else "none",
        "--user",
        "postgres" if role == "db" else f"{plan.uid}:{plan.gid}",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
    ]
    for key, value in plan.labels(role).items():
        args += ["--label", f"{key}={value}"]
    for source, target, readonly in mount_specs(plan, role):
        args += [
            "--mount",
            f"type=bind,src={source},dst={target}" + (",readonly" if readonly else ""),
        ]
    if role == "db":
        args += [
            "--tmpfs",
            "/var/lib/postgresql:rw,nosuid,nodev,size=256m,mode=1777",
            "--tmpfs",
            "/var/run/postgresql:rw,nosuid,nodev,size=16m,mode=1777",
            "--env",
            "POSTGRES_USER=m2_lab",
            "--env",
            "POSTGRES_DB=postgres",
            "--env",
            "POSTGRES_PASSWORD_FILE=/run/m2-pg-password",
            plan.pg_image,
            "postgres",
            "-c",
            "cluster_name=m2_" + plan.nonce,
            "-c",
            "listen_addresses=127.0.0.1",
            "-c",
            "log_statement=none",
        ]
    else:
        if role == "connector":
            args += [
                "--tmpfs",
                f"/run/m2-store:rw,noexec,nosuid,nodev,size=16m,mode=0700,uid={plan.uid},gid={plan.gid}",
            ]
        args += [
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--workdir",
            "/app",
            plan.image,
            "/app/.venv/bin/python",
            "-m",
            "tests.labs.m2.runtime_" + ("service" if role == "api" else "client"),
        ]
    return args


def owned_identity(plan: RunPlan, role: str, row: dict[str, Any]) -> str:
    cid = row.get("Id")
    labels = row.get("Config", {}).get("Labels", {})
    if (
        type(cid) is not str
        or re.fullmatch(r"[0-9a-f]{64}", cid) is None
        or row.get("Image") != plan.image_for(role)
        or row.get("Name") != "/" + plan.name(role)
        or any(labels.get(key) != value for key, value in plan.labels(role).items())
    ):
        raise LabFailure("identity")
    return cid


def reconcile_container(
    plan: RunPlan, role: str, execute: Callable[..., str] = bounded_command
) -> str | None:
    found = execute(
        [
            "docker",
            "ps",
            "--all",
            "--no-trunc",
            "--filter",
            "name=^/" + plan.name(role) + "$",
            "--format",
            "{{.ID}}",
        ],
        timeout=5,
    ).splitlines()
    if not found:
        return None
    if len(found) != 1 or re.fullmatch(r"[0-9a-f]{64}", found[0]) is None:
        raise LabFailure("identity")
    raw = json.loads(execute(["docker", "inspect", "--format", "{{json .}}", found[0]], timeout=5))
    if not isinstance(raw, dict) or owned_identity(plan, role, raw) != found[0]:
        raise LabFailure("identity")
    return found[0]


def verify_containment(plan: RunPlan, role: str, row: dict[str, Any], db_id: str = "") -> None:
    owned_identity(plan, role, row)
    host = row.get("HostConfig", {})
    memory, cpu, pids = {
        "db": (768, 1_000_000_000, 128),
        "api": (512, 1_000_000_000, 64),
        "connector": (128, 500_000_000, 32),
    }[role]
    expected_network = "container:" + db_id if role == "api" else "none"
    if (
        host.get("NetworkMode") != expected_network
        or host.get("ReadonlyRootfs") is not True
        or host.get("Privileged") is not False
        or host.get("CapAdd")
        or set(host.get("CapDrop") or []) != {"ALL"}
        or host.get("SecurityOpt") != ["no-new-privileges:true"]
        or host.get("CgroupnsMode") != "private"
        or host.get("LogConfig", {}).get("Type") != "none"
        or host.get("Memory") != memory * 1024**2
        or host.get("MemorySwap") != memory * 1024**2
        or host.get("NanoCpus") != cpu
        or host.get("PidsLimit") != pids
        or host.get("PortBindings")
        or host.get("Devices")
        or host.get("PidMode")
        or host.get("IpcMode") != "private"
    ):
        raise LabFailure("containment")
    tmpfs = {"/tmp": "rw,noexec,nosuid,nodev,size=64m,mode=1777"}
    if role == "db":
        tmpfs.update(
            {
                "/var/lib/postgresql": "rw,nosuid,nodev,size=256m,mode=1777",
                "/var/run/postgresql": "rw,nosuid,nodev,size=16m,mode=1777",
            }
        )
    elif role == "connector":
        tmpfs["/run/m2-store"] = (
            f"rw,noexec,nosuid,nodev,size=16m,mode=0700,uid={plan.uid},gid={plan.gid}"
        )
    if host.get("Tmpfs") != tmpfs:
        raise LabFailure("containment")
    mounts = row.get("Mounts")
    if type(mounts) is not list or any(type(m) is not dict for m in mounts):
        raise LabFailure("containment")
    destinations: set[str] = set()
    actual = []
    for mount in mounts:
        target = mount.get("Destination")
        if type(target) is not str or target in destinations or type(mount.get("RW")) is not bool:
            raise LabFailure("containment")
        destinations.add(target)
        if mount.get("Type") == "bind":
            actual.append((mount.get("Source"), target, not mount["RW"]))
        elif mount.get("Type") != "tmpfs" or target not in tmpfs or not mount["RW"]:
            raise LabFailure("containment")
    if set(actual) != set(mount_specs(plan, role)) or len(actual) != len(mount_specs(plan, role)):
        raise LabFailure("containment")
    user = row.get("Config", {}).get("User")
    if user != ("postgres" if role == "db" else f"{plan.uid}:{plan.gid}"):
        raise LabFailure("containment")


SERVICE_CHECKS = frozenset(
    {
        "scope",
        "current_grants",
        "rotation",
        "revocation",
        "closed_response",
        "postgresql_18_4",
        "fresh_database",
        "row_lock_timeout",
        "statement_timeout",
        "transaction_timeout",
        "pool_recovered",
        "revoke_before_read",
        "read_before_revoke",
    }
)
CHECKS = SERVICE_CHECKS | frozenset(
    {
        "network_isolation",
        "tls_hostname",
        "tls_trust",
        "projection_disposed",
        "containment",
        "database_cleanup",
    }
)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise LabFailure("evidence")
        value[key] = item
    return value


def parse_json(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError) as error:
        raise LabFailure("evidence") from error
    if not isinstance(value, dict):
        raise LabFailure("evidence")
    return value


def safe_parents(path: Path) -> None:
    # Reject symlinks at every existing ancestor, not just the final filename.
    for parent in (path.parent, *path.parent.parents):
        if parent.is_symlink():
            raise LabFailure("filesystem")


def read_json(path: Path, maximum: int = 65536) -> dict[str, Any]:
    safe_parents(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size > maximum
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) & 0o022
        ):
            raise LabFailure("filesystem")
        raw = os.read(descriptor, maximum + 1)
    finally:
        os.close(descriptor)
    if len(raw) > maximum:
        raise LabFailure("filesystem")
    return parse_json(raw)


def write_json(path: Path, value: dict[str, Any]) -> None:
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(data) > 65536:
        raise LabFailure("evidence")
    safe_parents(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise LabFailure("filesystem")
    descriptor, temporary = tempfile.mkstemp(prefix=".m2-json-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def check_evidence(directory: Path) -> int:
    safe_parents(directory / "result.json")
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != {
        "result.json",
        "cleanup.json",
    }:
        raise LabFailure("evidence")
    identity = {"commit", "tree", "nonce"}
    shared = {"schema", "status", "reason"}
    records = []
    total = 0
    for name in ("result.json", "cleanup.json"):
        value = read_json(directory / name, MAX_EVIDENCE)
        specific = {"checks"} if name == "result.json" else {"containers_absent", "root_removed"}
        if (
            set(value) != shared | specific | (identity if identity <= set(value) else set())
            or type(value.get("schema")) is not int
            or value["schema"] != 1
            or value.get("status") not in ("passed", "failed")
            or value.get("reason") not in REASONS
        ):
            raise LabFailure("evidence")
        for key, size in (("commit", 40), ("tree", 40), ("nonce", 32)):
            if key in value and (
                type(value[key]) is not str
                or re.fullmatch("[0-9a-f]{" + str(size) + "}", value[key]) is None
            ):
                raise LabFailure("evidence")
        if name == "result.json":
            checks = value["checks"]
            if (
                type(checks) is not dict
                or set(checks) - CHECKS
                or any(type(item) is not bool for item in checks.values())
            ):
                raise LabFailure("evidence")
            complete = set(checks) == CHECKS and all(checks.values())
        else:
            if any(type(value[key]) is not bool for key in specific):
                raise LabFailure("evidence")
            complete = value["containers_absent"] and value["root_removed"]
        if value["status"] == "passed" and (not complete or not identity <= set(value)):
            raise LabFailure("evidence")
        records.append(value)
        total += (directory / name).stat().st_size
    if any(records[0].get(key) != records[1].get(key) for key in identity) or total > MAX_EVIDENCE:
        raise LabFailure("evidence")
    return total


def identity_fields(plan: RunPlan) -> dict[str, str]:
    return {"commit": plan.commit, "tree": plan.tree, "nonce": plan.nonce}


def load_owned(path: Path) -> tuple[RunPlan, dict[str, Any]]:
    value = read_json(path)
    if set(value) != {"schema", "plan", "root_identity", "directories", "containers"}:
        raise LabFailure("ownership")
    if type(value["schema"]) is not int or value["schema"] != 1 or type(value["plan"]) is not dict:
        raise LabFailure("ownership")
    if set(value["plan"]) != {"nonce", "commit", "tree", "image", "pg_image", "uid", "gid"}:
        raise LabFailure("ownership")
    plan = RunPlan(**value["plan"])
    if plan.uid != os.getuid() or plan.gid != os.getgid():
        raise LabFailure("ownership")
    return plan, value


def cleanup_receipt(owned_path: Path, output: Path) -> bool:
    identity: dict[str, str] = {}
    success = False
    reason = "ownership"
    result = {"containers_absent": False, "root_removed": False}
    try:
        plan, manifest = load_owned(owned_path)
        identity = identity_fields(plan)
        from scripts.ci.m2_lab_cleanup import cleanup

        result = cleanup(plan, manifest)
        success = result == {"containers_absent": True, "root_removed": True}
        reason = "clean" if success else "cleanup"
    except Exception as error:
        # Never print command output, SQL, private file contents or exception text.
        reason = error.reason if isinstance(error, LabFailure) else "cleanup"
    if not identity:
        try:
            previous = read_json(output.with_name("result.json"))
            for key, size in (("commit", 40), ("tree", 40), ("nonce", 32)):
                value = previous.get(key)
                if type(value) is not str or re.fullmatch(f"[0-9a-f]{{{size}}}", value) is None:
                    raise LabFailure("identity")
                identity[key] = value
        except Exception:
            identity = {}
    write_json(
        output,
        {
            "schema": 1,
            **identity,
            "status": "passed" if success else "failed",
            "reason": reason,
            **result,
        },
    )
    if not output.with_name("result.json").exists():
        write_json(
            output.with_name("result.json"),
            {
                "schema": 1,
                **identity,
                "status": "failed",
                "reason": "not_started",
                "checks": {},
            },
        )
    return success


def main(arguments: list[str] | None = None) -> int:
    import argparse
    import secrets
    import signal

    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    runtime = subcommands.add_parser("run")
    for name in ("image", "pg-image", "commit", "tree", "owned", "evidence"):
        runtime.add_argument("--" + name, required=True)
    clean = subcommands.add_parser("cleanup")
    clean.add_argument("--owned", required=True)
    clean.add_argument("--evidence", required=True)
    proof = subcommands.add_parser("evidence")
    proof.add_argument("--directory", required=True)
    args = parser.parse_args(arguments)
    try:
        if args.action == "evidence":
            check_evidence(Path(args.directory))
            return 0
        output = Path(args.evidence)
        if output.name != ("result.json" if args.action == "run" else "cleanup.json"):
            raise LabFailure("evidence")
        owned = Path(args.owned)
        if args.action == "cleanup":
            return 0 if cleanup_receipt(owned, output) else 1
        plan = RunPlan(
            secrets.token_hex(16),
            args.commit,
            args.tree,
            args.image,
            args.pg_image,
            os.getuid(),
            os.getgid(),
        )
        checks: dict[str, bool] = {}
        passed = False
        reason = "runtime"

        def terminated(_signum: int, _frame: Any) -> None:
            raise LabFailure("deadline")

        previous = signal.signal(signal.SIGTERM, terminated)
        try:
            from scripts.ci.m2_lab_runtime import run

            checks = run(plan, owned, output)
            passed = set(checks) == CHECKS and all(value is True for value in checks.values())
            reason = "completed" if passed else "runtime"
        except Exception as error:
            reason = error.reason if isinstance(error, LabFailure) else "runtime"
        finally:
            signal.signal(signal.SIGTERM, previous)
            write_json(
                output,
                {
                    "schema": 1,
                    **identity_fields(plan),
                    "status": "passed" if passed else "failed",
                    "reason": reason,
                    "checks": checks,
                },
            )
            clean_passed = cleanup_receipt(owned, output.with_name("cleanup.json"))
        return 0 if passed and clean_passed else 1
    except Exception:
        # Closed diagnostics only. Failure evidence is independently attempted by
        # the always() cleanup step; hard runner termination is never called clean.
        print("M2 laboratory refused", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Runtime and cleanup import this canonical module. Use its exception class
    # at the script boundary too, preserving closed reason codes without exposing
    # arbitrary exception text from a second __main__ module instance.
    from scripts.ci.m2_lab_hosted import main as canonical_main

    raise SystemExit(canonical_main())
