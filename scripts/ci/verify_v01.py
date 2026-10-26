#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class Check:
    name: str
    status: str
    detail: str


# Two fixed serial shards, not a selector or command API. Ordinary imports do not
# register the plugin and the standalone verifier retains its local behavior.
FULL_RECORD_LIMIT = 4 * 1024 * 1024
FULL_MAX_NODES = 8192
# At most 448 bytes for each ordinary collection/outcome pair, plus 64 KiB for
# the 69 unique semantic IDs, three identities, policies and fixed envelopes.
# Successful phases use only fixed enums and <=9-digit microsecond integers.
FULL_MAX_SERIALIZED_BYTES = FULL_MAX_NODES * 448 + 65536
_FULL_PYTHON_ARGS = (
    "-p",
    "no:cacheprovider",
    "-p",
    "scripts.ci.verify_v01",
    "-o",
    "addopts=",
    "-o",
    "tmp_path_retention_policy=failed",
    "--basetemp=/tmp/ocwp-tests/pytest",
    "--maxfail=1",
    "--capture=fd",
    "--show-capture=no",
    "--no-showlocals",
    "--tb=short",
    "-q",
    "tests",
    "services/platform/tests",
)
FULL_SHARDS = ("a", "b")
FULL_SHARD_SELECTORS = {
    "a": (
        "tests/",
        "services/platform/tests/bicycles/",
        "services/platform/tests/blobs/",
        "services/platform/tests/branding/",
        "services/platform/tests/cli/",
        "services/platform/tests/customers/",
        "services/platform/tests/db/",
        "services/platform/tests/events/",
        "services/platform/tests/identity/",
        "services/platform/tests/inventory/",
    ),
    "b": (
        "services/platform/tests/jobs/",
        "services/platform/tests/ops/",
        "services/platform/tests/quotes/",
        "services/platform/tests/service_orders/",
        "services/platform/tests/settings/",
        "services/platform/tests/sync/",
        "services/platform/tests/test_baseline_wire.py",
        "services/platform/tests/test_health.py",
        "services/platform/tests/test_model_registration.py",
        "services/platform/tests/test_openapi.py",
    ),
}
FULL_POSTGRES_SETTINGS = {
    "max_wal_size": "128MB",
    "min_wal_size": "80MB",
    "checkpoint_timeout": "5min",
    "checkpoint_completion_target": "0.9",
    "fsync": "on",
    "full_page_writes": "on",
    "synchronous_commit": "on",
    "wal_level": "replica",
}
FULL_POLICY = {
    "version": 2,
    "shards": {key: list(value) for key, value in FULL_SHARD_SELECTORS.items()},
    "execution": "serial",
    "roots": ["tests", "services/platform/tests"],
    "workload_seconds": 900,
    "supervisor_seconds": 1020,
    "stdout_limit": 1048576,
    "record_limit": FULL_RECORD_LIMIT,
    "maximum_nodes": FULL_MAX_NODES,
    "expected_skips": 58,
    "worker_cpu": 1,
    "worker_memory_mib": 768,
    "worker_pids": 64,
    "postgres_cpu": 1,
    "postgres_memory_mib": 1024,
    "postgres_wal_checkpoint_trigger_mib": 128,
    "postgres_pids": 128,
    "shared_memory_bytes": 67108864,
    "worker_tmpfs_bytes": [67108864, 67108864, 16777216],
    "worker_tmpfs_inodes": [16384, 16384, 32],
    "postgres_tmpfs_bytes": [67108864, 536870912, 16777216],
    "postgres_tmpfs_inodes": [16384, 32768, 128],
}
FULL_PREFLIGHT = {
    "python": "3.13.14",
    "node": "22.16.0",
    "pnpm": "11.17.0",
    "playwright": "1.62.0",
    "pg_dump": "18.4",
    "pg_restore": "18.4",
    "psql": "18.4",
    "git_available": True,
    "database": {
        "server_version_num": 180004,
        "driver": "psycopg",
        "driver_version": "3.3.4",
        "database": "ocwp_quote_full_test",
        "server_encoding": "UTF8",
        "client_encoding": "UTF8",
        "settings": FULL_POSTGRES_SETTINGS,
    },
}
FULL_DATABASE_URL = "postgresql+psycopg://ocwp:ocwp-synthetic@127.0.0.1:5432/ocwp_quote_full_test"
FULL_SOURCE_FILES = {
    "workflow_sha256": ".github/workflows/ci.yml",
    "helper_sha256": "scripts/ci/quote_capacity_micro.py",
    "verifier_sha256": "scripts/ci/verify_v01.py",
    "uv_lock_sha256": "uv.lock",
    "pnpm_lock_sha256": "pnpm-lock.yaml",
}
FULL_FAILURE_CODES = frozenset(
    {
        "independent_cleanup_pending",
        "source_identity",
        "preparation_failed",
        "preflight_failed",
        "containment_failed",
        "collection_failed",
        "result_failed",
        "invalid_evidence",
        "output_limit",
        "wall_budget",
        "resource_pressure",
        "worker_failed",
        "interrupted",
        "cleanup_failed",
        "creation_uncertain",
        "unrun",
        "worker_stop_unverified",
    }
)
FULL_CHECK_NAMES = ("python_tests", "python_psycopg", "postgresql_integration")


class FullPythonEvidenceError(ValueError):
    """A closed diagnostic code; never an exception payload or connection URL."""

    source_status: str | None = None


def _full_require(condition: bool, code: str) -> None:
    if not condition:
        raise FullPythonEvidenceError(code)


def _full_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise FullPythonEvidenceError("invalid_json") from None


def _full_keys(value: object, keys: set[str], code: str) -> dict[str, Any]:
    _full_require(type(value) is dict and set(value) == keys, code)
    return value


def _full_int(value: object, minimum: int, maximum: int, code: str) -> int:
    _full_require(type(value) is int and minimum <= value <= maximum, code)
    return value


def _full_hash(value: object, code: str) -> str:
    _full_require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, code)
    return value


def _full_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _full_require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _full_constant(_value: str) -> None:
    raise FullPythonEvidenceError("nonfinite_json")


def _full_float(value: str) -> float:
    result = float(value)
    _full_require(math.isfinite(result), "nonfinite_json")
    return result


def _full_decode(raw: bytes) -> dict[str, Any]:
    _full_require(0 < len(raw) < FULL_RECORD_LIMIT, "record_size")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_full_pairs,
            parse_constant=_full_constant,
            parse_float=_full_float,
        )
    except (UnicodeError, ValueError, RecursionError):
        raise FullPythonEvidenceError("invalid_json") from None
    _full_require(type(value) is dict, "invalid_json")
    return value


def read_full_python_value(raw: str) -> dict[str, Any]:
    _full_require(type(raw) is str, "record_type")
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError:
        raise FullPythonEvidenceError("invalid_json") from None
    return _full_decode(encoded)


def read_full_python_json(path: Path) -> dict[str, Any]:
    """Read a strictly bounded regular file without following a final symlink."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as source:
            _full_require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), "record_type")
            raw = source.read(FULL_RECORD_LIMIT)
    except OSError:
        raise FullPythonEvidenceError("record_unavailable") from None
    return _full_decode(raw)


def write_full_python_json(path: Path, value: dict[str, Any]) -> None:
    """Publish one bounded atomic record. Parent directories are owned by the caller."""
    _full_require(FULL_MAX_SERIALIZED_BYTES < FULL_RECORD_LIMIT, "record_budget")
    raw = _full_json(value) + b"\n"
    _full_require(len(raw) < FULL_RECORD_LIMIT, "record_size")
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".ocwp-full-", dir=path.parent)
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(raw)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise FullPythonEvidenceError("record_write_failed") from None
    finally:
        if temporary is not None:
            with suppress(OSError):
                os.unlink(temporary)


def _full_source_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    try:
        for key, filename in FULL_SOURCE_FILES.items():
            with (root / filename).open("rb") as source:
                hashes[key] = hashlib.file_digest(source, "sha256").hexdigest()
    except OSError:
        raise FullPythonEvidenceError("source_unavailable") from None
    return hashes


def full_python_args(shard: str) -> tuple[str, ...]:
    """Closed shard enum; both commands collect the complete original roots."""
    _full_require(type(shard) is str and shard in FULL_SHARDS, "shard")
    return (*_FULL_PYTHON_ARGS[:-2], f"--ocwp-full-shard={shard}", *_FULL_PYTHON_ARGS[-2:])


def full_python_shard(source: str) -> str:
    """Partition canonical module paths, never generated parameter/node-ID text."""
    _full_require(
        type(source) is str
        and not source.startswith("/")
        and "\\" not in source
        and all(part not in {"", ".", ".."} for part in source.split("/"))
        and source.endswith(".py"),
        "module_path",
    )
    matches = [
        shard
        for shard, selectors in FULL_SHARD_SELECTORS.items()
        for selector in selectors
        if (source.startswith(selector) if selector.endswith("/") else source == selector)
    ]
    _full_require(len(matches) == 1, "module_assignment")
    return matches[0]


def _full_module_inventory() -> dict[str, tuple[str, str]]:
    """Resolve path digests independently against this exact checkout's test modules.

    The reviewed source-bound producer attests each legacy node-hash/module
    association, as it does semantic case labels. These are not signatures:
    coordinated forged producer records are outside this authenticity boundary.
    Raw parameterized IDs can contain huge/private values and are never exported.
    """
    modules: dict[str, tuple[str, str]] = {}
    try:
        for root in cast(list[str], FULL_POLICY["roots"]):
            for path in (ROOT / root).rglob("*.py"):
                if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
                    continue
                source = path.relative_to(ROOT).as_posix()
                _full_require(
                    path.is_file() and path.resolve().is_relative_to(ROOT.resolve()),
                    "module_path",
                )
                shard = full_python_shard(source)
                digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
                _full_require(digest not in modules, "module_assignment")
                modules[digest] = (source, shard)
    except OSError:
        raise FullPythonEvidenceError("source_unavailable") from None
    _full_require(bool(modules), "module_assignment")
    return modules


def _full_assigned_nodes(collection: dict[str, Any]) -> list[dict[str, Any]]:
    modules = _full_module_inventory()
    shard = collection["identity"]["shard"]
    return [node for node in collection["nodes"] if modules[node["module_sha256"]][1] == shard]


def _full_command_hash(shard: str) -> str:
    command = ["/app/.venv/bin/python", "-m", "pytest", *full_python_args(shard)]
    return hashlib.sha256(_full_json(command)).hexdigest()


def _full_identity(identity: object) -> dict[str, Any]:
    value = _full_keys(
        identity,
        {
            "shard",
            "commit",
            "tree",
            "image_id",
            "pg_image_id",
            "nonce",
            "run_id",
            "run_attempt",
            "job",
            "clean_source",
            "command_sha256",
            *FULL_SOURCE_FILES,
        },
        "identity_fields",
    )
    _full_require(type(value["shard"]) is str and value["shard"] in FULL_SHARDS, "shard")
    for key in ("commit", "tree"):
        _full_require(
            type(value[key]) is str and re.fullmatch(r"[0-9a-f]{40}", value[key]) is not None,
            "identity_source",
        )
    for key in ("image_id", "pg_image_id"):
        _full_require(
            type(value[key]) is str
            and re.fullmatch(r"sha256:[0-9a-f]{64}", value[key]) is not None,
            "identity_image",
        )
    _full_require(
        type(value["nonce"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["nonce"]) is not None,
        "identity_nonce",
    )
    for key in ("run_id", "run_attempt"):
        _full_require(
            type(value[key]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value[key]) is not None,
            "identity_run",
        )
    _full_require(value["job"] == "python-tests", "identity_job")
    _full_require(value["clean_source"] is True, "identity_dirty")
    for key in FULL_SOURCE_FILES:
        _full_hash(value[key], "identity_hash")
    _full_require(value["command_sha256"] == _full_command_hash(value["shard"]), "identity_command")
    return value


def full_python_identity(
    *,
    shard: str,
    commit: str,
    tree: str,
    image_id: str,
    pg_image_id: str,
    nonce: str,
    run_id: str,
    run_attempt: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Bind caller-verified clean checkout and job context to current source bytes."""
    return _full_identity(
        {
            "shard": shard,
            "commit": commit,
            "tree": tree,
            "image_id": image_id,
            "pg_image_id": pg_image_id,
            "nonce": nonce,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "job": "python-tests",
            "clean_source": True,
            "command_sha256": _full_command_hash(shard),
            **_full_source_hashes(root),
        }
    )


def full_python_peer_identity(identity: dict[str, Any], shard: str, nonce: str) -> dict[str, Any]:
    """Derive a peer's exact expected context from an independently verified identity."""
    _full_identity(identity)
    return _full_identity(
        {**identity, "shard": shard, "nonce": nonce, "command_sha256": _full_command_hash(shard)}
    )


def full_python_expected_identity(env: dict[str, str], *, shard: str) -> dict[str, Any]:
    """Build expectations independently; never use an artifact to choose them."""

    def git(*args: str) -> str:
        def limit_output() -> None:
            import resource

            resource.setrlimit(resource.RLIMIT_FSIZE, (16384, 16384))

        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    ["git", "--no-optional-locks", *args],
                    cwd=ROOT,
                    stdout=output,
                    stderr=output,
                    timeout=5,
                    preexec_fn=limit_output,
                )
                _full_require(result.returncode == 0, "source_unavailable")
                _full_require(os.fstat(output.fileno()).st_size < 16384, "source_output_limit")
                output.seek(0)
                return output.read(16384).decode("utf-8", errors="strict")
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            raise FullPythonEvidenceError("source_unavailable") from None

    status = git("status", "--porcelain", "--untracked-files=normal")
    if status:
        raw = status.encode("utf-8")
        retained = raw[:4096]
        error = FullPythonEvidenceError("identity_dirty")
        error.source_status = json.dumps(
            {
                "kind": "git_porcelain_paths_only",
                "observed_bytes": len(raw),
                "retained_bytes": len(retained),
                "limit_bytes": 4096,
                "truncated": len(raw) > len(retained),
                "encoding": "utf-8-with-replacement",
                "porcelain": retained.decode("utf-8", errors="replace"),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        raise error
    return full_python_identity(
        shard=shard,
        commit=git("rev-parse", "HEAD").strip(),
        tree=git("rev-parse", "HEAD^{tree}").strip(),
        image_id=env.get("OCWP_FULL_PYTHON_IMAGE_ID", ""),
        pg_image_id=env.get("OCWP_FULL_PYTHON_PG_IMAGE_ID", ""),
        nonce=env.get(f"OCWP_FULL_PYTHON_NONCE_{shard.upper()}", ""),
        run_id=env.get("GITHUB_RUN_ID", ""),
        run_attempt=env.get("GITHUB_RUN_ATTEMPT", ""),
    )


@dataclass(frozen=True, slots=True)
class FullPythonCase:
    case: str
    source: str
    function: str
    params: dict[str, object]
    reason: str | None = None
    phase: int | None = None


def _full_cases() -> tuple[FullPythonCase, ...]:
    """Exact existing source matrices, not a count-based skip allowance."""
    cases: list[FullPythonCase] = []
    identity = "services/platform/tests/identity/"
    quotes = "services/platform/tests/quotes/"
    sqlite = {"identity_migration_database": "sqlite"}
    postgres = {"identity_migration_database": "postgres"}

    def add(case, source, function, params, reason=None, phase=None):
        cases.append(FullPythonCase(case, source, function, params, reason, phase))

    scanner_reason = "Actual scanner canaries are mandatory in the hosted Security workflow"
    add(
        "skip.gitleaks.pinned",
        "tests/ci/test_gitleaks_policy.py",
        "test_actual_pinned_scanner_rejects_near_misses_and_other_paths",
        {},
        scanner_reason,
        1,
    )
    for mutation in ("remove_exceptions", "condition_or", "broaden_path", "broaden_value"):
        add(
            f"skip.gitleaks.{mutation}",
            "tests/ci/test_gitleaks_policy.py",
            "test_actual_scanner_canaries_reject_broadened_or_missing_exceptions",
            {"mutation": mutation},
            scanner_reason,
            1,
        )
    add(
        "skip.baseline.pg_lock",
        identity + "test_baseline_migration_lifecycle.py",
        "test_postgres_downgrade_lock_observes_concurrent_insert_before_emptiness_check",
        sqlite,
        "Access-exclusive migration serialization requires PostgreSQL",
        1,
    )
    for case, function, reason in (
        (
            "recovery",
            "test_concurrent_recovery_same_precondition_rotates_once_and_other_org_is_independent",
            "Row-lock ordering proof requires PostgreSQL",
        ),
        (
            "activation",
            "test_activation_waits_for_transaction_and_refuses_no_committed_history_on_rollback",
            "Row-lock ordering proof requires PostgreSQL",
        ),
        (
            "bootstrap",
            "test_supported_bootstraps_serialize_empty_installation_predicate",
            "Advisory-lock bootstrap ordering proof requires PostgreSQL",
        ),
    ):
        add(
            f"skip.cutover.{case}",
            identity + "test_cutover_operator_concurrency.py",
            function,
            sqlite,
            reason,
            1,
        )
    add(
        "skip.identity.truncate",
        identity + "test_identity_migration.py",
        "test_postgres_audit_history_rejects_truncate",
        sqlite,
        "TRUNCATE is PostgreSQL-specific",
        1,
    )
    add(
        "skip.identity.replace",
        identity + "test_identity_migration.py",
        "test_sqlite_replace_cannot_overwrite_an_existing_audit_event",
        postgres,
        "INSERT OR REPLACE is SQLite-specific",
        1,
    )
    for projection in ("page", "detail"):
        for label, table, mutation in (
            (
                "revision",
                "quote_revisions",
                "UPDATE quote_revisions SET total_minor = 1 WHERE version = 2",
            ),
            (
                "operation",
                "quote_operations",
                "UPDATE quote_operations SET proof = '{}' WHERE ordinal = 2",
            ),
            ("outbox", None, "UPDATE outbox_events SET event_type = 'invalid'"),
        ):
            add(
                f"skip.read_corruption.{projection}.{label}",
                quotes + "test_quote_reads.py",
                "test_repository_validates_corruption_outside_requested_page_or_detail",
                {**postgres, "projection": projection, "table": table, "mutation": mutation},
                "SQLite-only corruption injection; not PostgreSQL restore evidence",
                1,
            )
    for table in (
        "quote_lineages",
        "quote_revisions",
        "quote_lines",
        "quote_line_targets",
        "quote_decisions",
        "quote_operations",
    ):
        add(
            f"skip.schema.replace.{table}",
            quotes + "test_quote_schema.py",
            "test_sqlite_replace_cannot_erase_financial_evidence",
            {**postgres, "table": table},
            "INSERT OR REPLACE is SQLite-specific",
            1,
        )
    add(
        "skip.schema.truncate",
        quotes + "test_quote_schema.py",
        "test_postgres_truncate_guards",
        sqlite,
        "TRUNCATE guard requires PostgreSQL",
        1,
    )
    add(
        "skip.schema.alternate",
        quotes + "test_quote_schema.py",
        "test_sqlite_replace_alternate_keys_cannot_discard_other_rows",
        postgres,
        "INSERT OR REPLACE is SQLite-specific",
        1,
    )
    for case, filename, function in (
        (
            "three_operations",
            "test_quote_capacity_micro_postgres.py",
            "test_three_operations_fresh_load_and_exact_retry",
        ),
        (
            "fixed_revision",
            "test_quote_record_feasibility_postgres.py",
            "test_one_fixed_revision_and_initial_decision",
        ),
    ):
        add(
            f"skip.micro.{case}",
            quotes + filename,
            function,
            {},
            "host containment preflight required",
            0,
        )
    metadata = quotes + "test_quote_effect_metadata.py"
    for table, discriminator in (
        ("sync_changes", "entity_type"),
        ("outbox_events", "aggregate_type"),
    ):
        for fault in (
            "mutable",
            "wrong_type",
            "wrong_expression",
            "wrong_discriminator",
            "jsonb",
            "virtual",
            "inherited",
        ):
            add(
                f"skip.metadata.malformed.{table}.{fault}",
                metadata,
                "test_runtime_count_verifier_refuses_malformed_postgres_metadata",
                {**sqlite, "table": table, "discriminator": discriminator, "fault": fault},
                "actual PostgreSQL catalogue negative",
                1,
            )
        for replacement in ("partitioned", "view", "missing"):
            add(
                f"skip.metadata.relation.{table}.{replacement}",
                metadata,
                "test_runtime_count_verifier_refuses_nonordinary_relations",
                {
                    **sqlite,
                    "table": table,
                    "discriminator": discriminator,
                    "replacement": replacement,
                },
                "actual PostgreSQL relation negative",
                1,
            )
        for kind in ("TABLE", "VIEW"):
            for uppercase in (False, True):
                add(
                    f"skip.metadata.temp.{table}.{kind}.{'upper' if uppercase else 'lower'}",
                    metadata,
                    "test_sqlite_temp_shadow_refused",
                    {
                        **postgres,
                        "table": table,
                        "discriminator": discriminator,
                        "kind": kind,
                        "uppercase": uppercase,
                    },
                    "SQLite TEMP resolution surrogate",
                    1,
                )
    for shadow in ("function", "operator"):
        add(
            f"skip.metadata.dependency.{shadow}",
            metadata,
            "test_runtime_count_verifier_refuses_shadowed_generated_dependencies",
            {**sqlite, "shadow": shadow},
            "actual PostgreSQL dependency negative",
            1,
        )
    add(
        "skip.metadata.dependency_rows",
        metadata,
        "test_postgres_generated_dependency_rows_are_exact",
        sqlite,
        "actual PostgreSQL generated dependency rows",
        1,
    )
    for dialect in ("sqlite", "postgres"):
        add(
            f"required.proof_record.{dialect}",
            quotes + "test_quote_repository.py",
            "test_proof_and_result_share_one_bounded_logical_record",
            {"identity_migration_database": dialect},
        )
        add(
            f"required.page25.{dialect}",
            quotes + "test_quote_reads.py",
            "test_default_page_limit_is_25_with_small_one_line_revisions",
            {"identity_migration_database": dialect},
        )
    add(
        "required.restore.database",
        "tests/operations/test_backup_postgres_integration.py",
        "test_real_database_only_restore_drill",
        {},
    )
    for legacy in (False, True):
        add(
            f"required.restore.branding.{'legacy' if legacy else 'current'}",
            "tests/operations/test_branding_recovery_postgres.py",
            "test_real_snapshot_assets_corrupt_latest_earlier_restore_and_authenticated_bytes",
            {"legacy_source": legacy},
        )
    add(
        "required.restore.quote_repository",
        quotes + "test_quote_repository_postgres.py",
        "test_real_dump_restore_preserves_history_proofs_effect_ids_and_fresh_admission_replay",
        {},
    )
    add(
        "required.restore.generated_counts",
        metadata,
        "test_real_logical_restore_recomputes_generated_counts",
        {},
    )
    add(
        "required.restore.service",
        quotes + "test_quote_service_restore_postgres.py",
        "test_real_restore_preserves_version_one_service_effects_and_fresh_replay",
        {},
    )
    add(
        "required.database",
        "services/platform/tests/db/test_postgres_integration.py",
        "test_postgres_18_migrates_to_head_with_expected_v01_tables",
        {},
    )
    return tuple(cases)


FULL_CASES = _full_cases()
FULL_CASE_BY_ID = {case.case: case for case in FULL_CASES}
FULL_SKIP_CASES = frozenset(case.case for case in FULL_CASES if case.reason is not None)
FULL_REQUIRED_CASES = frozenset(case.case for case in FULL_CASES if case.reason is None)


def _full_typed_params(actual: object, expected: dict[str, object]) -> bool:
    return (
        type(actual) is dict
        and set(actual) == set(expected)
        and all(
            type(actual[key]) is type(value) and actual[key] == value
            for key, value in expected.items()
        )
    )


def full_python_case(source: str, function: str, params: dict[str, object]) -> str | None:
    """Classify only closed typed matrices; do not inspect generated node-ID text."""
    candidates = [case for case in FULL_CASES if (case.source, case.function) == (source, function)]
    if not candidates:
        return None
    for case in candidates:
        if _full_typed_params(params, case.params):
            return case.case
    # The other dialect of an intentionally inapplicable case must run normally.
    for case in candidates:
        if case.reason is not None and "identity_migration_database" in case.params:
            opposite = dict(case.params)
            opposite["identity_migration_database"] = (
                "postgres" if opposite["identity_migration_database"] == "sqlite" else "sqlite"
            )
            if _full_typed_params(params, opposite):
                return None
    raise FullPythonEvidenceError("case_matrix_changed")


def _full_envelope(value: dict[str, Any], expected: dict[str, Any], kind: str) -> None:
    _full_identity(expected)
    _full_identity(value["identity"])
    _full_require(_full_json(value["identity"]) == _full_json(expected), "identity_mismatch")
    _full_require(type(value["schema"]) is int and value["schema"] == 2, "schema")
    _full_require(value["kind"] == kind, "kind")
    _full_require(_full_json(value["policy"]) == _full_json(FULL_POLICY), "policy")


def _full_collection(collection: object, expected: dict[str, Any]) -> dict[str, Any]:
    _full_require(FULL_MAX_SERIALIZED_BYTES < FULL_RECORD_LIMIT, "record_budget")
    _full_require(
        len(FULL_CASES) == len(FULL_CASE_BY_ID) == 69
        and all(len(case.case) <= 96 and case.case.isascii() for case in FULL_CASES),
        "case_ledger",
    )
    value = _full_keys(
        collection,
        {
            "schema",
            "kind",
            "identity",
            "policy",
            "collection_errors",
            "deselected",
            "nodes",
            "count",
            "inventory_sha256",
        },
        "collection_fields",
    )
    _full_envelope(value, expected, "ocwp.full_python.collection")
    _full_require(len(_full_json(value)) < FULL_RECORD_LIMIT, "record_size")
    _full_int(value["collection_errors"], 0, FULL_MAX_NODES, "collection_errors")
    _full_int(value["deselected"], 0, FULL_MAX_NODES, "deselected")
    _full_require(
        value["collection_errors"] == 0 and value["deselected"] == 0, "collection_incomplete"
    )
    count = _full_int(value["count"], 1, FULL_MAX_NODES, "collection_count")
    nodes = value["nodes"]
    _full_require(type(nodes) is list and len(nodes) == count, "collection_count")
    keys: set[str] = set()
    cases: set[str] = set()
    modules = _full_module_inventory()
    for node in nodes:
        _full_keys(node, {"node_sha256", "module_sha256", "case"}, "collection_node")
        module = _full_hash(node["module_sha256"], "module_hash")
        _full_require(module in modules, "module_assignment")
        key = _full_hash(node["node_sha256"], "node_hash")
        _full_require(key not in keys, "duplicate_node")
        keys.add(key)
        case = node["case"]
        _full_require(case is None or type(case) is str, "case_identity")
        if case is not None:
            _full_require(case in FULL_CASE_BY_ID and case not in cases, "case_identity")
            _full_require(FULL_CASE_BY_ID[case].source == modules[module][0], "case_module")
            cases.add(case)
    _full_require(cases == set(FULL_CASE_BY_ID), "required_cases_missing")
    _full_require(len(FULL_SKIP_CASES) == 58 and len(FULL_REQUIRED_CASES) == 11, "case_ledger")
    _full_require(
        value["inventory_sha256"] == hashlib.sha256(_full_json(nodes)).hexdigest(),
        "inventory_digest",
    )
    _full_require(
        all(
            any(modules[node["module_sha256"]][1] == shard for node in nodes)
            for shard in FULL_SHARDS
        ),
        "shard_empty",
    )
    return value


def validate_full_python_collection(
    collection: object, expected_identity: dict[str, Any]
) -> dict[str, Any]:
    return _full_collection(collection, expected_identity)


def _full_counts(outcomes: object, nodes: list[dict[str, Any]]) -> dict[str, int]:
    _full_require(type(outcomes) is list and len(outcomes) == len(nodes), "outcome_bijection")
    counts = dict.fromkeys(
        (
            "collected",
            "passed",
            "failed",
            "error",
            "expected_skipped",
            "unexpected_skipped",
            "unrun",
        ),
        0,
    )
    counts["collected"] = len(nodes)
    for outcome, node in zip(outcomes, nodes, strict=True):
        _full_keys(outcome, {"node_sha256", "phases"}, "outcome_fields")
        _full_require(outcome["node_sha256"] == node["node_sha256"], "outcome_bijection")
        phases = outcome["phases"]
        _full_require(type(phases) is list and len(phases) == 3, "phase_slots")
        for index, phase in enumerate(phases):
            if phase is None:
                continue
            _full_require(type(phase) is list and len(phase) == 3, "phase_fields")
            status, duration, skipped = phase
            _full_require(
                type(status) is str and status in {"passed", "failed", "skipped"},
                "phase_status",
            )
            _full_int(duration, 0, 900000000, "phase_duration")
            if status == "skipped":
                _full_require(type(skipped) is str, "skip_identity")
                if skipped != "unexpected":
                    _full_require(
                        skipped in FULL_SKIP_CASES
                        and skipped == node["case"]
                        and FULL_CASE_BY_ID[skipped].phase == index,
                        "skip_identity",
                    )
            else:
                _full_require(skipped is None, "skip_identity")
        setup, call, teardown = phases
        if setup is None:
            _full_require(call is None and teardown is None, "phase_order")
            counts["unrun"] += 1
            continue
        _full_require(setup[0] == "passed" or call is None, "phase_order")
        if teardown is None or (setup[0] == "passed" and call is None):
            counts["unrun"] += 1
            continue
        if setup[0] == "failed" or teardown[0] == "failed":
            counts["error"] += 1
        elif call is not None and call[0] == "failed":
            counts["failed"] += 1
        else:
            skipped_phases = [
                phase for phase in phases if phase is not None and phase[0] == "skipped"
            ]
            if skipped_phases:
                expected = (
                    len(skipped_phases) == 1
                    and skipped_phases[0][2] == node["case"]
                    and node["case"] in FULL_SKIP_CASES
                    and teardown[0] == "passed"
                )
                counts["expected_skipped" if expected else "unexpected_skipped"] += 1
            else:
                _full_require(call is not None, "phase_order")
                counts["passed"] += 1
    return counts


def validate_full_python_result(
    result: object, expected_identity: dict[str, Any], collection: object
) -> dict[str, int]:
    manifest = _full_collection(collection, expected_identity)
    value = _full_keys(
        result,
        {
            "schema",
            "kind",
            "identity",
            "policy",
            "inventory_sha256",
            "session_finished",
            "exit_code",
            "collection_errors",
            "deselected",
            "preflight",
            "outcomes",
            "counts",
        },
        "result_fields",
    )
    _full_envelope(value, expected_identity, "ocwp.full_python.result")
    _full_require(len(_full_json(value)) < FULL_RECORD_LIMIT, "record_size")
    _full_require(value["inventory_sha256"] == manifest["inventory_sha256"], "inventory_digest")
    _full_require(value["session_finished"] is True, "session_unfinished")
    _full_int(value["exit_code"], 0, 255, "exit_code")
    _full_int(value["collection_errors"], 0, FULL_MAX_NODES, "collection_errors")
    _full_int(value["deselected"], 0, FULL_MAX_NODES, "deselected")
    _full_require(value["exit_code"] == 0, "pytest_failed")
    _full_require(
        value["collection_errors"] == 0 and value["deselected"] == 0, "collection_incomplete"
    )
    _full_require(_full_json(value["preflight"]) == _full_json(FULL_PREFLIGHT), "preflight_failed")
    assigned = _full_assigned_nodes(manifest)
    counts = _full_counts(value["outcomes"], assigned)
    declared = _full_keys(value["counts"], set(counts), "count_fields")
    for key, count in counts.items():
        _full_int(declared[key], 0, FULL_MAX_NODES, "count_type")
        _full_require(declared[key] == count, "count_mismatch")
    _full_require(
        not any(counts[key] for key in ("failed", "error", "unexpected_skipped", "unrun")),
        "result_incomplete",
    )
    expected_skips = sum(node["case"] in FULL_SKIP_CASES for node in assigned)
    _full_require(counts["expected_skipped"] == expected_skips, "skip_ledger")
    for node, outcome in zip(assigned, value["outcomes"], strict=True):
        if node["case"] in FULL_REQUIRED_CASES:
            _full_require(
                all(phase[0] == "passed" for phase in outcome["phases"]), "required_case_failed"
            )
        elif node["case"] in FULL_SKIP_CASES:
            expected = FULL_CASE_BY_ID[node["case"]]
            phase = outcome["phases"][expected.phase]
            _full_require(phase[0] == "skipped" and phase[2] == expected.case, "skip_ledger")
    return counts


def _full_containment(containment: object, expected_identity: dict[str, Any]) -> None:
    value = _full_keys(
        containment,
        {
            "predecessor_cleanup_sha256",
            "canary",
            "worker_exit",
            "deadline",
            "stdout_bytes",
            "source_read_only",
            "closed_network",
            "scratch_verified",
            "worker_stopped",
            "creation_uncertain",
            "resource_samples",
            "pressure_events",
            "final_probe",
        },
        "containment_fields",
    )
    predecessor = value["predecessor_cleanup_sha256"]
    if expected_identity["shard"] == "a":
        _full_require(predecessor is None, "serial_predecessor")
    else:
        _full_hash(predecessor, "serial_predecessor")
    _full_require(
        value["canary"] == "passed" and value["final_probe"] == "passed", "containment_failed"
    )
    _full_require(value["deadline"] == "completed", "workload_incomplete")
    _full_int(value["worker_exit"], 0, 0, "worker_failed")
    _full_int(value["stdout_bytes"], 0, 1048575, "output_limit")
    for field in ("source_read_only", "closed_network", "scratch_verified", "worker_stopped"):
        _full_require(value[field] is True, "containment_failed")
    _full_require(value["creation_uncertain"] is False, "creation_uncertain")
    samples = _full_keys(value["resource_samples"], {"worker", "db"}, "resource_samples")
    pressure = _full_keys(value["pressure_events"], {"worker", "db"}, "pressure_events")
    for role in ("worker", "db"):
        _full_int(samples[role], 2, 100000, "resource_samples")
        _full_int(pressure[role], 0, 0, "resource_pressure")


def validate_full_python_receipt(
    receipt: object,
    expected_identity: dict[str, Any],
    *,
    allow_pending_cleanup: bool = False,
) -> dict[str, int]:
    value = _full_keys(
        receipt,
        {
            "schema",
            "kind",
            "identity",
            "policy",
            "status",
            "failure",
            "collection",
            "result",
            "containment",
            "primary_cleanup",
            "independent_cleanup",
        },
        "receipt_fields",
    )
    _full_envelope(value, expected_identity, "ocwp.full_python.receipt")
    _full_require(len(_full_json(value)) + 1 < FULL_RECORD_LIMIT, "record_size")
    _full_require(
        type(value["status"]) is str and value["status"] in {"passed", "failed"}, "receipt_status"
    )
    failure = value["failure"]
    _full_require(
        failure is None or (type(failure) is str and failure in FULL_FAILURE_CODES), "failure_code"
    )
    pending = (
        allow_pending_cleanup
        and value["status"] == "failed"
        and failure == "independent_cleanup_pending"
        and value["independent_cleanup"] == "pending"
    )
    _full_require(pending or (value["status"] == "passed" and failure is None), "receipt_failed")
    _full_require(value["primary_cleanup"] == "verified_absent", "primary_cleanup_failed")
    _full_require(
        pending or value["independent_cleanup"] == "verified_absent", "independent_cleanup_failed"
    )
    _full_containment(value["containment"], expected_identity)
    return validate_full_python_result(value["result"], expected_identity, value["collection"])


def _full_failed_checks(code: str, source_status: str | None = None) -> list[Check]:
    detail = f"Required full-Python evidence rejected: {code}"
    if code == "identity_dirty" and source_status is not None:
        detail += f"; bounded source status: {source_status}"
    return [Check(name, "fail", detail) for name in FULL_CHECK_NAMES]


def validate_full_python_cleanup(record: object, expected_identity: dict[str, Any]) -> str:
    """Verify an absence-only gate; it cannot qualify the associated workload."""
    value = _full_keys(
        record,
        {
            "schema",
            "kind",
            "status",
            "expected_commit",
            "run_id",
            "run_attempt",
            "scope",
            "owner_manifest_present",
            "owner_token",
            "identity",
            "outcome",
            "build_resource_cleanup",
            "qualification",
        },
        "cleanup_fields",
    )
    _full_require(len(_full_json(value)) + 1 < FULL_RECORD_LIMIT, "record_size")
    _full_identity(expected_identity)
    _full_identity(value["identity"])
    _full_require(
        _full_json(value["identity"]) == _full_json(expected_identity), "identity_mismatch"
    )
    _full_require(type(value["schema"]) is int and value["schema"] == 2, "schema")
    _full_require(value["kind"] == "ocwp.full_python.independent_cleanup", "kind")
    _full_require(
        value["status"] == "unqualified"
        and value["scope"] == "manifest_owned_canary_database_worker"
        and value["build_resource_cleanup"] == "not_assessed"
        and value["qualification"] == "not_a_receipt",
        "cleanup_scope",
    )
    _full_require(
        value["expected_commit"] == expected_identity["commit"]
        and value["run_id"] == expected_identity["run_id"]
        and value["run_attempt"] == expected_identity["run_attempt"],
        "cleanup_context",
    )
    _full_require(
        value["owner_manifest_present"] is True
        and value["owner_token"] == expected_identity["nonce"],
        "cleanup_owner",
    )
    _full_require(value["outcome"] == "verified_absent", "independent_cleanup_failed")
    return hashlib.sha256(_full_json(value)).hexdigest()


def validate_full_python_pair(
    receipts: object, expected_identities: dict[str, dict[str, Any]], cleanups: object
) -> dict[str, int]:
    """Two separately bounded receipts, never an unchecked combined JSON envelope."""
    values = _full_keys(receipts, set(FULL_SHARDS), "pair_shards")
    expected = _full_keys(expected_identities, set(FULL_SHARDS), "pair_shards")
    cleanup_values = _full_keys(cleanups, set(FULL_SHARDS), "pair_shards")
    for shard in FULL_SHARDS:
        _full_identity(expected[shard])
        _full_require(expected[shard]["shard"] == shard, "pair_shards")
    a, b = (expected[shard] for shard in FULL_SHARDS)
    shared = set(a) - {"shard", "nonce", "command_sha256"}
    _full_require(all(a[key] == b[key] for key in shared), "pair_context")
    _full_require(a["nonce"] != b["nonce"], "pair_nonce")
    cleanup_digests = {
        shard: validate_full_python_cleanup(cleanup_values[shard], expected[shard])
        for shard in FULL_SHARDS
    }
    counts = {
        shard: validate_full_python_receipt(values[shard], expected[shard]) for shard in FULL_SHARDS
    }
    first, second = (values[shard] for shard in FULL_SHARDS)
    _full_require(
        _full_json(first["collection"]["nodes"]) == _full_json(second["collection"]["nodes"]),
        "pair_inventory",
    )
    _full_require(
        second["containment"]["predecessor_cleanup_sha256"] == cleanup_digests["a"],
        "pair_predecessor",
    )
    # Per-shard validation already proves ordered assignment and complete phases.
    outcomes = [receipt["result"]["outcomes"] for receipt in (first, second)]
    keys = [{item["node_sha256"] for item in items} for items in outcomes]
    inventory = {node["node_sha256"] for node in first["collection"]["nodes"]}
    _full_require(not keys[0] & keys[1] and keys[0] | keys[1] == inventory, "pair_coverage")
    _full_require(
        [outcome["node_sha256"] for items in outcomes for outcome in items]
        == [node["node_sha256"] for node in first["collection"]["nodes"]],
        "pair_order",
    )
    total = {key: sum(counts[shard][key] for shard in FULL_SHARDS) for key in counts["a"]}
    _full_require(total["expected_skipped"] == len(FULL_SKIP_CASES), "skip_ledger")
    return total


def consume_full_python_pair(
    path: Path, expected_identities: dict[str, dict[str, Any]]
) -> list[Check]:
    try:
        # Read each bounded record separately. No caller-supplied artifact selectors.
        receipts = {
            shard: read_full_python_json(path / shard / "receipt.json") for shard in FULL_SHARDS
        }
        cleanups = {
            shard: read_full_python_json(path / shard / "independent-cleanup.json")
            for shard in FULL_SHARDS
        }
        counts = validate_full_python_pair(receipts, expected_identities, cleanups)
    except FullPythonEvidenceError as error:
        return _full_failed_checks(str(error))
    detail = (
        f"Two source-bound serial invocations: {counts['passed']} passed, "
        f"{counts['expected_skipped']} exact intentional skips, zero unrun; "
        "both cleanups verified for each shard"
    )
    return [
        Check("python_tests", "pass", detail),
        Check(
            "python_psycopg",
            "pass",
            "Owned PostgreSQL 18.4, psycopg 3.3.4, UTF8 verified in both shards",
        ),
        Check(
            "postgresql_integration",
            "pass",
            "Exact migration case and all six genuine restores passed in the serial pair",
        ),
    ]


def full_python_route_checks(path: Path | None, env: dict[str, str]) -> list[Check]:
    try:
        _full_require(path is not None, "receipt_required")
        expected = {shard: full_python_expected_identity(env, shard=shard) for shard in FULL_SHARDS}
        return consume_full_python_pair(cast(Path, path), expected)
    except FullPythonEvidenceError as error:
        return _full_failed_checks(str(error), error.source_status)


def full_postgres_settings(rows: object) -> dict[str, str]:
    _full_require(
        type(rows) is list
        and len(rows) == len(FULL_POSTGRES_SETTINGS)
        and all(
            type(row) is tuple and len(row) == 2 and all(type(value) is str for value in row)
            for row in rows
        ),
        "database_settings",
    )
    settings = dict(cast(list[tuple[str, str]], rows))
    _full_require(settings == FULL_POSTGRES_SETTINGS, "database_settings")
    return settings


def _full_worker_preflight() -> dict[str, Any]:
    """Use only fixed local tools and the supervisor's owned synthetic database."""
    _full_require(Path("/app") == ROOT and Path.cwd() == ROOT, "worker_directory")
    _full_require(os.environ.get("OCWP_TEST_DATABASE_URL") == FULL_DATABASE_URL, "database_target")
    _full_require(
        not any(key.startswith("PG") for key in os.environ)
        and not any(
            os.environ.get(key)
            for key in (
                "OCWP_DATABASE_URL",
                "OCWP_DATABASE_URL_FILE",
                "OCWP_E2E_DATABASE_URL",
                "OCWP_QUOTE_MICRO",
                "OCWP_GITLEAKS_BINARY",
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
            )
        ),
        "ambient_environment",
    )
    _full_require(os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1", "plugin_autoload")
    _full_require(os.environ.get("TMPDIR") == "/tmp/ocwp-tests", "scratch_environment")
    _full_require(
        os.environ.get("OCWP_INVENTORY_READ_EVIDENCE_DIR") == "/tmp/ocwp-tests/evidence",
        "scratch_environment",
    )

    def version(command: list[str]) -> str:
        # Tools are fixed image prerequisites. A bounded scratch file avoids
        # accumulating unexpected version output in the supervising interpreter.
        with tempfile.TemporaryFile(dir="/tmp/ocwp-tests") as output:
            try:
                result = subprocess.run(
                    command, cwd=ROOT, stdout=output, stderr=output, timeout=5, check=False
                )
                _full_require(result.returncode == 0, "preflight_failed")
                _full_require(os.fstat(output.fileno()).st_size < 4096, "preflight_output")
                output.seek(0)
                return output.read(4096).decode("utf-8", errors="strict").strip()
            except (OSError, subprocess.TimeoutExpired, UnicodeError):
                raise FullPythonEvidenceError("preflight_failed") from None

    try:
        import psycopg

        values = {
            "python": platform.python_version(),
            "node": version(["node", "--version"]).removeprefix("v"),
            "pnpm": version(["pnpm", "--version"]),
            "playwright": version(
                ["node", "/app/apps/web/node_modules/@playwright/test/cli.js", "--version"]
            ).removeprefix("Version "),
            "git_available": version(["git", "--version"]).startswith("git version "),
        }
        for executable in ("pg_dump", "pg_restore", "psql"):
            raw = version([executable, "--version"])
            match = re.fullmatch(r"[a-z_]+ \(PostgreSQL\) (18\.4)(?: \([^\n]+\))?", raw)
            _full_require(match is not None, "preflight_failed")
            values[executable] = match.group(1)
        _full_require(importlib.metadata.version("pytest") == "9.1.1", "preflight_failed")
        with psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname="ocwp_quote_full_test",
            user="ocwp",
            password="ocwp-synthetic",
            connect_timeout=5,
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('server_version_num'), current_database(), "
                    "current_setting('server_encoding'), current_setting('client_encoding')"
                )
                row = cursor.fetchone()
                cursor.execute(
                    "SELECT name, current_setting(name) FROM pg_settings WHERE name = ANY(%s)",
                    (list(FULL_POSTGRES_SETTINGS),),
                )
                settings = full_postgres_settings(cursor.fetchall())
            _full_require(type(row) is tuple and len(row) == 4, "database_identity")
            values["database"] = {
                "server_version_num": int(row[0]),
                "driver": "psycopg",
                "driver_version": psycopg.__version__,
                "database": row[1],
                "server_encoding": row[2],
                "client_encoding": row[3],
                "settings": settings,
            }
    except FullPythonEvidenceError:
        raise
    except Exception:
        raise FullPythonEvidenceError("preflight_failed") from None
    _full_require(_full_json(values) == _full_json(FULL_PREFLIGHT), "preflight_failed")
    return values


class _FullPythonPlugin:
    """The complete collection is sealed before the first test body runs."""

    def __init__(self, config: Any) -> None:
        self.identity = _full_identity(
            read_full_python_value(os.environ.get("OCWP_FULL_PYTHON_IDENTITY", ""))
        )
        _full_require(
            tuple(config.invocation_params.args) == full_python_args(self.identity["shard"]),
            "pytest_command",
        )
        _full_require(
            all(self.identity[key] == value for key, value in _full_source_hashes(ROOT).items()),
            "source_hash_mismatch",
        )
        self.preflight = _full_worker_preflight()
        self.collection_errors = 0
        self.deselected = 0
        self.collection: dict[str, Any] | None = None
        self.outcomes: dict[str, dict[str, Any]] = {}
        self.cases: dict[str, str | None] = {}
        self.protocol_error = False

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed or report.skipped:
            self.collection_errors += 1

    def pytest_deselected(self, items: list[Any]) -> None:
        self.deselected += len(items)

    def pytest_collection_finish(self, session: Any) -> None:
        _full_require(0 < len(session.items) <= FULL_MAX_NODES, "collection_count")
        nodes = []
        for item in session.items:
            key = hashlib.sha256(item.nodeid.encode("utf-8")).hexdigest()
            _full_require(key not in self.cases, "duplicate_node")
            source = item.path.relative_to(ROOT).as_posix()
            _full_require(
                source.startswith(("tests/", "services/platform/tests/")), "collection_root"
            )
            _full_require(item.nodeid.startswith(source + "::"), "node_module")
            function = item.originalname
            _full_require(type(function) is str, "collection_function")
            callspec = getattr(item, "callspec", None)
            case = full_python_case(
                source, function, callspec.params if callspec is not None else {}
            )
            shard = full_python_shard(source)
            nodes.append(
                {
                    "node_sha256": key,
                    "module_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "case": case,
                }
            )
            if shard == self.identity["shard"]:
                self.outcomes[key] = {"node_sha256": key, "phases": [None, None, None]}
            self.cases[key] = case
        self.collection = {
            "schema": 2,
            "kind": "ocwp.full_python.collection",
            "identity": self.identity,
            "policy": FULL_POLICY,
            "collection_errors": self.collection_errors,
            "deselected": self.deselected,
            "nodes": nodes,
            "count": len(nodes),
            "inventory_sha256": hashlib.sha256(_full_json(nodes)).hexdigest(),
        }
        write_full_python_json(Path("/tmp/ocwp-proof/collection.json"), self.collection)
        _full_collection(self.collection, self.identity)
        # Planned partitioning is not pytest deselection. The complete manifest is
        # already sealed, while unexpected deselection remains a hard failure.
        session.items[:] = [
            item
            for item in session.items
            if full_python_shard(item.path.relative_to(ROOT).as_posix()) == self.identity["shard"]
        ]

    def pytest_runtest_logreport(self, report: Any) -> None:
        try:
            key = hashlib.sha256(report.nodeid.encode("utf-8")).hexdigest()
            _full_require(key in self.outcomes, "unknown_report")
            _full_require(report.when in ("setup", "call", "teardown"), "phase_status")
            index = ("setup", "call", "teardown").index(report.when)
            phases = self.outcomes[key]["phases"]
            _full_require(phases[index] is None, "duplicate_phase")
            _full_require(all(phase is None for phase in phases[index + 1 :]), "phase_order")
            if index > 0:
                _full_require(phases[0] is not None, "phase_order")
            if index == 1:
                _full_require(phases[0][0] == "passed", "phase_order")
            _full_require(
                type(report.duration) in (int, float)
                and math.isfinite(report.duration)
                and 0 <= report.duration <= 900,
                "phase_duration",
            )
            status = report.outcome
            _full_require(status in ("passed", "failed", "skipped"), "phase_status")
            skipped = None
            if hasattr(report, "wasxfail"):
                status, skipped = "skipped", "unexpected"
            elif status == "skipped":
                skipped = "unexpected"
                case = FULL_CASE_BY_ID.get(self.cases[key])
                raw = report.longrepr
                if (
                    case is not None
                    and case.reason is not None
                    and case.phase == index
                    and type(raw) is tuple
                    and len(raw) == 3
                    and type(raw[2]) is str
                    and raw[2] == "Skipped: " + case.reason
                ):
                    skipped = case.case
            phases[index] = [status, int(report.duration * 1000000), skipped]
        except (FullPythonEvidenceError, UnicodeError):
            self.protocol_error = True
            raise

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        if self.collection is None:
            return
        outcomes = list(self.outcomes.values())
        try:
            counts = _full_counts(outcomes, _full_assigned_nodes(self.collection))
        except FullPythonEvidenceError:
            self.protocol_error = True
            raise
        result = {
            "schema": 2,
            "kind": "ocwp.full_python.result",
            "identity": self.identity,
            "policy": FULL_POLICY,
            "inventory_sha256": self.collection["inventory_sha256"],
            "session_finished": not self.protocol_error,
            "exit_code": int(exitstatus),
            "collection_errors": self.collection_errors,
            "deselected": self.deselected,
            "preflight": self.preflight,
            "outcomes": outcomes,
            "counts": counts,
        }
        write_full_python_json(Path("/tmp/ocwp-proof/result.json"), result)


def pytest_addoption(parser: Any) -> None:
    parser.addoption("--ocwp-full-shard", choices=FULL_SHARDS, default=None)


def pytest_configure(config: Any) -> None:
    if os.environ.get("OCWP_FULL_PYTHON") == "contained":
        config.pluginmanager.register(_FullPythonPlugin(config), "ocwp-full-python-proof")


def run_check(
    name: str,
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> Check:
    result = subprocess.run(command, cwd=cwd or ROOT, env=env, text=True, capture_output=True)
    detail = (result.stdout + result.stderr).strip()
    return Check(
        name=name, status="pass" if result.returncode == 0 else "fail", detail=detail[-4000:]
    )


def probe_tool(name: str, executable: str, version_args: list[str], blocked_reason: str) -> Check:
    path = shutil.which(executable)
    if not path:
        return Check(f"tool_{name}", "blocked", blocked_reason)
    try:
        result = subprocess.run(
            [path, *version_args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Check(f"tool_{name}", "blocked", f"{blocked_reason}; probe failed: {error}")
    detail = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        suffix = detail[-1000:] if detail else f"exit {result.returncode}"
        return Check(f"tool_{name}", "blocked", f"{blocked_reason}; probe failed: {suffix}")
    version = detail.splitlines()[0] if detail else "version probe passed"
    return Check(f"tool_{name}", "pass", f"{path} · {version}")


def qualification_metadata() -> dict[str, str | bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    git_sha = commit.stdout.strip() if commit.returncode == 0 else "unknown"
    node = subprocess.run(
        ["node", "--version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    node_version = node.stdout.strip() if node.returncode == 0 else "unavailable"
    return {
        "git_sha": git_sha,
        "python": platform.python_version(),
        "node": node_version,
        "platform": platform.platform(),
        "ci": bool(os.environ.get("CI")),
    }


def static_analysis_checks(
    *,
    pnpm_probe: Check,
    ruff_probe: Check,
    mypy_probe: Check,
    env: dict[str, str],
) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []

    if ruff_probe.status == "pass" and mypy_probe.status == "pass":
        checks.extend(
            [
                run_check(
                    "python_ruff",
                    [
                        "ruff",
                        "check",
                        "services/platform/src",
                        "services/platform/tests",
                        "tests",
                        "scripts",
                    ],
                    env=env,
                ),
                run_check(
                    "python_format",
                    [
                        "ruff",
                        "format",
                        "--check",
                        "services/platform/src",
                        "services/platform/tests",
                        "tests",
                        "scripts",
                    ],
                    env=env,
                ),
                run_check("python_mypy", ["mypy", "services/platform/src"], env=env),
            ]
        )
    else:
        blockers.append(
            Check("python_static_analysis", "blocked", "Ruff and mypy must both execute")
        )

    if pnpm_probe.status == "pass":
        checks.extend(
            [
                # Direct node invocations: pnpm launched from this Python
                # process resolves tool versions differently across
                # platforms; the workspace bins are the source of truth.
                run_check(
                    "frontend_eslint",
                    ["node", str(ROOT / "node_modules" / "eslint" / "bin" / "eslint.js"), "."],
                    env=env,
                ),
                run_check(
                    "frontend_prettier",
                    [
                        "node",
                        str(ROOT / "node_modules" / "prettier" / "bin" / "prettier.cjs"),
                        "--check",
                        "**/*.{js,mjs,ts,tsx,json,css,md,yml,yaml}",
                    ],
                    env=env,
                ),
            ]
        )
    else:
        blockers.append(
            Check(
                "frontend_static_analysis",
                "blocked",
                "pnpm must execute with workspace dependencies",
            )
        )

    return checks, blockers


def postgresql_runtime_checks(env: dict[str, str]) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []
    if importlib.util.find_spec("psycopg") is None:
        blockers.append(
            Check(
                "python_psycopg",
                "blocked",
                "psycopg v3 is not installed in the execution environment",
            )
        )
    else:
        checks.append(Check("python_psycopg", "pass", "psycopg v3 import available"))

    database_url = env.get("OCWP_TEST_DATABASE_URL")
    if not database_url:
        blockers.append(
            Check("postgresql_integration", "blocked", "OCWP_TEST_DATABASE_URL is required")
        )
    elif any(item.name == "python_psycopg" for item in blockers):
        blockers.append(
            Check(
                "postgresql_integration",
                "blocked",
                "psycopg v3 is required for PostgreSQL integration",
            )
        )
    else:
        checks.append(
            run_check(
                "postgresql_integration",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "services/platform/tests/db/test_postgres_integration.py",
                ],
                env=env,
            )
        )
    return checks, blockers


def indexeddb_runtime_check() -> Check:
    result = subprocess.run(
        [sys.executable, "scripts/benchmarks/run_indexeddb_native_benchmark.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    detail = (result.stdout + result.stderr).strip()[-4000:]
    if result.returncode == 0:
        return Check("indexeddb_100k", "pass", detail)
    if result.returncode == 2:
        return Check("indexeddb_100k", "blocked", detail)
    return Check("indexeddb_100k", "fail", detail)


def browser_runtime_checks(
    pnpm_probe: Check, env: dict[str, str]
) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []
    if pnpm_probe.status != "pass":
        blockers.extend(
            [
                Check(
                    "pwa_build",
                    "blocked",
                    "pnpm must execute with installed workspace dependencies",
                ),
                Check(
                    "browser_e2e",
                    "blocked",
                    "pnpm/Playwright must execute before browser E2E can run",
                ),
            ]
        )
        return checks, blockers

    web = ROOT / "apps" / "web"
    tsc_bin = str(ROOT / "node_modules" / "typescript" / "bin" / "tsc")
    vite_bin = str(web / "node_modules" / "vite" / "bin" / "vite.js")
    playwright_bin = str(web / "node_modules" / "@playwright" / "test" / "cli.js")

    def web_build() -> Check:
        # Replicate the package build script (`tsc -b && vite build`) with
        # direct node invocations: pnpm launched from this Python process
        # resolves differently across platforms and shells.
        compile_check = run_check("pwa_build", ["node", tsc_bin, "-b"], env=env, cwd=web)
        if compile_check.status != "pass":
            return Check("pwa_build", "fail", f"tsc -b failed: {compile_check.detail[-500:]}")
        current = run_check("pwa_build", ["node", vite_bin, "build"], env=env, cwd=web)
        if current.status != "pass":
            return current
        return run_check(
            "pwa_build",
            [
                "node",
                "scripts/e2e/build_legacy_client.mjs",
                "artifacts/legacy-client",
                "--verify-reproducible",
            ],
            env=env,
        )

    checks.append(web_build())
    if checks[-1].status != "pass":
        checks.append(Check("browser_e2e", "fail", "current or pinned old PWA build failed"))
        return checks, blockers
    database_url = env.get("OCWP_E2E_DATABASE_URL")
    if not database_url:
        blockers.append(
            Check(
                "browser_e2e",
                "blocked",
                "OCWP_E2E_DATABASE_URL is required for destructive browser E2E setup",
            )
        )
        return checks, blockers

    prepare = run_check(
        "browser_e2e_prepare", [sys.executable, "scripts/e2e/prepare_e2e_database.py"], env=env
    )
    checks.append(prepare)
    if prepare.status != "pass":
        checks.append(Check("browser_e2e", "fail", "browser E2E database preparation failed"))
        return checks, blockers
    # Override inherited direct/repeat paths even outside CI. Playwright clears
    # its output directory on every invocation, so qualification owns siblings.
    browser_env = {
        **env,
        "OCWP_PLAYWRIGHT_OUTPUT_DIR": str(web / "test-results/qualification"),
        "PLAYWRIGHT_HTML_OUTPUT_DIR": str(web / "playwright-report/qualification"),
    }
    checks.append(
        run_check("browser_e2e", ["node", playwright_bin, "test"], env=browser_env, cwd=web)
    )
    return checks, blockers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--allow-blocked", action="store_true")
    parser.add_argument(
        "--full-python-receipt",
        type=Path,
        help="Directory with fixed a/receipt.json and b/receipt.json",
    )
    args = parser.parse_args()

    python_env = dict(__import__("os").environ)
    python_env["PYTHONPATH"] = str(ROOT / "services/platform/src")
    receipt_route = args.full_python_receipt is not None or bool(python_env.get("CI"))
    full_checks = (
        full_python_route_checks(args.full_python_receipt, python_env) if receipt_route else []
    )
    checks = [
        run_check("repository_contract", [sys.executable, "scripts/ci/verify_repository.py"]),
        (
            full_checks[0]
            if receipt_route
            else run_check("python_tests", [sys.executable, "-m", "pytest", "-q"], env=python_env)
        ),
        run_check(
            "runtime_http_smoke",
            [sys.executable, "scripts/ci/runtime_http_smoke.py"],
            env=python_env,
        ),
        run_check("frontend_core_tests", ["node", "apps/web/tools/run-core-tests.mjs"]),
        run_check(
            "api_client_core_tests", ["node", "packages/api-client/tools/run-core-tests.mjs"]
        ),
        run_check(
            "frontend_offline_typecheck",
            # Run the workspace TypeScript directly with node: `pnpm exec`
            # from a Python subprocess resolves different tsc versions or
            # breaks pnpm's self-management depending on the platform.
            [
                "node",
                str(ROOT / "node_modules" / "typescript" / "bin" / "tsc"),
                "-p",
                "apps/web/tsconfig.offline-check.json",
                "--pretty",
                "false",
            ],
        ),
        run_check(
            "openapi_contract",
            [sys.executable, "scripts/contracts/export_openapi.py", "--check"],
            env=python_env,
        ),
        run_check(
            "typescript_api_contract",
            [sys.executable, "scripts/contracts/generate_ts_client.py", "--check"],
        ),
        run_check(
            "typescript_api_typecheck",
            [
                "node",
                str(ROOT / "node_modules" / "typescript" / "bin" / "tsc"),
                "-p",
                "packages/api-client/tsconfig.json",
                "--pretty",
                "false",
            ],
        ),
    ]

    blockers: list[Check] = []
    if receipt_route:
        checks.extend(full_checks[1:])
    else:
        postgresql_checks, postgresql_blockers = postgresql_runtime_checks(python_env)
        checks.extend(postgresql_checks)
        blockers.extend(postgresql_blockers)
    for filename, name, reason in (
        (
            "pnpm-lock.yaml",
            "pnpm_lock",
            "registry access is required to produce and verify the lockfile",
        ),
        (
            "uv.lock",
            "uv_lock",
            "registry/cache access is required to produce and verify the lockfile",
        ),
    ):
        if (ROOT / filename).is_file():
            checks.append(Check(name, "pass", filename))
        else:
            blockers.append(Check(name, "blocked", reason))

    tool_probes: dict[str, Check] = {}
    for name, executable, version_args, reason in (
        ("docker", "docker", ["--version"], "Docker CLI is unavailable in the execution container"),
        (
            "pnpm",
            "pnpm",
            ["--version"],
            "pnpm cannot execute because the npm registry is unreachable "
            "or Corepack is not provisioned",
        ),
        (
            "psql",
            "psql",
            ["--version"],
            "PostgreSQL client/server tools are unavailable in the execution container",
        ),
        ("ruff", "ruff", ["--version"], "Ruff is not installed in the execution container"),
        ("mypy", "mypy", ["--version"], "mypy is not installed in the execution container"),
    ):
        probe = probe_tool(name, executable, version_args, reason)
        tool_probes[name] = probe
        (checks if probe.status == "pass" else blockers).append(probe)

    pnpm_probe = tool_probes["pnpm"]
    static_checks, static_blockers = static_analysis_checks(
        pnpm_probe=pnpm_probe,
        ruff_probe=tool_probes["ruff"],
        mypy_probe=tool_probes["mypy"],
        env=python_env,
    )
    checks.extend(static_checks)
    blockers.extend(static_blockers)
    indexeddb_check = indexeddb_runtime_check()
    (checks if indexeddb_check.status != "blocked" else blockers).append(indexeddb_check)
    browser_checks, browser_blockers = browser_runtime_checks(pnpm_probe, python_env)
    checks.extend(browser_checks)
    blockers.extend(browser_blockers)

    failed = [check for check in checks if check.status == "fail"]
    status = "failed" if failed else ("partial" if blockers else "passed")
    report = {
        "schema": 2,
        "release": "V0.1",
        "status": status,
        "metadata": qualification_metadata(),
        "checks": [asdict(check) for check in checks],
        "blockers": [asdict(check) for check in blockers],
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")

    if failed:
        return 1
    if blockers and not args.allow_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
