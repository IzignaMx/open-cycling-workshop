"""Fixed contained H/S orchestration, separate from full-suite qualification.

All Docker/process/file effects are behind explicit runtime construction/main.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.ci import quote_capacity_micro as containment
from scripts.ci.quote_ownership_evidence import (
    SECOND,
    decode_receipt,
    encode_receipt,
    identity_from_environment,
    validate_cleanup,
    validate_fixture_preparation,
    validate_observation,
)
from scripts.ci.quote_ownership_worker import PipeChannel, WorkerRefusal, _empty_case

ROOT = Path(__file__).resolve().parents[2]


def container_args(
    role: str, image: str, token: str, owned: Path, db: str | None = None
) -> list[str]:
    if role not in ("canary", "db", "worker") or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise WorkerRefusal("identity")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise WorkerRefusal("identity")
    memory, pids = containment.full_role_limits(role)
    network = "none"
    if role == "worker":
        network = "container:" + containment.identifier(db or "")
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
    for path, options in containment.FULL_TMPFS["db" if role == "db" else "worker"].items():
        args.extend(["--tmpfs", f"{path}:{options}"])
    if role == "db":
        args.extend(
            [
                "--user",
                "postgres",
                "--env",
                "POSTGRES_USER=postgres",
                "--env",
                "POSTGRES_DB=postgres",
                "--env",
                "POSTGRES_PASSWORD=ocwp-synthetic",
                image,
                "-c",
                "max_connections=20",
                "-c",
                "shared_buffers=64MB",
                "-c",
                "max_wal_size=128MB",
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
                image,
                "-c",
                "import time; time.sleep(1200)",
            ]
        )
    return args


def _initial_report(identity: dict[str, object]) -> dict[str, Any]:
    return {
        "schema": 1,
        "kind": "ocwp.quote_ownership.receipt",
        "identity": identity,
        "status": "failed",
        "failure": "preflight",
        "setup_ns": 0,
        "elapsed_ns": 0,
        "observer": {
            **dict.fromkeys(
                ("reserved", "read_only", "transaction_idle", "closed", "reaped"), False
            ),
            **dict.fromkeys(("process", "reserved_setup_ns", "closed_ns", "reaped_ns")),
        },
        "cases": [_empty_case("H"), _empty_case("S")],
        "resources": dict.fromkeys(
            (
                "worker_peak_bytes",
                "pg_peak_bytes",
                "worker_processes",
                "pg_processes",
                "pressure_events",
            ),
            0,
        ),
        "primary_cleanup": "unknown",
        "independent_cleanup": "pending",
    }


def supervise_measurement(runtime: Any, setup_deadline_ns: int) -> dict[str, Any]:
    """No fresh setup clock: runtime inherits the original pre-guard deadline."""
    report = _initial_report(runtime.expected)
    try:
        if not 0 < setup_deadline_ns - runtime.now() <= 65 * SECOND:
            raise WorkerRefusal("setup_deadline")
        runtime.source(setup_deadline_ns)
        runtime.setup(setup_deadline_ns)
        observation, resources = runtime.observe(setup_deadline_ns)
        validate_observation(observation, runtime.expected)
        report.update(observation)
        report["resources"] = resources
        report["status"] = "pending_cleanup" if observation["status"] == "observed" else "failed"
    except Exception as error:
        report["status"] = "failed"
        report["failure"] = error.code if isinstance(error, WorkerRefusal) else "preflight"
    finally:
        try:
            absent = runtime.cleanup(runtime.now() + 55 * SECOND)
            report["primary_cleanup"] = "verified_absent" if absent else "unknown"
            if not absent:
                report.update(status="failed", failure="cleanup_unknown")
        except Exception:
            report.update(status="failed", failure="cleanup_unknown", primary_cleanup="unknown")
        # A late/malformed resource/lifetime claim never becomes a passing receipt.
        try:
            encode_receipt(report, runtime.expected)
        except ValueError:
            report.update(status="failed", failure="protocol")
        runtime.save(report)
    return report


def _read_closed(path: Path) -> dict[str, Any]:
    from scripts.ci.quote_ownership_actions_adapter import _directory_fd, _same_root
    from scripts.ci.quote_ownership_evidence import _decode
    from scripts.ci.quote_ownership_staging import _read

    directory = _directory_fd(path.parent.absolute(), create=False)
    try:
        raw = _read(directory, path.name)
        _same_root(path.parent.absolute(), directory)
        return _decode(raw, 16384)
    finally:
        os.close(directory)


def _write_closed(path: Path, value: dict[str, Any]) -> None:
    from scripts.ci.quote_ownership_actions_adapter import _directory_fd, _same_root, _write_at
    from scripts.ci.quote_ownership_staging import _regular

    directory = _directory_fd(path.parent.absolute(), create=True)
    try:
        try:
            previous = _regular(directory, path.name)
        except FileNotFoundError:
            previous = None
        replacement = path.name + ".replace"
        _write_at(directory, replacement, value)
        _same_root(path.parent.absolute(), directory)
        if previous is not None:
            current = _regular(directory, path.name)
            if (previous.st_dev, previous.st_ino) != (current.st_dev, current.st_ino):
                raise WorkerRefusal("identity")
        else:
            try:
                os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise WorkerRefusal("identity")
        os.replace(replacement, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        _same_root(path.parent.absolute(), directory)
    except Exception:
        raise WorkerRefusal("identity") from None
    finally:
        os.close(directory)


def _ownership_hints(owned: Path) -> bool:
    paths = [
        owned,
        *(
            owned.with_suffix(suffix)
            for suffix in (".owner.json", ".canary.cid", ".db.cid", ".worker.cid")
        ),
    ]
    return any(path.exists() or path.is_symlink() for path in paths) or any(
        parent.is_symlink() for parent in owned.parents
    )


def _reconcile_fixed(owned: Path, manifest: dict[str, Any], execute: Callable[..., str]) -> None:
    """Immutable caller binding only; filesystem hints never grant removal authority."""
    from scripts.ci.quote_ownership_actions_adapter import _directory_fd, _same_root
    from scripts.ci.quote_ownership_staging import _read

    hinted = []
    directory = _directory_fd(owned.parent.absolute(), create=False)
    try:
        for role in ("canary", "db", "worker"):
            name = owned.with_suffix(f".{role}.cid").name
            try:
                raw = _read(directory, name).decode("ascii").strip()
            except FileNotFoundError:
                continue
            if not re.fullmatch(r"[0-9a-f]{0,64}", raw):
                raise WorkerRefusal("identity")
            if len(raw) == 64:
                hinted.append(raw)
        _same_root(owned.parent.absolute(), directory)
    finally:
        os.close(directory)
    token, images = manifest["token"], manifest["images"]
    all_ids = [
        containment.identifier(cid)
        for cid in execute(
            ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"]
        ).splitlines()
    ]
    query = [
        "docker",
        "ps",
        "--all",
        "--no-trunc",
        "--filter",
        f"label=ocwp.quote-micro={token}",
        "--format",
        "{{.ID}}",
    ]
    found = [containment.identifier(cid) for cid in execute(query).splitlines()]
    if len(found) > 3 or len(set(found)) != len(found):
        raise WorkerRefusal("identity")
    allowed = {f"{image}|{token}|/ocwp-quote-{token}-{role}" for role, image in images.items()}
    for cid in found:
        result = execute(
            [
                "docker",
                "inspect",
                "--format",
                '{{.Image}}|{{index .Config.Labels "ocwp.quote-micro"}}|{{.Name}}',
                cid,
            ]
        )
        if result not in allowed:
            raise WorkerRefusal("identity")
    if not set(hinted).intersection(all_ids).issubset(found):
        raise WorkerRefusal("identity")
    containment.remove_owned(found, execute)
    if execute(query):
        raise WorkerRefusal("cleanup_unknown")


class HostRuntime:
    def __init__(
        self,
        worker_image: str,
        pg_image: str,
        commit: str,
        guard: Path,
        owned: Path,
        evidence: Path,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        self.env = dict(os.environ if env is None else env)
        self.expected = identity_from_environment(self.env)
        self.worker_image, self.pg_image, self.commit = worker_image, pg_image, commit
        self.guard, self.owned, self.evidence = guard, owned, evidence
        self.now = time.monotonic_ns
        self.containers: dict[str, str] = {}
        self.host_child: subprocess.Popen[bytes] | None = None
        self.resources = dict.fromkeys(
            (
                "worker_peak_bytes",
                "pg_peak_bytes",
                "worker_processes",
                "pg_processes",
                "pressure_events",
            ),
            0,
        )
        self._paths()
        if (worker_image, pg_image, commit) != (
            self.expected["worker_image"],
            self.expected["pg_image"],
            self.expected["commit"],
        ):
            raise WorkerRefusal("identity")

    def _paths(self) -> None:
        expected = [
            (self.evidence, ROOT / "artifacts/quote-ownership/receipt.json"),
            (self.guard, ROOT / "artifacts/quote-ownership/guard-setup.json"),
            (self.owned, Path(self.env["RUNNER_TEMP"]) / "quote-ownership-owned.json"),
        ]
        for path, wanted in expected:
            if path.absolute() != wanted.absolute():
                raise WorkerRefusal("identity")
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise WorkerRefusal("identity")

    def client(self, deadline: int) -> Callable[..., str]:
        def execute(args: list[str], *, timeout: float = 5, **kwargs: Any) -> str:
            remaining = (deadline - self.now()) / SECOND
            cap = 15 if args[:2] == ["docker", "create"] and "canary" in " ".join(args[:8]) else 5
            if remaining <= 0:
                raise WorkerRefusal("setup_deadline")
            result = containment.full_client(args, timeout=min(timeout, cap, remaining), **kwargs)
            if self.now() >= deadline:
                raise WorkerRefusal("setup_deadline")
            return result

        return execute

    def source(self, deadline: int) -> None:
        execute = self.client(deadline)
        record = _read_closed(self.guard)
        if (
            set(record) != {"schema", "phase", "status", "binding"}
            or record["schema"] != 1
            or record["phase"] != "setup"
            or record["status"] != "passed"
        ):
            raise WorkerRefusal("identity")
        binding = record["binding"]
        for key in (
            "repository",
            "workflow_path",
            "ref",
            "commit",
            "tree",
            "workflow_id",
            "run_id",
            "run_number",
            "run_attempt",
        ):
            if binding.get(key) != self.expected[key] or type(binding.get(key)) is not type(
                self.expected[key]
            ):
                raise WorkerRefusal("identity")
        if binding.get("authorization_id") != self.expected["authorization"]:
            raise WorkerRefusal("identity")
        if (
            containment.source_query("head", execute) != self.commit
            or containment.source_query("status", execute)
            or containment.source_query("tree", execute) != self.expected["tree"]
        ):
            raise WorkerRefusal("identity")
        for image in (self.worker_image, self.pg_image):
            if execute(["docker", "image", "inspect", "--format", "{{.Id}}", image]) != image:
                raise WorkerRefusal("identity")
            if (
                execute(
                    [
                        "docker",
                        "image",
                        "inspect",
                        "--format",
                        '{{index .Config.Labels "ocwp.source-tree"}}',
                        image,
                    ]
                )
                != self.expected["tree"]
            ):
                raise WorkerRefusal("identity")
        base = self.env["OCWP_OWNERSHIP_PG_BASE_IMAGE_ID"]
        reference = self.env["OCWP_OWNERSHIP_PG_BASE_REFERENCE"]
        if execute(["docker", "image", "inspect", "--format", "{{.Id}}", reference]) != base:
            raise WorkerRefusal("identity")
        files = {
            "dockerfile": "infra/docker/quote-ownership-postgres.fixture.Dockerfile",
            "initializer": "infra/compose/postgres-init/10-application-role.sql",
            "public_fixture": "tests/fixtures/quote-ownership/public-synthetic-password.txt",
        }
        preparation = {
            "schema": 1,
            "kind": "ocwp.quote_ownership.fixture_preparation",
            "identity": self.expected,
            "pg_base_image": base,
            "pg_base_reference": reference,
            "files": {
                key: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for key, path in files.items()
            },
        }
        validate_fixture_preparation(preparation, self.expected)
        _write_closed(self.evidence.parent / "fixture-preparation.json", preparation)

    def sample(self, deadline: int) -> None:
        execute = self.client(deadline)
        for role, prefix in (("worker", "worker"), ("db", "pg")):
            raw = execute(
                [
                    "docker",
                    "exec",
                    self.containers[role],
                    "sh",
                    "-c",
                    containment.PROBE
                    + "printf '\\n---ownership-pids---\\n'; cat /sys/fs/cgroup/pids.current",
                ]
            )
            sections = raw.split("\n---ownership-pids---\n")
            if len(sections) != 2:
                raise WorkerRefusal("protocol")
            memory, pids = containment.full_role_limits(role)
            counters = containment.parse_probe(sections[0], memory, pids)
            count = containment.integer(sections[1].strip())
            if not 1 <= count <= pids:
                raise WorkerRefusal("pressure")
            self.resources[prefix + "_peak_bytes"] = max(
                self.resources[prefix + "_peak_bytes"], counters["memory_peak"]
            )
            self.resources[prefix + "_processes"] = max(
                self.resources[prefix + "_processes"], count
            )

    def _manifest(self) -> dict[str, Any]:
        return {
            "token": self.expected["nonce"],
            "images": {
                "canary": self.worker_image,
                "db": self.pg_image,
                "worker": self.worker_image,
            },
        }

    def setup(self, deadline: int) -> None:
        execute = self.client(deadline)
        owner = self.owned.with_suffix(".owner.json")
        if owner.exists() or owner.is_symlink():
            raise WorkerRefusal("identity")
        _write_closed(owner, self._manifest())  # Ownership precedes every possible create.
        for role in ("canary", "db", "worker"):
            image = self.pg_image if role == "db" else self.worker_image
            args = container_args(
                role, image, str(self.expected["nonce"]), self.owned, self.containers.get("db")
            )
            cid = containment.identifier(execute(args, timeout=15 if role == "canary" else 5))
            self.containers[role] = cid
            network = "container:" + self.containers["db"] if role == "worker" else "none"
            containment.full_inspect(
                cid, image, str(self.expected["nonce"]), network, role, execute
            )
            execute(["docker", "start", cid])
            containment.effective_privileges(cid, role != "db", execute)
            containment.full_scratch(cid, role, execute)
            memory, pids = containment.full_role_limits(role)
            containment.parse_probe(
                execute(["docker", "exec", cid, "sh", "-c", containment.PROBE]), memory, pids
            )
            if role == "canary":
                containment.cancellation_canary(cid, execute)
                self.owned.with_suffix(".canary.cid").unlink()
        while True:
            try:
                execute(
                    [
                        "docker",
                        "exec",
                        self.containers["db"],
                        "pg_isready",
                        "-U",
                        "postgres",
                        "-d",
                        "postgres",
                    ],
                    timeout=2,
                )
                break
            except containment.ProofFailure:
                if self.now() >= deadline:
                    raise WorkerRefusal("setup_deadline") from None
                time.sleep(min(0.1, max(0, (deadline - self.now()) / SECOND)))
        self.sample(deadline)

    def observe(self, deadline: int) -> tuple[dict[str, Any], dict[str, int]]:
        environment = {
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp/ocwp-tests",
            "TMPDIR": "/tmp/ocwp-tests",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "OCWP_OWNERSHIP_CONTAINED": "1",
            "OCWP_OWNERSHIP_IDENTITY": json.dumps(self.expected),
            "OCWP_OWNERSHIP_SETUP_DEADLINE_NS": str(deadline),
        }
        args = [
            "docker",
            "exec",
            "-i",
            self.containers["worker"],
            "env",
            "-i",
            *(f"{k}={v}" for k, v in environment.items()),
            "/app/.venv/bin/python",
            "-m",
            "scripts.ci.quote_ownership_worker",
            "--role",
            "owner",
            "--case",
            "setup",
        ]
        self.host_child = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        if self.host_child.stdin is None or self.host_child.stdout is None:
            raise WorkerRefusal("protocol")
        channel = PipeChannel(
            self.host_child.stdout.fileno(), self.host_child.stdin.fileno(), self.expected, "host"
        )
        ready = channel.receive("owner", deadline, case="setup")
        if ready["event"] != "RESERVED" or self.now() >= deadline:
            raise WorkerRefusal("setup_deadline")
        go = self.now()
        end = go + 26 * SECOND
        channel.send("GO", "setup", {}, min(deadline, end))
        self.sample(end)
        message = channel.receive("owner", end, case="teardown")
        if message["event"] != "RESULT":
            raise WorkerRefusal("protocol")
        result = message["payload"]
        self.host_child.wait(timeout=max(0, (end - self.now()) / SECOND))
        if self.host_child.returncode != 0 and result["status"] != "failed":
            raise WorkerRefusal("protocol")
        self.sample(end)
        result["elapsed_ns"] = max(result["elapsed_ns"], self.now() - go)
        validate_observation(result, self.expected)
        if self.now() >= end:
            raise WorkerRefusal("experiment_deadline")
        return result, self.resources

    def cleanup(self, deadline: int) -> bool:
        owner = self.owned.with_suffix(".owner.json")
        if not owner.exists():
            if _ownership_hints(self.owned):
                raise WorkerRefusal("cleanup_unknown")
            return False
        if _read_closed(owner) != self._manifest():
            raise WorkerRefusal("identity")
        execute = self.client(deadline)
        _reconcile_fixed(self.owned, self._manifest(), execute)
        if self.host_child is not None:
            if self.host_child.poll() is None:
                # Exact owned containers are absent before the owned Docker client is reaped.
                self.host_child.kill()
            self.host_child.wait(timeout=max(0, min(2, (deadline - self.now()) / SECOND)))
            for pipe in (self.host_child.stdin, self.host_child.stdout):
                if pipe is not None:
                    pipe.close()
        if self.now() >= deadline:
            raise WorkerRefusal("cleanup_unknown")
        return True

    def save(self, report: dict[str, Any]) -> None:
        encode_receipt(report, self.expected)
        _write_closed(self.evidence, report)


def seal_receipt(
    report: dict[str, Any], identity: dict[str, object], absent: bool
) -> dict[str, Any]:
    """Independent absence never upgrades an already failed measurement."""
    encode_receipt(report, identity)
    sealed = dict(report)
    sealed["independent_cleanup"] = "verified_absent" if absent else "unknown"
    if not absent:
        sealed.update(status="failed", failure="cleanup_unknown")
    elif report["status"] == "pending_cleanup":
        sealed.update(status="passed", failure=None)
    encode_receipt(sealed, identity)
    return sealed


def finalize_measurement(runtime: HostRuntime) -> dict[str, Any]:
    started = runtime.now()
    deadline = started + 55 * SECOND
    owner = runtime.owned.with_suffix(".owner.json")
    present = owner.exists() or owner.is_symlink()
    cleanup: dict[str, Any] = {
        "schema": 1,
        "kind": "ocwp.quote_ownership.independent_cleanup",
        "identity": runtime.expected,
        "expected_commit": runtime.expected["commit"],
        "run_id": runtime.expected["run_id"],
        "run_attempt": runtime.expected["run_attempt"],
        "owner_manifest_present": present,
        "owner_token": None,
        "outcome": "unknown",
        "elapsed_ns": 0,
        "receipt_sha256": None,
    }
    try:
        absent = runtime.cleanup(deadline)
        cleanup["outcome"] = (
            "verified_absent" if absent else ("unknown" if present else "not_started")
        )
        if absent:
            cleanup["owner_token"] = runtime.expected["nonce"]
        if runtime.evidence.exists():
            report = decode_receipt(
                json.dumps(_read_closed(runtime.evidence)).encode(), runtime.expected
            )
            try:
                runtime.source(deadline)
            except Exception:
                report.update(status="failed", failure="identity")
            sealed = seal_receipt(report, runtime.expected, absent)
            runtime.save(sealed)
            # Hash actual final bytes, including the anchored writer's newline.
            from scripts.ci.quote_ownership_actions_adapter import _directory_fd, _same_root
            from scripts.ci.quote_ownership_staging import _read

            directory = _directory_fd(runtime.evidence.parent.absolute(), create=False)
            try:
                raw = _read(directory, runtime.evidence.name)
                _same_root(runtime.evidence.parent.absolute(), directory)
            finally:
                os.close(directory)
            cleanup["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
    except Exception:
        cleanup["outcome"] = "unknown"
        # Never manufacture a passing replacement for malformed/missing evidence.
    cleanup["elapsed_ns"] = max(0, runtime.now() - started)
    if runtime.now() >= deadline:
        cleanup["outcome"] = "unknown"
    if cleanup["outcome"] == "unknown":
        cleanup["receipt_sha256"] = None
        # Best-effort fixed metadata downgrade only, never renewed runtime cleanup.
        # If writing fails, bundle staging independently rejects passed/unknown.
        try:
            failed = decode_receipt(
                json.dumps(_read_closed(runtime.evidence)).encode(), runtime.expected
            )
            failed.update(status="failed", failure="cleanup_unknown", independent_cleanup="unknown")
            runtime.save(failed)
        except Exception:
            pass
    validate_cleanup(cleanup, runtime.expected)
    _write_closed(runtime.evidence.parent / "cleanup.json", cleanup)
    return cleanup


def _early_cleanup_record(env: dict[str, str], owned: Path, evidence: Path) -> None:
    """No valid owner identity means no Docker action, never guessed cleanup."""
    value = {
        "schema": 1,
        "kind": "ocwp.quote_ownership.independent_cleanup",
        "identity": None,
        "expected_commit": env.get("GITHUB_SHA"),
        "run_id": env.get("GITHUB_RUN_ID"),
        "run_attempt": int(env.get("GITHUB_RUN_ATTEMPT", "0")),
        "owner_manifest_present": (
            owned.with_suffix(".owner.json").exists()
            or owned.with_suffix(".owner.json").is_symlink()
            or any(part.is_symlink() for part in owned.parents)
        ),
        "owner_token": None,
        "outcome": "unknown",
        "elapsed_ns": 0,
        "receipt_sha256": None,
    }
    if not value["owner_manifest_present"] and not _ownership_hints(owned):
        value["outcome"] = "not_started"
    validate_cleanup(value, None)
    _write_closed(evidence.parent / "cleanup.json", value)


def main() -> int:
    import argparse
    import signal

    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--supervise", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--worker-image", required=True)
    parser.add_argument("--pg-image", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--guard-evidence", required=True, type=Path)
    parser.add_argument("--owned", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    env = dict(os.environ)

    def interrupted(_signal: int, _frame: Any) -> None:
        raise WorkerRefusal("interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        # Fixed paths checked even when preparation failed before identity existed.
        expected_paths = (
            (args.evidence, ROOT / "artifacts/quote-ownership/receipt.json"),
            (args.guard_evidence, ROOT / "artifacts/quote-ownership/guard-setup.json"),
            (args.owned, Path(env["RUNNER_TEMP"]) / "quote-ownership-owned.json"),
        )
        for actual, expected in expected_paths:
            if actual.absolute() != expected.absolute() or any(
                part.is_symlink() for part in (actual, *actual.parents)
            ):
                return 1
        try:
            runtime = HostRuntime(
                args.worker_image,
                args.pg_image,
                args.commit,
                args.guard_evidence,
                args.owned,
                args.evidence,
                env=env,
            )
        except Exception:
            if args.finalize:
                _early_cleanup_record(env, args.owned, args.evidence)
            return 1
        if args.finalize:
            outcome = finalize_measurement(runtime)
            return 0 if outcome["outcome"] in ("verified_absent", "not_started") else 1
        deadline = int(env["OCWP_OWNERSHIP_SETUP_DEADLINE_NS"])
        report = supervise_measurement(runtime, deadline)
        return 0 if report["status"] == "pending_cleanup" else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
