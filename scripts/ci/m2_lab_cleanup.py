"""Independent exact-identity cleanup. Never run by import or against generic labels.

Tests inject fake command execution and owned public-text temporary roots only.
An absent root is reported as verified absence, not proof of secure erasure.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from scripts.ci.m2_lab_hosted import (
    ROLES,
    LabFailure,
    RunPlan,
    owned_identity,
    reconcile_container,
)
from scripts.ci.quote_capacity_micro import run as bounded_command

INVENTORY: dict[str, dict[str, set[int]]] = {
    "api": {"catalogue.sock": {0o600}},
    "api-private": {"run.json": {0o400, 0o600}, "pg-password": {0o400, 0o600}},
    "tls": {"api.crt": {0o400, 0o600}, "api.key": {0o400, 0o600}},
    "public": {"ca.crt": {0o444, 0o600}},
    "credential": {
        "credential": {0o400, 0o600},
        "scope.json": {0o400, 0o600},
        "api-status.json": {0o600},
    },
    "ca": {
        "ca.key": {0o600},
        "ca.crt": {0o600, 0o644},
        "api.csr": {0o600, 0o644},
        "san.cnf": {0o600},
    },
}


def _identity(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"dev", "ino", "uid", "mode"}:
        raise LabFailure("ownership")
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise LabFailure("ownership")
    if value["ino"] <= 0 or value["uid"] != os.getuid() or value["mode"] != 0o700:
        raise LabFailure("ownership")
    return value


def _matches(info: os.stat_result, expected: dict[str, int]) -> bool:
    return (
        stat.S_ISDIR(info.st_mode)
        and info.st_dev == expected["dev"]
        and info.st_ino == expected["ino"]
        and info.st_uid == expected["uid"]
        and stat.S_IMODE(info.st_mode) == expected["mode"]
    )


def _manifest(plan: RunPlan, owned: dict[str, Any]) -> None:
    if (
        set(owned) != {"schema", "plan", "root_identity", "directories", "containers"}
        or type(owned["schema"]) is not int
        or owned["schema"] != 1
        or owned["plan"] != asdict(plan)
    ):
        raise LabFailure("ownership")
    if owned["root_identity"] is not None:
        _identity(owned["root_identity"])
    directories, containers = owned["directories"], owned["containers"]
    if not isinstance(directories, dict) or set(directories) - set(INVENTORY):
        raise LabFailure("ownership")
    for identity in directories.values():
        _identity(identity)
    if not isinstance(containers, dict) or set(containers) != set(ROLES):
        raise LabFailure("ownership")
    for cid in containers.values():
        if cid is not None and (type(cid) is not str or re.fullmatch(r"[0-9a-f]{64}", cid) is None):
            raise LabFailure("ownership")


def _cid_exists(cid: str, execute: Callable[..., str]) -> bool:
    found = execute(
        ["docker", "ps", "--all", "--no-trunc", "--filter", "id=" + cid, "--format", "{{.ID}}"],
        timeout=5,
    ).splitlines()
    if found not in ([], [cid]):
        raise LabFailure("identity")
    return found == [cid]


def _remove_containers(plan: RunPlan, owned: dict[str, Any], execute: Callable[..., str]) -> None:
    identified = {}
    # Validate all candidates before removing any. A name alone or label alone
    # cannot authorize removal; known CIDs cannot be silently replaced/renamed.
    for role in ROLES:
        known = owned["containers"][role]
        found = reconcile_container(plan, role, execute)
        if known is not None:
            if _cid_exists(known, execute):
                row = json.loads(
                    execute(["docker", "inspect", "--format", "{{json .}}", known], timeout=5)
                )
                if not isinstance(row, dict) or owned_identity(plan, role, row) != known:
                    raise LabFailure("identity")
                if found != known:
                    raise LabFailure("identity")
            elif found is not None:
                raise LabFailure("identity")
        identified[role] = found
    for role in reversed(ROLES):
        cid = identified[role]
        if cid is not None:
            execute(["docker", "rm", "--force", cid], timeout=10)
            if _cid_exists(cid, execute):
                raise LabFailure("cleanup")
        if reconcile_container(plan, role, execute) is not None:
            raise LabFailure("cleanup")


def _remove_root(plan: RunPlan, owned: dict[str, Any]) -> None:
    root = plan.root
    if not os.path.lexists(root):
        return
    expected = owned["root_identity"]
    if expected is None or any(parent.is_symlink() for parent in root.parents):
        raise LabFailure("ownership")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directories: dict[str, int] = {}
    files: list[tuple[int, str, os.stat_result]] = []
    try:
        if not _matches(os.fstat(root_fd), expected):
            raise LabFailure("ownership")
        root_names = set(os.listdir(root_fd))
        if root_names - {*INVENTORY, "pg-password"}:
            raise LabFailure("ownership")
        for directory in root_names - {"pg-password"}:
            identity = owned["directories"].get(directory)
            if identity is None:
                raise LabFailure("ownership")
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
            directories[directory] = fd
            info = os.fstat(fd)
            if not _matches(info, identity) or info.st_dev != expected["dev"]:
                raise LabFailure("ownership")
            names = set(os.listdir(fd))
            if names - set(INVENTORY[directory]):
                raise LabFailure("ownership")
            for name in names:
                entry = os.stat(name, dir_fd=fd, follow_symlinks=False)
                is_socket = directory == "api" and name == "catalogue.sock"
                if (
                    not (stat.S_ISSOCK(entry.st_mode) if is_socket else stat.S_ISREG(entry.st_mode))
                    or entry.st_uid != expected["uid"]
                    or entry.st_nlink != 1
                    or entry.st_dev != expected["dev"]
                    or stat.S_IMODE(entry.st_mode) not in INVENTORY[directory][name]
                ):
                    raise LabFailure("ownership")
                files.append((fd, name, entry))
        if "pg-password" in root_names:
            entry = os.stat("pg-password", dir_fd=root_fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(entry.st_mode)
                or entry.st_uid != expected["uid"]
                or entry.st_nlink != 1
                or entry.st_dev != expected["dev"]
                or stat.S_IMODE(entry.st_mode) not in {0o444, 0o600}
            ):
                raise LabFailure("ownership")
            files.append((root_fd, "pg-password", entry))
        # Full fixed-depth inventory has passed before the first file deletion.
        for fd, name, before in files:
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if current != before:
                raise LabFailure("ownership")
            os.unlink(name, dir_fd=fd)
        for name, fd in directories.items():
            if os.listdir(fd) or not _matches(
                os.stat(name, dir_fd=root_fd, follow_symlinks=False), owned["directories"][name]
            ):
                raise LabFailure("ownership")
            os.rmdir(name, dir_fd=root_fd)
        if os.listdir(root_fd) or not _matches(root.lstat(), expected):
            raise LabFailure("ownership")
        root.rmdir()
        if os.path.lexists(root):
            raise LabFailure("cleanup")
    finally:
        for fd in directories.values():
            os.close(fd)
        os.close(root_fd)


def cleanup(
    plan: RunPlan, owned: dict[str, Any], *, execute: Callable[..., str] = bounded_command
) -> dict[str, bool]:
    """Future explicitly authorized cleanup; no broad rm/prune, no unknown paths."""
    previous = time.monotonic()
    deadline = previous + 90

    def remaining() -> float:
        nonlocal previous
        now = time.monotonic()
        if (
            not math.isfinite(deadline)
            or not math.isfinite(now)
            or now < previous
            or now >= deadline
        ):
            raise LabFailure("deadline")
        previous = now
        return deadline - now

    def command(args: list[str], *, timeout: float) -> str:
        result = execute(args, timeout=min(timeout, remaining()))
        remaining()
        return result

    try:
        remaining()
        _manifest(plan, owned)
        _remove_containers(plan, owned, command)
        remaining()
        _remove_root(plan, owned)
        remaining()
        return {"containers_absent": True, "root_removed": True}
    except LabFailure:
        raise
    except Exception:
        raise LabFailure("cleanup") from None
