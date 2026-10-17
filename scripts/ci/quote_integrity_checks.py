"""Seven fixed integrity groups; source preparation is not runtime evidence.

SPDX-FileCopyrightText: 2026 Open Cycling Workshop Platform contributors
SPDX-License-Identifier: AGPL-3.0-only

Only prepare/run/cleanup and seven source-declared environment group keys exist.
No caller selector, path, budget or retry exists. Host imports only the pinned baseline.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import resource
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts/ci/frozen_quote_guard/baseline_323661ad.py"
BASELINE_SHA = "1d7e19e627d9b0506813a12b76829defa9905550537f00a2a8e5d5c359149db6"
CANDIDATE_SHA = {
    "scripts/ci/quote_capacity_micro.py": (
        "39f60d861187048878b32b55f3834168ca19f199c1e090d38bffb37fe9db0d6b"
    ),
    "tests/operations/test_quote_integrity_static_contracts.py": (
        "f9b40338f3cbec87b6a5d04d4d415cfc2964609212c01db4e0889cfce6f8c440"
    ),
    "services/platform/src/cycling_workshop/quotes/repository.py": (
        "8a672931a4b5a8cff831f1466e7bd97bd1b31d2991f77b6160ebce69501bbe91"
    ),
    "services/platform/src/cycling_workshop/quotes/service.py": (
        "f72715b6bcc38635b394e0257c4c63ff62c5ef9b15fe9116c4eee959618caed3"
    ),
    "services/platform/src/cycling_workshop/quotes/responses.py": (
        "f21fcff0793d682abe6f120fb897ff7cce1d356b5bce22d71b972d91b91f68c6"
    ),
    "services/platform/tests/quotes/test_quote_application_service.py": (
        "cb8fa657410399b091454c1324ddec1faf28c52f7d629b7a609eb73602a3a57f"
    ),
    "services/platform/tests/quotes/test_quote_atomic_effects.py": (
        "e02f262efa710eaacf2e0d5a045187eaa4ba64067fcef77dd9341ef27c8eb7e4"
    ),
    "services/platform/tests/quotes/test_quote_command_response.py": (
        "a7c8665c9043caa5455c78c46cd5fda17f564e6a9232a37287e51fa4aba7d2d7"
    ),
    "services/platform/tests/identity/test_identity_migration.py": (
        "52aca207fc09a15aae626947d622a32085533d7ed4225d988dce32541630a877"
    ),
    "scripts/ci/quote_integrity_postgres.py": (
        "f3ccf930302e424830dd6346f2cc112778bffb88d4393fd795da65b1da27da7c"
    ),
    "tests/operations/test_quote_integrity_selection.py": (
        "4243d459fa40380658e5f6c9783322c3cc44517a763a81f146424ab49a116d00"
    ),
    ".github/workflows/quote-integrity-checks.yml": (
        "cdf6b937fdc92fc90646fcc7f400594bf6c392b9794643e50f54e49af96b8616"
    ),
    ".github/workflows/quote-integrity-style-checks.yml": (
        "7023b418b4fd6061f2b10fb82a1446deb9d1d33ffc93ee11339476d9137be20b"
    ),
    ".github/workflows/quote-integrity-format-checks.yml": (
        "cb383e9e1176e585a1322697644d8d6ee75a8ea5ebbbb0fe4008f81c197855ba"
    ),
    "services/platform/tests/sync/test_prepared_order_change.py": (
        "265627babde722d95f364becec13dca70efb02fb9128c69a8692b62e8a38d812"
    ),
    "services/platform/tests/quotes/test_quote_bounded_effects_postgres.py": (
        "3371ea170bcaa11a9478e8a30ae4c1bc20ea0e89dd767323378a3af69e4fd1f7"
    ),
    ".github/workflows/quote-loader-writer-checks.yml": (
        "14cd94ec07eaf2055dd6db07beb2ba2ffae10e5d449ea7857b7232a9045b0b7c"
    ),
    ".github/workflows/quote-loader-static-checks.yml": (
        "a4b6dbc53b4a35162271823715e6e2c89fee9ce291d8bc0e530043d1b50d9e07"
    ),
    ".github/workflows/quote-loader-format-checks.yml": (
        "27bb6de03bcfec349f18076363c16bcec0e1d624369c03b12d7a3a8b8fce814b"
    ),
    "services/platform/tests/quotes/test_quote_service_decisions_postgres.py": (
        "e6ef7431067f34d20dc6404c3517e8cafc25657f6136b9f3020ec38dbd3b0d9f"
    ),
    "services/platform/tests/quotes/test_quote_payload_integrity_postgres.py": (
        "2f69a3fd8ce6d3f1532821377bf144c5e16ba4177c3ea1318785a1723f9655c4"
    ),
    "services/platform/tests/quotes/test_quote_service_atomicity_postgres.py": (
        "159d746b433864c50070fa41d26e73cec134df98451d4707caa491a7f5fa83f9"
    ),
    "services/platform/tests/quotes/test_quote_service_races_postgres.py": (
        "484d13587927d6c3b07f2b61ec0ecb12af8c3537effe4de148d4554bde969825"
    ),
    ".github/workflows/quote-semantic-closure-checks.yml": (
        "229704b528b71cc7f9a27b3a53aff9d4f50fd6188a27efa79f0062b6913e1c6e"
    ),
    ".github/workflows/quote-semantic-style-checks.yml": (
        "d702dbf02aea6022c9f684d9105ae622975d65e554cd0557fdcaf5247e1b3f92"
    ),
}
LOCKED_INPUT_SHA = {
    "pyproject.toml": "fd9f19fdeea77c028552a7f9aaeaa3adb42358fa4859c7d7229ae27d6e859be5",
    "uv.lock": "4439fc18e440130de10912aecf5a0cb7b18d4a27714e1c4fc20ccb4a4011febb",
    "services/platform/pyproject.toml": (
        "38333b1d09dcfdd86778611ded96c8d310003f6a987cff3f6fdfe6d323fc460c"
    ),
    "LICENSE": "5132c7f0475b02c8107a2e0f0363e70423c62d2664ab927e76193226e5e05905",
}
LIMIT = 16 * 1024
BRANCH = "refs/heads/codex/quote-integrity-checks"
WORKFLOW = ".github/workflows/quote-integrity-checks.yml"
STYLE_BRANCH = "refs/heads/codex/quote-integrity-style-checks"
STYLE_WORKFLOW = ".github/workflows/quote-integrity-style-checks.yml"
FORMAT_BRANCH = "refs/heads/codex/quote-integrity-format-checks"
FORMAT_WORKFLOW = ".github/workflows/quote-integrity-format-checks.yml"
LOADER_BRANCH = "refs/heads/codex/quote-loader-writer-checks"
LOADER_WORKFLOW = ".github/workflows/quote-loader-writer-checks.yml"
LOADER_STATIC_BRANCH = "refs/heads/codex/quote-loader-static-checks"
LOADER_STATIC_WORKFLOW = ".github/workflows/quote-loader-static-checks.yml"
LOADER_FORMAT_BRANCH = "refs/heads/codex/quote-loader-format-checks"
LOADER_FORMAT_WORKFLOW = ".github/workflows/quote-loader-format-checks.yml"
SEMANTIC_BRANCH = "refs/heads/codex/quote-semantic-closure-checks"
SEMANTIC_WORKFLOW = ".github/workflows/quote-semantic-closure-checks.yml"
SEMANTIC_STYLE_BRANCH = "refs/heads/codex/quote-semantic-style-checks"
SEMANTIC_STYLE_WORKFLOW = ".github/workflows/quote-semantic-style-checks.yml"
IMAGE_PREFIX = "ocwp-quote-integrity-"
SERVICE_PATH = "services/platform/tests/quotes/test_quote_application_service.py"
ATOMIC_PATH = "services/platform/tests/quotes/test_quote_atomic_effects.py"
RESPONSE_PATH = "services/platform/tests/quotes/test_quote_command_response.py"
STATIC_PATH = "tests/operations/test_quote_integrity_static_contracts.py"
SELECTION_PATH = "tests/operations/test_quote_integrity_selection.py"
SOURCE_CLASSES = {
    SERVICE_PATH: "services.platform.tests.quotes.test_quote_application_service",
    ATOMIC_PATH: "services.platform.tests.quotes.test_quote_atomic_effects",
    RESPONSE_PATH: "services.platform.tests.quotes.test_quote_command_response",
    STATIC_PATH: "tests.operations.test_quote_integrity_static_contracts",
    SELECTION_PATH: "tests.operations.test_quote_integrity_selection",
}
# Complete fixed functions: count and maximum JSON-encoded parameter suffix bytes.
GROUPS = {
    "service27": (
        (
            SERVICE_PATH,
            (
                ("test_create_decide_replay_commits_one_complete_tuple", 1, 8),
                ("test_false_flag_denies_new_but_preserves_exact_revision_replay", 1, 8),
                ("test_replay_requires_fresh_operation_grants", 5, 32),
                ("test_historical_quote_only_decision_replay_does_not_invent_transition", 1, 8),
                ("test_response_failure_rolls_back_all_decision_effects", 1, 8),
                ("test_commit_ack_loss_is_unknown_and_same_identity_replays", 1, 8),
                ("test_expired_deadline_refuses_before_writer_or_effects", 1, 8),
                ("test_foreign_actor_and_noncustomer_decision_are_refused", 1, 8),
                ("test_nul_order_reference_refuses_before_text_hydration", 2, 48),
                ("test_service_does_not_take_ownership_of_existing_transaction", 1, 8),
                ("test_replay_retains_receipt_after_order_cancellation", 1, 8),
                ("test_expiry_after_order_effect_flush_rolls_back_outer_transaction", 1, 8),
                ("test_create_revise_initial_and_revision_replays", 1, 8),
                ("test_failed_rollback_and_invalidation_preserve_closed_cleanup_state", 1, 8),
                ("test_hook_cleanup_failure_never_replaces_unknown_commit", 1, 8),
                ("test_driver_budget_failure_invalidates_instead_of_returning_connection", 1, 8),
            ),
        ),
        (
            SELECTION_PATH,
            (
                ("test_fixed_postgres_selection_and_argv", 1, 0),
                ("test_typed_postgres_collection_contract", 1, 0),
                ("test_closed_postgres_reports_and_identities", 1, 0),
                ("test_metadata_observer_and_bridge_registration", 1, 0),
                ("test_numeric_failure_bounds_and_static_exactness", 1, 0),
                ("test_fixed_junit_maps_and_parser", 1, 0),
            ),
        ),
    ),
    "atomic18_corruption": (
        (
            ATOMIC_PATH,
            (
                ("test_corrupt_effect_association_has_normalized_integrity_error", 15, 64),
                ("test_missing_or_duplicate_effect_is_not_repaired", 3, 24),
            ),
        ),
    ),
    "atomic18_other": (
        (
            ATOMIC_PATH,
            (
                ("test_actual_fresh_result_and_complete_receipt_exist_on_first_insert", 1, 8),
                ("test_historical_null_effect_replay_never_creates_transition", 1, 8),
                ("test_absent_operation_policy_runs_before_stale_cas_and_any_effect", 1, 8),
                ("test_failure_after_order_effects_rolls_back_complete_operation", 1, 8),
                ("test_missing_or_boolean_tuple_field_is_not_treated_as_historical", 1, 8),
                ("test_unsupported_effect_version_is_rejected", 6, 16),
                ("test_version_on_historical_empty_tuple_is_rejected", 1, 8),
                ("test_foreign_cursor_is_refused_without_materializing_its_payload", 1, 8),
                ("test_delivery_bookkeeping_does_not_change_receipt", 1, 8),
                ("test_application_decision_requires_complete_effects", 1, 8),
                ("test_late_checkpoint_rolls_back_effects_without_integrity_normalization", 1, 8),
                ("test_reconstruction_checkpoint_escapes_integrity_normalization", 1, 8),
                ("test_replay_after_later_cancellation_retains_original_transition", 1, 8),
            ),
        ),
    ),
    "response50": (
        (
            RESPONSE_PATH,
            (("test_numeric_fields_refuse_coercion_and_unsafe_values", 50, 24),),
        ),
    ),
    "response64": (
        (
            RESPONSE_PATH,
            (
                ("test_create_and_applied_decision_round_trip_exact_closed_fields", 1, 0),
                ("test_replay_preserves_historical_quote_only_decision_with_fresh_context", 1, 0),
                ("test_revision_and_replayed_transition_keep_operation_time_fields", 1, 0),
                (
                    "test_applied_decision_requires_transition_and_revision_requires_quote_only",
                    2,
                    8,
                ),
                ("test_effect_tuple_refuses_partial_nulls_and_nonnull_quote_only", 4, 25),
                ("test_receipt_ordinal_is_the_safe_sum_of_revision_and_decision_sequence", 2, 37),
                ("test_order_transition_requires_two_distinct_outbox_delivery_identities", 1, 0),
                ("test_all_objects_refuse_extra_fields_and_require_every_listed_field", 7, 7),
                ("test_positive_versions_refuse_zero", 7, 7),
                ("test_literal_discriminators_and_states_are_closed", 5, 7),
                ("test_legacy_identifiers_keep_composite_canonical_validation", 16, 45),
                ("test_quote_outbox_requires_canonical_uuidv7", 3, 38),
                ("test_recording_requires_canonical_calendar_valid_microsecond_utc", 2, 29),
                ("test_service_projector_preserves_four_digit_receipt_year", 8, 12),
                ("test_scope_and_current_decision_must_match_current_head", 1, 0),
                ("test_withdrawal_remains_visible_and_safe_integer_extreme_is_exact", 1, 0),
                ("test_order_state_schema_matches_existing_nine_state_domain_enum", 1, 0),
                ("test_encoder_revalidates_nested_bypasses_and_checks_actual_utf8_bytes", 1, 0),
            ),
        ),
    ),
    "static6": (
        (
            STATIC_PATH,
            (
                ("test_repository_contract", 1, 0),
                ("test_python_lint", 1, 0),
                ("test_python_format", 1, 0),
                ("test_production_types", 1, 0),
                ("test_openapi_contract", 1, 0),
                ("test_generated_client_contract", 1, 0),
            ),
        ),
    ),
    "selection_static12": (
        (
            SELECTION_PATH,
            (
                ("test_fixed_postgres_selection_and_argv", 1, 0),
                ("test_typed_postgres_collection_contract", 1, 0),
                ("test_closed_postgres_reports_and_identities", 1, 0),
                ("test_metadata_observer_and_bridge_registration", 1, 0),
                ("test_numeric_failure_bounds_and_static_exactness", 1, 0),
                ("test_fixed_junit_maps_and_parser", 1, 0),
            ),
        ),
        (
            STATIC_PATH,
            (
                ("test_repository_contract", 1, 0),
                ("test_python_lint", 1, 0),
                ("test_python_format", 1, 0),
                ("test_production_types", 1, 0),
                ("test_openapi_contract", 1, 0),
                ("test_generated_client_contract", 1, 0),
            ),
        ),
    ),
}
GROUP_COUNTS = {
    "service27": 27,
    "atomic18_corruption": 18,
    "atomic18_other": 18,
    "response50": 50,
    "response64": 64,
    "static6": 6,
    "selection_static12": 12,
}
GROUP_KEY = os.environ.get("OCWP_INTEGRITY_GROUP", "")
SELECTION = GROUPS.get(GROUP_KEY, ())
NODES = tuple(f"{path}::{name}" for path, cases in SELECTION for name, _, _ in cases)
EXPECTED_COUNTS = {name: count for _, cases in SELECTION for name, count, _ in cases}
CLASS_NAMES = [SOURCE_CLASSES[path] for path, _ in SELECTION]
CASE_COUNT = GROUP_COUNTS.get(GROUP_KEY, 0)
SPOOL_LIMIT = 32 * 1024 if GROUP_KEY in ("static6", "selection_static12") else LIMIT
JUNIT_PATH = "/tmp/quote-integrity-checks.xml"
PYTEST = [
    "env",
    "-i",
    "PATH=/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
    "HOME=/tmp",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
    *(
        ["OCWP_QUOTE_SERVICE_INITIAL=contained"]
        if GROUP_KEY in ("static6", "selection_static12")
        else []
    ),
    "/app/.venv/bin/python",
    "-m",
    "pytest",
    "-q",
    "-o",
    "addopts=",
    "-o",
    "junit_family=xunit2",
    "-p",
    "no:cacheprovider",
    "--tb=short",
    "--no-showlocals",
    "--show-capture=no",
    "--capture=fd",
    "--maxfail=1",
    "--basetemp=/tmp/quote-integrity-checks",
    "-W",
    "error::pytest.PytestUnhandledThreadExceptionWarning",
    "-W",
    "error::pytest.PytestUnraisableExceptionWarning",
    f"--junitxml={JUNIT_PATH}",
    *NODES,
]
DOCKERFILE = (
    "FROM ghcr.io/astral-sh/uv:0.11.15 AS uv\n"
    "FROM python:3.13.14-slim-trixie\n"
    "COPY --from=uv /uv /bin/uv\n"
    "ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1\n"
    "RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends git "
    "&& rm -rf /var/lib/apt/lists/*\n"
    "WORKDIR /app\n"
    "COPY . /app/\n"
    "RUN uv sync --all-packages --group dev --locked\n"
    "ARG SOURCE_TREE\n"
    "LABEL ocwp.source-tree=$SOURCE_TREE\n"
    "USER 10001:10001\n"
)


class Refusal(RuntimeError):
    pass


def require(condition: bool) -> None:
    if not condition:
        raise Refusal("fixed_bootstrap_unqualified")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_baseline():
    require(digest(BASELINE) == BASELINE_SHA)
    spec = importlib.util.spec_from_file_location("ocwp_frozen_323661ad", BASELINE)
    require(spec is not None and spec.loader is not None)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def gate() -> None:
    require(GROUP_KEY in GROUPS and sum(EXPECTED_COUNTS.values()) == CASE_COUNT)
    require(Path.cwd().resolve() == ROOT)
    require(os.environ.get("GITHUB_EVENT_NAME") == "push")
    branch, workflow = BRANCH, WORKFLOW
    if os.environ.get("GITHUB_REF") == STYLE_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = STYLE_BRANCH, STYLE_WORKFLOW
    elif os.environ.get("GITHUB_REF") == FORMAT_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = FORMAT_BRANCH, FORMAT_WORKFLOW
    elif os.environ.get("GITHUB_REF") == LOADER_STATIC_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = LOADER_STATIC_BRANCH, LOADER_STATIC_WORKFLOW
    elif os.environ.get("GITHUB_REF") == LOADER_FORMAT_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = LOADER_FORMAT_BRANCH, LOADER_FORMAT_WORKFLOW
    elif os.environ.get("GITHUB_REF") == LOADER_BRANCH:
        require(GROUP_KEY == "selection_static12")
        branch, workflow = LOADER_BRANCH, LOADER_WORKFLOW
    elif os.environ.get("GITHUB_REF") == SEMANTIC_STYLE_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = SEMANTIC_STYLE_BRANCH, SEMANTIC_STYLE_WORKFLOW
    elif os.environ.get("GITHUB_REF") == SEMANTIC_BRANCH:
        require(GROUP_KEY == "selection_static12")
        branch, workflow = SEMANTIC_BRANCH, SEMANTIC_WORKFLOW
    else:
        require(GROUP_KEY != "selection_static12")
    require(os.environ.get("GITHUB_REF") == branch)
    require(os.environ.get("GITHUB_RUN_NUMBER") == "1")
    require(os.environ.get("GITHUB_RUN_ATTEMPT") == "1")
    require(
        os.environ.get("GITHUB_WORKFLOW_REF")
        == f"{os.environ.get('GITHUB_REPOSITORY')}/{workflow}@{branch}"
    )
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_NUMBER", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", os.environ.get(key, "")) is not None)
    require(re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is not None)
    require(Path(os.environ["RUNNER_TEMP"]).is_dir())


def paths() -> tuple[Path, Path]:
    root = Path(os.environ["RUNNER_TEMP"])
    return (
        root / f"quote-integrity-{GROUP_KEY}-prepared.json",
        root / f"quote-integrity-{GROUP_KEY}-owned.json",
    )


def base_report() -> dict:
    return {
        "schema": 1,
        "status": "failed",
        "commit": os.environ["GITHUB_SHA"],
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_number": 1,
        "run_attempt": 1,
        "mode": "fixed_integrity_checks",
        "group": GROUP_KEY,
        "baseline_sha256": BASELINE_SHA,
        "wrapper_sha256": digest(Path(__file__)),
        "candidate_sha256": CANDIDATE_SHA,
        "locked_input_sha256": LOCKED_INPUT_SHA,
        "service_behavior_qualified": False,
        "postgresql_qualified": False,
        "capacity_qualified": False,
        "activation_qualified": False,
    }


def write_report(name: str, value: dict) -> None:
    raw = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    require(len(raw.encode("utf-8")) < LIMIT)
    target = ROOT / "artifacts" / name
    target.parent.mkdir(exist_ok=True)
    target.write_text(raw)


class Stage:
    """Reserve baseline run's two-second reap grace inside each stage deadline."""

    def __init__(self, helper, deadline: float):
        self.helper = helper
        self.deadline = deadline

    def check(self, reserve: float = 0) -> None:
        require(time.monotonic() + reserve < self.deadline)

    def __call__(self, args: list[str], *, timeout: float = 5) -> str:
        self.check(2)
        result = self.helper.run(args, timeout=min(timeout, self.deadline - time.monotonic() - 2))
        self.check()
        return result


def source(helper, execute, *, clean: bool) -> str:
    require(helper.source_query("head", execute) == os.environ["GITHUB_SHA"])
    if clean:
        require(helper.source_query("status", execute) == "")
    tree = helper.source_query("tree", execute)
    require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None)
    require(
        all(
            digest(ROOT / name) == value
            for name, value in (CANDIDATE_SHA | LOCKED_INPUT_SHA).items()
        )
    )
    return tree


def archive_source(helper, target: Path, execute: Stage) -> None:
    # Source tar bytes are not diagnostic output. Stream at most 64 MiB through
    # a pipe; preserve the 16 KiB stderr cap without applying it to source files.
    deadline = min(time.monotonic() + 20, execute.deadline - 2)
    with tempfile.TemporaryFile() as errors, target.open("xb") as archive:
        child = subprocess.Popen(
            ["git", "archive", "--format=tar", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=errors,
            start_new_session=True,
            preexec_fn=helper.output_limit,
        )
        total = 0
        try:
            require(child.stdout is not None)
            os.set_blocking(child.stdout.fileno(), False)
            while True:
                require(time.monotonic() < deadline and os.fstat(errors.fileno()).st_size < LIMIT)
                try:
                    data = os.read(child.stdout.fileno(), 65536)
                except BlockingIOError:
                    time.sleep(0.02)
                    continue
                if not data:
                    break
                total += len(data)
                require(total <= 64 * 1024 * 1024)
                archive.write(data)
            child.wait(timeout=min(2, max(0.001, deadline - time.monotonic())))
            require(child.returncode == 0 and total > 0)
            require(os.fstat(errors.fileno()).st_size < LIMIT)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            if child.stdout is not None:
                child.stdout.close()
    execute.check()


def prepare(helper) -> None:
    prepared, owned = paths()
    require(not prepared.exists() and not owned.with_suffix(".owner.json").exists())
    execute = Stage(helper, time.monotonic() + 630)
    tree = source(helper, execute, clean=True)
    with tempfile.TemporaryDirectory(
        prefix="quote-integrity-source-", dir=os.environ["RUNNER_TEMP"]
    ) as tmp:
        root = Path(tmp)
        context = root / "source"
        context.mkdir()
        archive = root / "source.tar"
        archive_source(helper, archive, execute)
        with tarfile.open(archive, mode="r:") as source_tar:
            for member in source_tar.getmembers():
                require(member.isfile() or member.isdir())
                require(not member.name.startswith("/") and ".." not in Path(member.name).parts)
            source_tar.extractall(context, filter="data")
        execute.check()
        require(
            all(
                digest(context / name) == value
                for name, value in (CANDIDATE_SHA | LOCKED_INPUT_SHA).items()
            )
        )
        dockerfile = root / "integrity-checks.Dockerfile"
        dockerfile.write_text(DOCKERFILE)
        execute(
            [
                "docker",
                "build",
                "--quiet",
                "--file",
                str(dockerfile),
                "--build-arg",
                f"SOURCE_TREE={tree}",
                "--tag",
                IMAGE_PREFIX + GROUP_KEY,
                str(context),
            ],
            timeout=570,
        )
    image = execute(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE_PREFIX + GROUP_KEY])
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None)
    require(
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
        == tree
    )
    prepared.write_text(
        json.dumps(
            {
                "commit": os.environ["GITHUB_SHA"],
                "tree": tree,
                "image": image,
                "wrapper_sha256": digest(Path(__file__)),
            }
        )
        + "\n"
    )


def prepared_state(helper, execute) -> dict:
    prepared, _ = paths()
    require(prepared.stat().st_size < LIMIT)
    value = json.loads(prepared.read_text())
    require(type(value) is dict and set(value) == {"commit", "tree", "image", "wrapper_sha256"})
    require(value["commit"] == os.environ["GITHUB_SHA"])
    require(value["wrapper_sha256"] == digest(Path(__file__)))
    require(
        type(value["image"]) is str
        and re.fullmatch(r"sha256:[0-9a-f]{64}", value["image"]) is not None
    )
    require(value["tree"] == source(helper, execute, clean=False))
    require(
        execute(
            [
                "docker",
                "image",
                "inspect",
                "--format",
                '{{index .Config.Labels "ocwp.source-tree"}}',
                value["image"],
            ]
        )
        == value["tree"]
    )
    return value


def inspect_fixed(helper, cid: str, image: str, token: str, execute: Stage) -> None:
    # Frozen inspect makes two five-second calls with up to two seconds reap each.
    # It bypasses execute, so reserve the full 14 seconds, then check the deadline.
    execute.check(14)
    helper.inspect_owned(cid, image, token, "none")
    execute.check()
    raw = execute(
        [
            "docker",
            "inspect",
            "--format",
            "{{json .HostConfig}}|{{.Config.User}}|{{.Config.WorkingDir}}",
            cid,
        ]
    )
    host_raw, user, workdir = raw.rsplit("|", 2)
    host = json.loads(host_raw)
    require(user == "10001:10001" and workdir == "/app")
    require(host["NanoCpus"] == 1_000_000_000 and host["Memory"] == 536870912)
    require(host["MemorySwap"] == 536870912 and host["PidsLimit"] == 64)
    require(host["ReadonlyRootfs"] is True and host["Privileged"] is False)
    require(host["NetworkMode"] == "none" and host["CgroupnsMode"] == "private")
    require(host["CapDrop"] == ["ALL"] and not host["CapAdd"])
    require(host["SecurityOpt"] == ["no-new-privileges:true"])
    require(host["Tmpfs"] == {"/tmp": "rw,noexec,nosuid,size=64m"})
    require(not host["Binds"] and not host["Devices"] and not host["DeviceRequests"])
    require(host["LogConfig"]["Type"] == "none")
    require(host["RestartPolicy"]["Name"] == "no")


def resource_sample(helper, cid: str, execute: Stage, previous: dict | None = None) -> dict:
    value = helper.parse_probe(execute(["docker", "exec", cid, "sh", "-c", helper.PROBE]), 512, 64)
    if previous is not None:
        require(value["cpu_usec"] >= previous["cpu_usec"])
        require(value["memory_peak"] >= previous["memory_peak"])
    require(value["cpu_usec"] <= 30_000_000)
    return value


def create(
    helper, role: str, state: dict, token: str, owned: Path, execute: Stage
) -> tuple[str, dict]:
    require(role in ("canary", "worker"))
    cid = helper.identifier(
        execute(
            [
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
                "--cpus",
                "1",
                "--memory",
                "512m",
                "--memory-swap",
                "512m",
                "--pids-limit",
                "64",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--log-driver",
                "none",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--user",
                "10001:10001",
                "--workdir",
                "/app",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--entrypoint",
                "/app/.venv/bin/python",
                state["image"],
                "-c",
                "import time; time.sleep(10)"
                if role == "canary"
                else "import time; time.sleep(30)",
            ]
        )
    )
    inspect_fixed(helper, cid, state["image"], token, execute)
    execute(["docker", "start", cid])
    first = resource_sample(helper, cid, execute)
    privileges = helper.effective_privileges(cid, True, execute)
    return cid, {
        "role": role,
        "container_id": cid,
        "image_id": state["image"],
        "owner_label": token,
        "network": "none",
        "memory_max": 536870912,
        "memory_swap_max": 0,
        "cpu_max": "100000 100000",
        "pids_max": 64,
        "cgroup": "0::/",
        "events_zero": True,
        "privileges": privileges,
        "initial": first,
    }


def stop_worker(helper, cid: str, report: dict) -> None:
    # cid was validated against owner, exact immutable image and controls before start.
    # Signal this whole container before reaping the workload exec client or diagnostics.
    execute = Stage(helper, time.monotonic() + 5)
    report["cancellation"] = "unverified"
    with suppress(helper.ProofFailure):
        execute(["docker", "kill", "--signal=KILL", helper.identifier(cid)], timeout=1)
    stopped = execute(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Running}}|{{.State.Status}}|{{.State.Pid}}|{{.State.OOMKilled}}",
            cid,
        ],
        timeout=1,
    )
    require(stopped == "false|exited|0|false")
    report["cancellation"] = "whole_worker_stopped"


def client_exit_without_reaping(child: subprocess.Popen) -> int | None:
    # Linux hosted runner: observe exit without waitpid/poll consuming the child.
    # Even an unsuccessful exit is not reaped until whole-container cancellation.
    status = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if status is None:
        return None
    require(status.si_code in (os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED))
    return status.si_status if status.si_code == os.CLD_EXITED else -status.si_status


def parse_junit(raw: str) -> dict:
    # No candidate hooks or generated parameter IDs are trusted as the selector.
    require(0 < len(raw.encode("utf-8")) < LIMIT)
    require("<!DOCTYPE" not in raw.upper() and "<!ENTITY" not in raw.upper())
    root = ET.fromstring(raw)
    require(root.tag == "testsuites" and set(root.attrib) == {"name"})
    require(root.attrib["name"] == "pytest tests" and len(root) == 1)
    suite = root[0]
    require(suite.tag == "testsuite")
    require(
        set(suite.attrib)
        == {"name", "errors", "failures", "skipped", "tests", "time", "timestamp", "hostname"}
    )
    require(suite.attrib["name"] == "pytest")
    require(suite.attrib["tests"] == str(CASE_COUNT) and len(suite) == CASE_COUNT)
    require(all(suite.attrib[key] == "0" for key in ("errors", "failures", "skipped")))

    def seconds(value: str) -> float:
        require(re.fullmatch(r"[0-9]{1,2}\.[0-9]{3}", value) is not None)
        parsed = float(value)
        require(math.isfinite(parsed) and 0 <= parsed < 20)
        return parsed

    expected = [
        (SOURCE_CLASSES[path], name, suffix_limit)
        for path, cases in SELECTION
        for name, count, suffix_limit in cases
        for _ in range(count)
    ]
    observed = []
    elapsed = []
    for (classname, function, suffix_limit), case in zip(expected, suite, strict=True):
        require(case.tag == "testcase" and len(case) == 0)
        require(set(case.attrib) == {"classname", "name", "time"})
        require(case.attrib["classname"] == classname)
        name = case.attrib["name"]
        require(all(32 <= ord(char) <= 126 for char in name) and name not in observed)
        if suffix_limit:
            require(name.startswith(function + "[") and name.endswith("]"))
            suffix = name[len(function) :]
            require(len(json.dumps(suffix, ensure_ascii=True)) - 2 <= suffix_limit)
        else:
            require(name == function)
        observed.append(name)
        elapsed.append(seconds(case.attrib["time"]))
    require(all(not element.text or element.text.isspace() for element in root.iter()))
    require(all(not element.tail or element.tail.isspace() for element in root.iter()))
    require(sum(elapsed) < 20)
    return {
        "expected_counts": EXPECTED_COUNTS,
        "class_names": CLASS_NAMES,
        "observed_cases": observed,
        "tests": CASE_COUNT,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "exit_code": 0,
        "session_finished": True,
        "junit_seconds": seconds(suite.attrib["time"]),
        "test_seconds": elapsed,
    }


def reconcile(helper, owned: Path, state: dict, token: str, execute: Stage) -> list[str]:
    ids = helper.reconcile_owned(owned, execute)
    allowed = {f"/{'ocwp-quote-' + token + '-' + role}" for role in ("worker", "canary")}
    for cid in ids:
        require(execute(["docker", "inspect", "--format", "{{.Name}}", cid]) in allowed)
    recorded = [
        helper.identifier(path.read_text().strip())
        for path in owned.parent.glob(f"quote-integrity-{GROUP_KEY}-owned.*.cid")
    ]
    present = execute(["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"]).splitlines()
    for cid in present:
        helper.identifier(cid)
    require(set(recorded).intersection(present).issubset(ids))
    # Exact owner schema is fixed despite the baseline's unused db compatibility key.
    manifest = json.loads(owned.with_suffix(".owner.json").read_text())
    require(
        manifest
        == {"token": token, "images": {role: state["image"] for role in ("db", "worker", "canary")}}
    )
    return ids


def workload_output_limit() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (SPOOL_LIMIT, SPOOL_LIMIT))


def run_guard(helper) -> None:
    started = time.monotonic()
    setup = Stage(helper, started + 30)
    _, owned = paths()
    report = base_report() | {
        "phase": "setup",
        "cleanup": "unverified",
        "cancellation": "not_started",
    }
    report["result"] = {
        "expected_counts": EXPECTED_COUNTS,
        "class_names": CLASS_NAMES,
        "observed_cases": [],
        "tests": None,
        "failures": None,
        "errors": None,
        "skipped": None,
        "exit_code": None,
        "session_finished": False,
    }
    worker = None
    child = None
    state = None
    token = None
    try:
        state = prepared_state(helper, setup)
        source(helper, setup, clean=True)
        report.update({"tree": state["tree"], "image_id": state["image"]})
        require(not owned.with_suffix(".owner.json").exists())
        token = uuid4().hex
        # The db key is required by the unchanged baseline parser. No DB is created.
        owned.with_suffix(".owner.json").write_text(
            json.dumps(
                {
                    "token": token,
                    "images": {role: state["image"] for role in ("db", "worker", "canary")},
                }
            )
            + "\n"
        )
        canary, identity = create(helper, "canary", state, token, owned, setup)
        report["identities"] = [identity]
        canary_after = helper.cancellation_canary(canary, setup)
        setup.check()
        require(canary_after["cpu_usec"] >= identity["initial"]["cpu_usec"])
        require(canary_after["memory_peak"] >= identity["initial"]["memory_peak"])
        require(canary_after["cpu_usec"] <= 10_000_000)
        report["canary_final"] = canary_after
        report["canary"] = "three_generations_survived_client_kill_then_verified_absent"
        worker_started = time.monotonic()
        worker, identity = create(helper, "worker", state, token, owned, setup)
        report["identities"].append(identity)
        setup.check()
        report["setup_seconds"] = time.monotonic() - started
        report["phase"] = "fixed_group"
        previous = identity["initial"]
        worker_deadline = worker_started + 30
        batch_started = time.monotonic()
        batch_deadline = min(batch_started + 20, worker_deadline)
        workload = Stage(helper, batch_deadline)
        cancellation_attempted = False
        with tempfile.TemporaryFile() as output:
            try:
                child = subprocess.Popen(
                    ["docker", "exec", worker, *PYTEST],
                    stdout=output,
                    stderr=output,
                    start_new_session=True,
                    preexec_fn=workload_output_limit,
                )
                next_probe = batch_started
                exit_code = client_exit_without_reaping(child)
                while exit_code is None:
                    workload.check()
                    require(os.fstat(output.fileno()).st_size < SPOOL_LIMIT)
                    if time.monotonic() >= next_probe:
                        previous = resource_sample(helper, worker, workload, previous)
                        require(
                            previous["cpu_usec"] - identity["initial"]["cpu_usec"] <= 20_000_000
                        )
                        next_probe = time.monotonic() + 0.25
                    time.sleep(0.02)
                    exit_code = client_exit_without_reaping(child)
                report["exit_code"] = exit_code
                workload.check()
                require(exit_code == 0 and os.fstat(output.fileno()).st_size < SPOOL_LIMIT)
                report["workload_seconds"] = time.monotonic() - batch_started
                report["phase"] = "final_read"
                final_read = Stage(helper, min(time.monotonic() + 5, worker_deadline))
                # Parse only bounded all-pass XML before stopping the worker.
                # Any failure output is read locally only after stop and client reap.
                raw = final_read(
                    [
                        "docker",
                        "exec",
                        worker,
                        "/app/.venv/bin/python",
                        "-c",
                        "from pathlib import Path; import sys; "
                        f"data=Path({JUNIT_PATH!r}).open('rb').read({LIMIT}); "
                        f"sys.exit(2) if len(data)>={LIMIT} else sys.stdout.buffer.write(data)",
                    ]
                )
                report["result"] = parse_junit(raw)
                previous = resource_sample(helper, worker, final_read, previous)
                final_read.check()
                require(previous["cpu_usec"] + canary_after["cpu_usec"] <= 40_000_000)
                require(previous["cpu_usec"] - identity["initial"]["cpu_usec"] <= 20_000_000)
                report["worker_final"] = previous
                report["phase"] = "termination"
                cancellation_attempted = True
                stop_worker(helper, worker, report)
                require(time.monotonic() < worker_deadline)
                report["worker_lifetime_seconds"] = time.monotonic() - worker_started
                report["status"] = "fixed_group_passed_pending_cleanup"
            finally:
                # On failure/expiry, cancel whole-worker descendants first. Never use
                # killing the docker exec client as evidence that descendants stopped.
                if not cancellation_attempted:
                    cancellation_attempted = True
                    try:
                        stop_worker(helper, worker, report)
                    except (helper.ProofFailure, Refusal, OSError, ValueError):
                        report["cancellation"] = "unverified"
                if child is not None:
                    try:
                        if child.poll() is None:
                            os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        report["client_reap"] = "unverified"
                    else:
                        report["client_reap"] = "bounded_two_seconds"
                if child is not None:
                    report["exit_code"] = child.returncode
                if (
                    report["status"] != "fixed_group_passed_pending_cleanup"
                    and report.get("cancellation") == "whole_worker_stopped"
                    and report.get("client_reap") == "bounded_two_seconds"
                ):
                    size = os.fstat(output.fileno()).st_size
                    output.seek(0)
                    captured = output.read(SPOOL_LIMIT)
                    diagnostic = ROOT / "artifacts" / f"quote-integrity-{GROUP_KEY}-diagnostic.txt"
                    diagnostic.parent.mkdir(exist_ok=True)
                    diagnostic.write_bytes(captured)
                    report["diagnostic"] = {
                        "path": diagnostic.name,
                        "output_bytes": len(captured),
                        "spool_bytes": size,
                        "output_truncated": size >= SPOOL_LIMIT,
                        "limit_bytes": SPOOL_LIMIT,
                    }
    except (helper.ProofFailure, Refusal, OSError, ValueError, KeyError, ET.ParseError):
        report["status"] = "failed"
    finally:
        report["failed_phase"] = report["phase"] if report["status"] == "failed" else None
        report["phase"] = "cleanup"
        cleanup = Stage(helper, time.monotonic() + 35)
        try:
            if state is not None and token is not None:
                ids = reconcile(helper, owned, state, token, cleanup)
                helper.remove_owned(ids, cleanup)
            else:
                require(not owned.with_suffix(".owner.json").exists())
                require(not list(owned.parent.glob(f"quote-integrity-{GROUP_KEY}-owned.*.cid")))
                for cid in cleanup(
                    ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"]
                ).splitlines():
                    helper.identifier(cid)
            cleanup.check()
            report["cleanup"] = "verified_absent"
        except (helper.ProofFailure, Refusal, OSError, ValueError, KeyError):
            report["cleanup"] = "unverified"
            report["status"] = "failed"
        if report["status"] == "fixed_group_passed_pending_cleanup":
            if (
                report["cancellation"] == "whole_worker_stopped"
                and report.get("client_reap") == "bounded_two_seconds"
            ):
                report["status"] = "fixed_group_passed_not_full_integration_or_activation"
            else:
                report["status"] = "failed"
        report["elapsed_seconds"] = time.monotonic() - started
        write_report(f"quote-integrity-{GROUP_KEY}.json", report)
    require(report["status"] == "fixed_group_passed_not_full_integration_or_activation")


def independent_cleanup(helper) -> None:
    report = base_report() | {"cleanup": "unverified"}
    execute = Stage(helper, time.monotonic() + 55)
    _, owned = paths()
    try:
        if owned.with_suffix(".owner.json").exists():
            state = prepared_state(helper, execute)
            manifest = json.loads(owned.with_suffix(".owner.json").read_text())
            token = manifest["token"]
            require(type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token) is not None)
            ids = reconcile(helper, owned, state, token, execute)
            helper.remove_owned(ids, execute)
        else:
            require(not list(owned.parent.glob(f"quote-integrity-{GROUP_KEY}-owned.*.cid")))
            for cid in execute(
                ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"]
            ).splitlines():
                helper.identifier(cid)
        execute.check()
        report["cleanup"] = "verified_absent"
        report["status"] = "independent_cleanup_passed"
    except (helper.ProofFailure, Refusal, OSError, ValueError, KeyError):
        pass
    finally:
        write_report(f"quote-integrity-{GROUP_KEY}-independent-cleanup.json", report)
    require(report["cleanup"] == "verified_absent")


def main() -> None:
    require(len(sys.argv) == 2 and sys.argv[1] in ("prepare", "run", "cleanup"))
    gate()
    helper = load_baseline()

    def interrupted(_signum, _frame):
        raise Refusal("interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    {"prepare": prepare, "run": run_guard, "cleanup": independent_cleanup}[sys.argv[1]](helper)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never leak candidate-controlled output, exception text or tracebacks.
        raise SystemExit("Fixed integrity group unqualified; inspect bounded evidence") from None
