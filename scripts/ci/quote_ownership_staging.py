"""Bounded no-follow evidence staging, not measurement qualification.

Only a fresh trusted RUNNER_TEMP directory is uploaded; no source glob is safe.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from scripts.ci.quote_ownership_actions_adapter import _directory_fd, _same_root, _write_at

JSON_FILES = (
    "guard-prebuild.json",
    "guard-setup.json",
    "receipt.json",
    "cleanup.json",
    "fixture-preparation.json",
    "preparation/preparation.json",
)
FILE_LIMIT = 16384
TOTAL_LIMIT = len(JSON_FILES) * FILE_LIMIT


class StagingRefusal(ValueError):
    def __init__(self) -> None:
        super().__init__("ownership_staging_refused")


def _require(value: bool) -> None:
    if not value:
        raise StagingRefusal()


def _regular(descriptor: int, name: str) -> os.stat_result:
    value = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
    _require(
        stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and 0 <= value.st_size <= FILE_LIMIT
    )
    return value


def _read(descriptor: int, name: str) -> bytes:
    before = _regular(descriptor, name)
    child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
    try:
        opened = os.fstat(child)
        _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino))
        raw = bytearray()
        while len(raw) <= FILE_LIMIT:
            part = os.read(child, min(4096, FILE_LIMIT + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        after = os.fstat(child)
        _require(len(raw) <= FILE_LIMIT and len(raw) == before.st_size)
        _require(
            (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        )
        return bytes(raw)
    finally:
        os.close(child)


def _entries(descriptor: int, limit: int) -> set[str]:
    names: set[str] = set()
    with os.scandir(descriptor) as entries:
        for index, entry in enumerate(entries):
            _require(index < limit)
            names.add(entry.name)
    return names


def _collect(source: Path, validators: Mapping[str, Callable[[bytes], None]]) -> dict[str, bytes]:
    _require(set(validators) == set(JSON_FILES))
    descriptor = _directory_fd(source, create=False)
    collected: dict[str, bytes] = {}
    try:
        names = _entries(descriptor, 6)
        allowed = {name for name in JSON_FILES if "/" not in name} | {"preparation"}
        _require(names <= allowed)
        for name in sorted(names - {"preparation"}):
            raw = _read(descriptor, name)
            validators[name](raw)
            collected[name] = raw
            _same_root(source, descriptor)
        if "preparation" in names:
            child = os.open(
                "preparation", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            try:
                children = _entries(child, 2)
                _require(children <= {"preparation.json", "preparation.txt"})
                if "preparation.txt" in children:
                    _regular(child, "preparation.txt")  # Never read/copy raw build text.
                if "preparation.json" in children:
                    raw = _read(child, "preparation.json")
                    validators["preparation/preparation.json"](raw)
                    collected["preparation.json"] = raw
                opened = os.fstat(child)
                current = os.stat("preparation", dir_fd=descriptor, follow_symlinks=False)
                _require(
                    stat.S_ISDIR(current.st_mode)
                    and (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino)
                )
            finally:
                os.close(child)
        _same_root(source, descriptor)
        _require(sum(map(len, collected.values())) <= TOTAL_LIMIT)
        return collected
    finally:
        os.close(descriptor)


def stage_evidence(
    source: Path,
    runner_temp: Path,
    validators: Mapping[str, Callable[[bytes], None]],
    *,
    bundle_validator: Callable[[Mapping[str, bytes]], None] = lambda data: None,
) -> tuple[Path, bool]:
    """Unsafe source yields only a fixed refusal; unsafe destination yields none."""
    try:
        _require(not any(c in str(runner_temp) for c in "\r\n\x00"))
        parent = _directory_fd(runner_temp, create=False)
    except Exception:
        raise StagingRefusal() from None
    stage = None
    try:
        name = "quote-ownership-upload-" + secrets.token_hex(16)
        os.mkdir(name, mode=0o700, dir_fd=parent)
        stage = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        output = runner_temp / name
        try:
            data = _collect(source, validators)
            bundle_validator(data)
            okay = True
        except Exception:
            data, okay = {}, False
        _same_root(runner_temp, parent)
        _same_root(output, stage)
        for filename, raw in data.items():
            descriptor = os.open(
                filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400, dir_fd=stage
            )
            with os.fdopen(descriptor, "wb") as file:
                file.write(raw)
        _write_at(
            stage,
            "staging.json",
            {
                "schema": 1,
                "kind": "ocwp.quote_ownership.staging",
                "status": "copied" if okay else "unsafe_source",
                "qualification": "not_a_receipt",
                "files": sorted(data),
                "copied_bytes": sum(map(len, data.values())),
            },
        )
        _same_root(runner_temp, parent)
        _same_root(output, stage)
        os.fchmod(stage, 0o500)
        return output, okay
    except Exception:
        raise StagingRefusal() from None
    finally:
        if stage is not None:
            os.close(stage)
        os.close(parent)


def _json(raw: bytes) -> dict[str, Any]:
    from scripts.ci.quote_ownership_actions_guard import _object, _pairs

    def invalid(_: str) -> None:
        raise StagingRefusal()

    return _object(
        json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=invalid)
    )


def validate_bundle(data: Mapping[str, bytes]) -> None:
    """An independently finalized receipt digest must identify copied bytes."""
    import hashlib

    if "receipt.json" in data:
        receipt = _json(data["receipt.json"])
        if receipt.get("status") == "passed":
            _require("cleanup.json" in data)
            cleanup = _json(data["cleanup.json"])
            _require(cleanup.get("outcome") == "verified_absent")
            _require(cleanup.get("identity") == receipt["identity"])
            _require(cleanup.get("receipt_sha256") is not None)
    if "cleanup.json" in data:
        digest = _json(data["cleanup.json"])["receipt_sha256"]
        if digest is not None:
            _require("receipt.json" in data)
            _require(hashlib.sha256(data["receipt.json"]).hexdigest() == digest)


def validators_for_environment(env: Mapping[str, str]) -> dict[str, Callable[[bytes], None]]:
    from scripts.ci import quote_ownership_actions_guard as guard
    from scripts.ci import quote_ownership_evidence as evidence
    from scripts.ci.quote_ownership_actions_adapter import _context

    def validate(name: str, raw: bytes) -> None:
        context, pins = _context(env)
        value = _json(raw)
        if name.startswith("guard-"):
            phase = "prebuild" if name == "guard-prebuild.json" else "setup"
            _require(type(value.get("schema")) is int and value["schema"] == 1)
            _require(value.get("phase") == phase)
            status = value.get("status")
            base = {"schema", "phase", "status"}
            if status == "unknown_spent":
                _require(
                    set(value) == base
                    or (set(value) == base | {"reason"} and value["reason"] == "guard_not_started")
                )
            elif status == "refused_spent":
                _require(
                    set(value) == base | {"reason"} and value["reason"] == "ownership_guard_refused"
                )
            else:
                _require(status == "passed" and set(value) == base | {"binding"})
                expected = dict(
                    schema=1,
                    authorization_id=guard.PROPOSAL_SHA256,
                    repository=guard.REPOSITORY,
                    workflow_path=guard.WORKFLOW_PATH,
                    ref=guard.REF,
                    commit=pins["source_sha"],
                    tree=pins["tree_sha"],
                    workflow_id=str(pins["workflow_id"]),
                    run_id=str(context["run_id"]),
                    run_number=1,
                    run_attempt=1,
                )
                _require(value["binding"] == expected)
                for key in ("schema", "run_number", "run_attempt"):
                    _require(type(value["binding"][key]) is int)
        elif name == "preparation/preparation.json":
            _validate_preparation(value, env)
        elif name == "cleanup.json" and value.get("identity") is None:
            evidence.validate_cleanup(value, None)
            _require(
                value["expected_commit"] == env["GITHUB_SHA"]
                and value["run_id"] == env["GITHUB_RUN_ID"]
                and value["run_attempt"] == 1
            )
        else:
            identity = evidence.identity_from_environment(dict(env))
            if name == "receipt.json":
                evidence.validate_receipt(value, identity)
            elif name == "cleanup.json":
                evidence.validate_cleanup(value, identity)
            else:
                evidence.validate_fixture_preparation(value, identity)
                _require(value["pg_base_image"] == env["OCWP_OWNERSHIP_PG_BASE_IMAGE_ID"])
                _require(value["pg_base_reference"] == env["OCWP_OWNERSHIP_PG_BASE_REFERENCE"])
                import hashlib

                root = Path(__file__).resolve().parents[2]
                for key, path in {
                    "dockerfile": "infra/docker/quote-ownership-postgres.fixture.Dockerfile",
                    "initializer": "infra/compose/postgres-init/10-application-role.sql",
                    "public_fixture": (
                        "tests/fixtures/quote-ownership/public-synthetic-password.txt"
                    ),
                }.items():
                    _require(
                        value["files"][key]
                        == hashlib.sha256((root / path).read_bytes()).hexdigest()
                    )

    def checker(name: str) -> Callable[[bytes], None]:
        def check(raw: bytes) -> None:
            validate(name, raw)

        return check

    return {name: checker(name) for name in JSON_FILES}


def _validate_preparation(value: dict[str, Any], env: Mapping[str, str]) -> None:
    fixed = dict(
        schema=2,
        kind="ocwp.full_python.preparation_client",
        status="unqualified",
        expected_commit=env["GITHUB_SHA"],
        run_id=env["GITHUB_RUN_ID"],
        run_attempt="1",
        limit_bytes=FILE_LIMIT,
        build_resource_cleanup="not_assessed",
        qualification="not_a_receipt",
    )
    variable = {
        "stage",
        "failure",
        "returncode",
        "client_reaped",
        "available",
        "observed_bytes",
        "retained_bytes",
        "spool_limit_bytes",
        "capture",
        "dropped_prefix_bytes",
        "retention_truncated",
        "at_spool_limit",
        "at_limit_or_truncated",
    }
    _require(set(value) == set(fixed) | variable)
    for key, expected in fixed.items():
        _require(type(value[key]) is type(expected) and value[key] == expected)
    _require(
        value["stage"]
        in {"source_tree", "image_build", "postgres_pull", "worker_image", "postgres_image"}
    )
    _require(
        value["failure"]
        in {
            None,
            "unfinished",
            "preparation_deadline",
            "interrupted",
            "tool_unavailable",
            "command_timeout",
            "command_failed",
            "output_limit",
            "client_reap_unverified",
            "preparation_failed",
        }
    )
    _require(
        value["returncode"] is None
        or (type(value["returncode"]) is int and -255 <= value["returncode"] <= 255)
    )
    for key in ("client_reaped", "available"):
        _require(type(value[key]) is bool)
    _require(
        type(value["spool_limit_bytes"]) is int
        and value["spool_limit_bytes"] in {FILE_LIMIT, 1048576}
    )
    _require(type(value["retained_bytes"]) is int and 0 <= value["retained_bytes"] <= FILE_LIMIT)
    size = value["observed_bytes"]
    _require(size is None or (type(size) is int and 0 <= size <= value["spool_limit_bytes"]))
    tail = value["spool_limit_bytes"] == 1048576
    _require(value["capture"] == ("tail" if tail else "prefix"))
    _require(value["available"] is (size is not None))
    expected_flags = {
        "dropped_prefix_bytes": None
        if size is None
        else max(0, size - value["retained_bytes"])
        if tail
        else 0,
        "retention_truncated": None if size is None else size > value["retained_bytes"],
        "at_spool_limit": None if size is None else size >= value["spool_limit_bytes"],
        "at_limit_or_truncated": None if size is None else size >= FILE_LIMIT,
    }
    for key, expected in expected_flags.items():
        _require(type(value[key]) is type(expected) and value[key] == expected)


def main() -> int:
    import sys

    try:
        root = Path(__file__).resolve().parents[2] / "artifacts/quote-ownership"
        output, okay = stage_evidence(
            root,
            Path(os.environ["RUNNER_TEMP"]),
            validators_for_environment(os.environ),
            bundle_validator=validate_bundle,
        )
        print(output)
        return 0 if okay else 1
    except Exception:
        print("ownership_staging_refused", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
