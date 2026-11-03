"""Future-only fixed M2 orchestration; imports and fake-executor tests launch nothing.

The CLI owns independent destructive cleanup and final evidence. This module
only stops the API gracefully to observe its database-cleanup receipt.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.ci.m2_lab_hosted import (
    ROLES,
    LabFailure,
    Progress,
    RunPlan,
    create_command,
    parse_json,
    read_json,
    safe_parents,
    validate_api_projection,
    verify_containment,
)
from scripts.ci.quote_capacity_micro import run as bounded_command

# 760s runtime + 90s cleanup + 30s reserve fit the outer 880s command.
RUNTIME_SECONDS = 760
DIRECTORIES = ("ca", "tls", "public", "api-private", "api", "credential")


def _identity(path: Path) -> dict[str, int]:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise LabFailure("filesystem")
    return {
        "dev": info.st_dev,
        "ino": info.st_ino,
        "uid": info.st_uid,
        "mode": stat.S_IMODE(info.st_mode),
    }


def _new_file(path: Path, data: bytes, mode: int = 0o600) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise LabFailure("filesystem")
            view = view[count:]
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)


def _save_owned(path: Path, value: dict[str, Any], *, initial: bool = False) -> None:
    safe_parents(path)
    payload = json.dumps(value, sort_keys=True).encode("ascii")
    if initial:
        _new_file(path, payload)
        return
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        raise LabFailure("ownership")
    temporary = path.with_name(path.name + ".tmp")
    _new_file(temporary, payload)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _cert_mode(path: Path, mode: int) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or not 0 < info.st_size <= 16384
    ):
        raise LabFailure("private_input")
    path.chmod(mode)


def _private_inputs(plan: RunPlan, command: Callable[..., str]) -> None:
    root = plan.root
    password = secrets.token_hex(32).encode("ascii")
    _new_file(root / "pg-password", password, 0o444)
    _new_file(root / "api-private/pg-password", password, 0o400)
    _new_file(
        root / "api-private/run.json",
        json.dumps(
            {
                "schema": 1,
                "nonce": plan.nonce,
                "source_commit": plan.commit,
                "source_tree": plan.tree,
            },
            sort_keys=True,
        ).encode("ascii"),
        0o400,
    )
    _new_file(
        root / "ca/san.cnf",
        b"subjectAltName=DNS:ocwp-m2-api\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n",
    )
    ca, tls = root / "ca", root / "tls"
    command(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=OCWP-M2-Ephemeral",
            "-keyout",
            str(ca / "ca.key"),
            "-out",
            str(ca / "ca.crt"),
        ],
        timeout=30,
    )
    _cert_mode(ca / "ca.key", 0o600)
    _cert_mode(ca / "ca.crt", 0o644)
    command(
        [
            "openssl",
            "req",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-subj",
            "/CN=ocwp-m2-api",
            "-keyout",
            str(tls / "api.key"),
            "-out",
            str(ca / "api.csr"),
        ],
        timeout=30,
    )
    _cert_mode(tls / "api.key", 0o400)
    _cert_mode(ca / "api.csr", 0o644)
    command(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(ca / "api.csr"),
            "-CA",
            str(ca / "ca.crt"),
            "-CAkey",
            str(ca / "ca.key"),
            "-set_serial",
            "1",
            "-days",
            "1",
            "-extfile",
            str(ca / "san.cnf"),
            "-out",
            str(tls / "api.crt"),
        ],
        timeout=30,
    )
    _cert_mode(tls / "api.crt", 0o400)
    _new_file(root / "public/ca.crt", (ca / "ca.crt").read_bytes(), 0o444)


def _api_value(plan: RunPlan) -> dict[str, Any]:
    path = plan.root / "credential/api-status.json"
    safe_parents(path)
    info = path.parent.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise LabFailure("filesystem")
    # Reject on the first unknown/fourth entry; never enumerate an unbounded directory.
    for count, item in enumerate(path.parent.iterdir()):
        if count >= 3 or item.name not in {"credential", "scope.json", "api-status.json"}:
            raise LabFailure("filesystem")
    value = read_json(path, exact_mode=0o600)
    if (
        set(value)
        != {
            "schema",
            "nonce",
            "source_commit",
            "source_tree",
            "phase",
            "stage",
            "checks",
            "database_cleanup_complete",
        }
        or type(value["schema"]) is not int
        or value["schema"] != 2
    ):
        raise LabFailure("evidence")
    if (
        value["nonce"] != plan.nonce
        or value["source_commit"] != plan.commit
        or value["source_tree"] != plan.tree
    ):
        raise LabFailure("identity")
    projection = {
        key: value[key] for key in ("phase", "stage", "checks", "database_cleanup_complete")
    }
    validate_api_projection(projection)
    return projection


def snapshot(plan: RunPlan, progress: Progress) -> None:
    """Single bounded regular-file read inside the reserved second; no retries."""
    observation, value = "unavailable", None
    if time.monotonic() < progress.deadline:
        try:
            value = _api_value(plan)
            observation = "valid"
        except FileNotFoundError:
            observation = "absent"
        except LabFailure as error:
            observation = {"identity": "identity_mismatch", "filesystem": "filesystem"}.get(
                error.reason, "invalid"
            )
        except OSError:
            observation = "filesystem"
        except Exception:
            observation = "unavailable"
        if time.monotonic() >= progress.deadline:
            observation, value = "unavailable", None
    progress.api = {
        "observation": observation,
        "snapshot": value if observation == "valid" else None,
    }


def _status(plan: RunPlan, phase: str) -> dict[str, bool]:
    value = _api_value(plan)
    if value["phase"] == "preparing" and phase == "ready":
        raise FileNotFoundError
    if value["phase"] != phase:
        raise LabFailure("runtime")
    return {key: True for key in value["checks"]}


def run(
    plan: RunPlan,
    owned: Path,
    evidence: Path,
    *,
    execute: Callable[..., str] = bounded_command,
    progress: Progress | None = None,
) -> dict[str, bool]:
    """Observe this exact synthetic run. Never publish a passed final receipt here."""
    del evidence  # The CLI combines our observations with independently verified cleanup.
    progress = Progress() if progress is None else progress
    deadline = progress.deadline - 1  # Reserve one second within 760 for the pre-cleanup snapshot.

    def check_deadline() -> None:
        if time.monotonic() >= deadline:
            raise LabFailure("deadline")

    def command(args: list[str], *, timeout: float = 5) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LabFailure("deadline")
        result = execute(args, timeout=min(timeout, remaining))
        check_deadline()
        return result

    def inspect(role: str, cid: str, db_id: str = "") -> dict[str, Any]:
        row = parse_json(command(["docker", "inspect", "--format", "{{json .}}", cid]))
        if not isinstance(row, dict) or row.get("Id") != cid:
            raise LabFailure("identity")
        verify_containment(plan, role, row, db_id)
        return row

    phase = "source"
    progress.enter("source")
    previous_umask = os.umask(0o077)
    try:
        if plan.uid != os.getuid() or plan.gid != os.getgid():
            raise LabFailure("identity")
        if (
            command(["git", "--no-optional-locks", "rev-parse", "HEAD"]) != plan.commit
            or command(["git", "--no-optional-locks", "rev-parse", "HEAD^{tree}"]) != plan.tree
            or command(["git", "--no-optional-locks", "status", "--porcelain"])
        ):
            raise LabFailure("source")
        progress.finish()
        progress.enter("images")
        phase = "identity"
        for image in (plan.image, plan.pg_image):
            row = parse_json(
                command(["docker", "image", "inspect", "--format", "{{json .}}", image])
            )
            if not isinstance(row, dict) or row.get("Id") != image:
                raise LabFailure("identity")
            if image == plan.image:
                labels = row.get("Config", {}).get("Labels", {})
                if (
                    labels.get("org.opencontainers.image.revision") != plan.commit
                    or labels.get("org.opencontainers.image.tree") != plan.tree
                ):
                    raise LabFailure("source")
        progress.finish()
        progress.enter("workspace")
        phase = "ownership"
        manifest: dict[str, Any] = {
            "schema": 1,
            "plan": asdict(plan),
            "root_identity": None,
            "directories": {},
            "containers": dict.fromkeys(ROLES),
        }
        _save_owned(owned, manifest, initial=True)
        plan.root.mkdir(mode=0o700)
        manifest["root_identity"] = _identity(plan.root)
        _save_owned(owned, manifest)
        for name in DIRECTORIES:
            (plan.root / name).mkdir(mode=0o700)
            manifest["directories"][name] = _identity(plan.root / name)
            _save_owned(owned, manifest)
        progress.finish()
        progress.enter("private_inputs")
        phase = "private_input"
        _private_inputs(plan, command)
        progress.finish()

        def create(role: str, db_id: str = "") -> str:
            nonlocal phase
            phase = "containment"
            found = command(
                [
                    "docker",
                    "ps",
                    "--all",
                    "--no-trunc",
                    "--filter",
                    "name=^/" + plan.name(role) + "$",
                    "--format",
                    "{{.ID}}",
                ]
            )
            if found:
                raise LabFailure("ownership")
            cid = command(create_command(plan, role, db_id), timeout=20)
            if re.fullmatch(r"[0-9a-f]{64}", cid) is None:
                raise LabFailure("identity")
            inspect(role, cid, db_id)
            manifest["containers"][role] = cid
            _save_owned(owned, manifest)
            return cid

        progress.enter("db_create")
        db = create("db")
        progress.finish()
        progress.enter("db_start")
        command(["docker", "start", db], timeout=10)
        progress.finish()
        progress.enter("db_ready")
        until = min(deadline, time.monotonic() + 60)
        while True:
            check_deadline()
            health = command(
                [
                    "docker",
                    "exec",
                    db,
                    "sh",
                    "-c",
                    "pg_isready -h 127.0.0.1 -p 5432 -U m2_lab -d postgres "
                    ">/dev/null 2>&1; printf '%s' \"$?\"",
                ],
                timeout=5,
            )
            if health == "0":
                break
            if health not in ("1", "2") or time.monotonic() >= until:
                raise LabFailure("runtime")
            check_deadline()
            time.sleep(min(0.5, max(0, until - time.monotonic())))
        progress.finish()
        progress.enter("api_create")
        api = create("api", db)
        progress.finish()
        progress.enter("api_start")
        phase = "runtime"
        command(["docker", "start", api], timeout=10)
        progress.finish()
        progress.enter("api_ready")
        until = min(deadline, time.monotonic() + 120)
        while True:
            check_deadline()
            try:
                checks = _status(plan, "ready")
                break
            except LabFailure as error:
                if error.reason != "evidence" or not isinstance(
                    error.__cause__, json.JSONDecodeError
                ):
                    raise
                if time.monotonic() >= until:
                    raise LabFailure("runtime") from None
                check_deadline()
                time.sleep(min(0.2, max(0, until - time.monotonic())))
            except FileNotFoundError:
                if time.monotonic() >= until:
                    raise LabFailure("runtime") from None
                check_deadline()
                time.sleep(min(0.2, max(0, until - time.monotonic())))
        progress.finish()
        progress.enter("namespace")
        namespaces = []
        for role, cid in (("db", db), ("api", api)):
            row = inspect(role, cid, db if role == "api" else "")
            if row.get("State", {}).get("Running") is not True:
                raise LabFailure("runtime")
            ns = command(["docker", "exec", cid, "readlink", "/proc/self/ns/net"])
            if re.fullmatch(r"net:\[[0-9]+\]", ns) is None:
                raise LabFailure("containment")
            namespaces.append(ns)
        if namespaces[0] != namespaces[1]:
            raise LabFailure("containment")
        progress.finish()
        progress.enter("connector_create")
        connector = create("connector")
        progress.finish()
        progress.enter("connector_run")
        phase = "runtime"
        raw = command(["docker", "start", "--attach", connector], timeout=120)
        progress.finish()
        progress.enter("connector_result")
        result = parse_json(raw)
        if (
            not isinstance(result, dict)
            or set(result)
            != {
                "status",
                "item_count",
                "projection_disposed",
                "tls_negative",
                "isolation_verified",
                "network_namespace",
            }
            or result["status"] != "ok"
            or type(result["item_count"]) is not int
            or result["item_count"] != 3
            or result["projection_disposed"] is not True
            or result["isolation_verified"] is not True
            or type(result["network_namespace"]) is not str
            or re.fullmatch(r"net:\[[0-9]+\]", result["network_namespace"]) is None
            or result["network_namespace"] in namespaces
            or result["tls_negative"] != {"wrong_hostname": True, "wrong_ca": True}
            or any(v is not True for v in result["tls_negative"].values())
        ):
            raise LabFailure("runtime")
        row = inspect("connector", connector)
        # docker start --attach's status alone does not prove the container exit code.
        if (
            row.get("State", {}).get("Running") is not False
            or type(row.get("State", {}).get("ExitCode")) is not int
            or row["State"]["ExitCode"] != 0
        ):
            raise LabFailure("runtime")
        progress.finish()
        progress.enter("api_stop")
        command(["docker", "stop", "--time", "5", api], timeout=10)
        row = inspect("api", api, db)
        if row.get("State", {}).get("Running") is not False or row["State"].get("ExitCode") != 0:
            raise LabFailure("runtime")
        progress.finish()
        progress.enter("database_disposal")
        if _status(plan, "stopped") != checks:
            raise LabFailure("runtime")
        check_deadline()
        progress.finish()
        return {
            **checks,
            "network_isolation": True,
            "tls_hostname": True,
            "tls_trust": True,
            "projection_disposed": True,
            "containment": True,
            "database_cleanup": True,
        }
    except LabFailure:
        raise
    except Exception:
        # Closed phase only: never expose subprocess text or private paths.
        raise LabFailure(phase) from None
    finally:
        os.umask(previous_umask)
