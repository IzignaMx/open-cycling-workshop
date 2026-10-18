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
        "bff6f743f5e0c8959f4c00476514a42edf4931144b0207eb1675ae2f366be5fa"
    ),
    "tests/operations/test_quote_integrity_static_contracts.py": (
        "152c2ab380b631c6c41f6f3c29669a4fa6777ee616a5ce88faca8066dc6c68ed"
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
        "a6798d59dd1e11721a11e31d24e1bfbfbdef483bc08e5253d590d9096338835d"
    ),
    "tests/operations/test_quote_integrity_selection.py": (
        "07c8f1bc4dbfc9eb0083c348195f487534a11f09708661b7dff2b689a22d39e5"
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
        "d3abe336efcf23a333a46f8475db8d70ed946e95a06b9093e859de3dc35293f2"
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
    ".github/workflows/quote-semantic-format-checks.yml": (
        "353f4c0a5f178d1ecb00314ecb43c4cef9c92727624ffbcfda724f6a6ef2eda3"
    ),
    ".github/workflows/quote-existing-integration-checks.yml": (
        "754798da585c598a6c98ce615d412dd108490ac0debaf49581775a924211c682"
    ),
    ".github/workflows/quote-oracle-adapter-checks.yml": (
        "11cc3ec404f87a6e6509d70b2c5cc97c4cfb5a627423f8fb7b05668891d0d897"
    ),
    "services/platform/tests/branding/test_profile_migration.py": (
        "600410d91d8854f12c55231bf7678a95d7589a1dacfd0deaefa1862ed53d5f50"
    ),
    "services/platform/tests/events/test_outbox.py": (
        "ff368c15ad67c1efdd3a74d6452ac048832bba80568f745f43d2b6d476f2b30f"
    ),
    "services/platform/tests/identity/test_administration_postgres.py": (
        "f83323a05951d45d7c8450d08012c79006dd5a1de9bb980848d9e6fd23faf453"
    ),
    "services/platform/tests/identity/test_cutover_migration.py": (
        "46bb5b4892605bce9d0177fca82f4d809b61ea54766d1710051d9dad5a20d142"
    ),
    "services/platform/tests/ops/test_cutover_cli.py": (
        "a924e441518e7b130e3bcf83d3cf2a807931c5123034cd9b4fcfb0a360638493"
    ),
    "services/platform/tests/quotes/test_quote_effect_metadata.py": (
        "a761699b2bf1e68fd18d8888a79717e2e9666fd0d1ed65e0b8f02bea46306157"
    ),
    "services/platform/tests/quotes/test_quote_history_byte_reuse.py": (
        "3e7b2218dcada35471980e99d3286c857d572c6ef9d5267009a1f0116fdaf9ba"
    ),
    "services/platform/tests/quotes/test_quote_reads.py": (
        "4e37af395a2359c7c67127058925319011d3c97e8681fd51843239445a6c9aae"
    ),
    "services/platform/tests/quotes/test_quote_reconstruction.py": (
        "0ff237606ffd5b7d24e89968e8f1a0cb43171c81c85098a8fe4433c2c6a3309b"
    ),
    "services/platform/tests/quotes/test_quote_repository.py": (
        "87fdc1b03aa50d6db3050d1fdafd837ad3322eaa8d0b17b2c974ea9fc5b9b30a"
    ),
    "services/platform/tests/quotes/test_quote_repository_postgres.py": (
        "f8be5679ceeb1879e3af245553401adbcbd68dd0bf3c5b1e86050037d919f57d"
    ),
    "services/platform/tests/quotes/test_quote_result_codec_once.py": (
        "2a2ba6b2d303d9af700ec7397a365ba6f950c78e97d06bf34811b1a3c7a4f3a7"
    ),
    "services/platform/tests/quotes/test_quote_schema.py": (
        "bd49accbfebf5f113277382a952060a777140c4f20ef493cb5578b424843285c"
    ),
    "services/platform/tests/quotes/test_quote_single_pass.py": (
        "a60cbfa30095c7869e3436013aac9d15b520f1ca38dac313b2ebfdfa8be62b79"
    ),
    "services/platform/tests/service_orders/test_order_sync_service.py": (
        "9a56f33c030427f996d32d7e1494c97d4b3f952628b513b94ff8017daf78bb61"
    ),
    "services/platform/tests/sync/test_rest_change_feed.py": (
        "aa188d7c23a3d17ac9787ae89eba8864b047f2302f345e21d31ed1f0a63ab924"
    ),
    "services/platform/tests/sync/test_sync_service.py": (
        "0b069ad9dfd3dd62abfdb4ab17b3603e10fe0759130e7570b884c60f6fb4345d"
    ),
    ".github/workflows/quote-full-python-mock-static.yml": (
        "1179950616d30f852766bff7a8f513f2d807881c4a722e4f37f5746e4fc4b087"
    ),
    ".github/workflows/ci.yml": "894ba53c299c205cd53d427c19c3fbea6fc2fa0b5dd5b143a649038d8d70512c",
    "scripts/ci/verify_v01.py": "e65603f2aa317323d243d1c39ac3f69dba9ea6d271485faf6cb9ca3be0fa38e9",
    "tests/operations/test_quote_capacity_micro.py": (
        "3864e984551af2094540c33faca484ead724f2b92efd14cb391f17abf5341eb9"
    ),
    "tests/ci/test_verify_v01.py": (
        "649e60ebccc33c02a38ed464697b8007ff65f1deef585177e79195614566f10b"
    ),
    "tests/operations/test_ci_contract.py": (
        "d0415cf03d8b206ba984aedb5fe900158ec2b6917727b65b898e3819cdb445cd"
    ),
    "tests/repository/test_repository_contract.py": (
        "d357c050cde8fa86872aec57bb85acfebee1bd2bfab5e5ff0fa35506e40fe0aa"
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
FULL_CHECKS_BRANCH = "refs/heads/codex/quote-full-python-mock-static"
FULL_CHECKS_WORKFLOW = ".github/workflows/quote-full-python-mock-static.yml"
FULL_CHECKS_GROUPS = ("aggregate_mocks214", "static6")
INTENDED_SOURCE = {
    "intended_source_base": "dea1a661c81fee3aa1ce907f095a1709edb82d6e",
    "intended_source_tree": "d3bde4a9526a0a1c40cc95646c6fcdd7f438fb6f",
    "intended_source_manifest_sha256": (
        "b7a10c7c2416cae95d93136ef3865a8e2b085eae6ceb6cbee363819f7cb6d3e3"
    ),
    "preserved_functional_reference": "b353c4b4d364ebfbcd1dc98134017c8bc6aae609",
}
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
SEMANTIC_FORMAT_BRANCH = "refs/heads/codex/quote-semantic-format-checks"
SEMANTIC_FORMAT_WORKFLOW = ".github/workflows/quote-semantic-format-checks.yml"
EXISTING_BRANCH = "refs/heads/codex/quote-existing-integration-checks"
EXISTING_WORKFLOW = ".github/workflows/quote-existing-integration-checks.yml"
ORACLE_BRANCH = "refs/heads/codex/quote-oracle-adapter-checks"
ORACLE_WORKFLOW = ".github/workflows/quote-oracle-adapter-checks.yml"
IMAGE_PREFIX = "ocwp-quote-integrity-"
SERVICE_PATH = "services/platform/tests/quotes/test_quote_application_service.py"
ATOMIC_PATH = "services/platform/tests/quotes/test_quote_atomic_effects.py"
RESPONSE_PATH = "services/platform/tests/quotes/test_quote_command_response.py"
STATIC_PATH = "tests/operations/test_quote_integrity_static_contracts.py"
SELECTION_PATH = "tests/operations/test_quote_integrity_selection.py"
SOURCE_CLASSES = {
    "tests/operations/test_quote_capacity_micro.py": "tests.operations.test_quote_capacity_micro",
    "tests/ci/test_verify_v01.py": "tests.ci.test_verify_v01",
    "tests/operations/test_ci_contract.py": "tests.operations.test_ci_contract",
    "tests/repository/test_repository_contract.py": "tests.repository.test_repository_contract",
    SERVICE_PATH: "services.platform.tests.quotes.test_quote_application_service",
    ATOMIC_PATH: "services.platform.tests.quotes.test_quote_atomic_effects",
    RESPONSE_PATH: "services.platform.tests.quotes.test_quote_command_response",
    STATIC_PATH: "tests.operations.test_quote_integrity_static_contracts",
    SELECTION_PATH: "tests.operations.test_quote_integrity_selection",
    "services/platform/tests/branding/test_profile_migration.py": (
        "services.platform.tests.branding.test_profile_migration"
    ),
    "services/platform/tests/events/test_outbox.py": "services.platform.tests.events.test_outbox",
    "services/platform/tests/identity/test_cutover_migration.py": (
        "services.platform.tests.identity.test_cutover_migration"
    ),
    "services/platform/tests/ops/test_cutover_cli.py": (
        "services.platform.tests.ops.test_cutover_cli"
    ),
    "services/platform/tests/quotes/test_quote_effect_metadata.py": (
        "services.platform.tests.quotes.test_quote_effect_metadata"
    ),
    "services/platform/tests/quotes/test_quote_history_byte_reuse.py": (
        "services.platform.tests.quotes.test_quote_history_byte_reuse"
    ),
    "services/platform/tests/quotes/test_quote_reads.py": (
        "services.platform.tests.quotes.test_quote_reads"
    ),
    "services/platform/tests/quotes/test_quote_reconstruction.py": (
        "services.platform.tests.quotes.test_quote_reconstruction"
    ),
    "services/platform/tests/quotes/test_quote_repository.py": (
        "services.platform.tests.quotes.test_quote_repository"
    ),
    "services/platform/tests/quotes/test_quote_result_codec_once.py": (
        "services.platform.tests.quotes.test_quote_result_codec_once"
    ),
    "services/platform/tests/quotes/test_quote_schema.py": (
        "services.platform.tests.quotes.test_quote_schema"
    ),
    "services/platform/tests/quotes/test_quote_single_pass.py": (
        "services.platform.tests.quotes.test_quote_single_pass"
    ),
    "services/platform/tests/service_orders/test_order_sync_service.py": (
        "services.platform.tests.service_orders.test_order_sync_service"
    ),
    "services/platform/tests/sync/test_prepared_order_change.py": (
        "services.platform.tests.sync.test_prepared_order_change"
    ),
    "services/platform/tests/sync/test_rest_change_feed.py": (
        "services.platform.tests.sync.test_rest_change_feed"
    ),
    "services/platform/tests/sync/test_sync_service.py": (
        "services.platform.tests.sync.test_sync_service"
    ),
}
# Complete fixed functions: count and maximum JSON-encoded parameter suffix bytes.
GROUPS = {
    "aggregate_mocks214": (
        (
            "tests/operations/test_quote_capacity_micro.py",
            (
                ("test_exact_enforced_limits_and_numeric_counters", 1, 0),
                ("test_full_route_stops_worker_before_reaping_failed_exec_client", 1, 0),
                ("test_full_route_unverified_stop_stays_failure_even_after_client_hygiene", 1, 0),
                ("test_full_diagnostic_retains_only_the_bounded_host_spool", 1, 0),
                (
                    "test_full_record_capture_accepts_only_fixed_names_and_typed_pending_marker",
                    1,
                    0,
                ),
                ("test_full_stop_requires_exact_terminal_state", 4, 16),
                ("test_full_boundary_has_fixed_memory_shm_and_only_declared_scratch", 6, 24),
                ("test_full_scratch_uses_kernel_bytes_inodes_permissions_and_flags", 10, 24),
                ("test_full_preflight_failure_has_no_candidate_launch_and_cannot_qualify", 1, 0),
                ("test_independent_absence_cannot_promote_failed_or_missing_proof", 1, 0),
                ("test_full_supervisor_terminal_paths_require_stop_and_both_cleanups", 5, 16),
                ("test_missing_or_wrong_containment_fails_closed", 9, 128),
                ("test_cpu_counters_cannot_go_backwards_or_exceed_budget", 1, 0),
                ("test_cleanup_failure_is_not_absence", 1, 0),
                ("test_cleanup_requires_successful_listing_and_absence", 1, 0),
                ("test_cleanup_success_reverses_creation_order", 1, 0),
                ("test_invalid_container_id_never_reaches_docker", 1, 0),
                ("test_failed_preflight_never_launches_specimen", 1, 0),
                ("test_bounded_client_rejects_output_overflow", 1, 0),
                ("test_bounded_client_terminates_sleeping_process_group", 1, 0),
                ("test_actual_shell_probe_delimiters", 1, 0),
                ("test_closed_micro_report_rejects_raw_proof_and_nonfinite_timings", 1, 0),
                ("test_supervisor_success_and_terminal_failures_are_closed", 14, 64),
                ("test_effective_privileges_fail_closed", 5, 128),
                ("test_effective_privileges_are_observed", 1, 0),
                ("test_invalid_ownership_manifest_never_calls_docker", 5, 16),
                ("test_owner_discovery_checks_image_and_label_before_removal", 1, 0),
                ("test_canary_kills_client_then_requires_descendant_chain_and_removal", 5, 96),
                ("test_source_status_never_refreshes_large_index", 1, 0),
                ("test_failed_client_retains_only_numeric_returncode", 1, 0),
                ("test_source_failure_records_closed_stage_and_returncode", 1, 0),
                ("test_fixed_feasibility_schema_accepts_only_reviewed_specimen", 1, 0),
                ("test_fixed_feasibility_metrics_fail_closed", 6, 64),
                ("test_record_failure_diagnostic_is_closed", 1, 0),
                ("test_record_failure_diagnostic_refuses_unclosed_fields", 6, 16),
            ),
        ),
        (
            "tests/ci/test_verify_v01.py",
            (
                ("test_probe_tool_requires_the_executable_to_run_successfully", 1, 0),
                (
                    "test_browser_runtime_checks_are_explicitly_blocked_"
                    "without_pnpm_or_e2e_database",
                    1,
                    0,
                ),
                ("test_indexeddb_runtime_check_preserves_environment_blockers", 1, 0),
                ("test_static_analysis_checks_run_available_python_and_frontend_tools", 1, 0),
                (
                    "test_static_analysis_checks_report_blocked_groups_without_executing_commands",
                    1,
                    0,
                ),
                ("test_qualification_metadata_identifies_commit_and_runtime", 1, 0),
                (
                    "test_postgresql_runtime_checks_block_when_driver_or_database_is_unavailable",
                    1,
                    0,
                ),
                ("test_postgresql_runtime_checks_execute_integration_when_ready", 1, 0),
                (
                    "test_qualifier_browser_evidence_is_isolated_even_with_inherited_direct_paths",
                    1,
                    0,
                ),
                ("test_qualifier_requires_real_pinned_old_build_before_browser_setup", 1, 0),
                ("test_full_python_receipt_consumes_all_three_controls_once", 1, 0),
                ("test_full_python_receipt_rejects_stale_or_wrong_context", 15, 96),
                ("test_full_python_receipt_requires_inner_source_identity", 2, 16),
                ("test_full_python_receipt_requires_every_large_restore_and_database_case", 11, 40),
                ("test_full_python_receipt_requires_unique_bijective_inventory", 5, 24),
                ("test_full_python_exit_zero_alone_never_proves_completion", 8, 32),
                ("test_full_python_phase_duration_is_strict_bounded_microseconds", 6, 16),
                ("test_full_python_fail_fast_tail_is_unrun_not_passed", 2, 16),
                ("test_full_python_restore_dependency_skips_are_never_allowed", 6, 40),
                ("test_full_python_exact_skip_ledger_rejects_replacement_or_wrong_phase", 1, 0),
                (
                    "test_full_python_classifier_uses_complete_typed_parameters_"
                    "not_nodeid_spelling",
                    1,
                    0,
                ),
                ("test_full_python_containment_is_required_for_success", 16, 32),
                ("test_full_python_both_cleanup_proofs_are_required", 2, 24),
                ("test_full_python_finalizer_can_only_accept_exact_provisional_success", 1, 0),
                ("test_full_python_count_reconciliation_rejects_booleans_and_wrong_totals", 4, 24),
                (
                    "test_full_python_reader_rejects_duplicate_nonfinite_truncated_or_wrong_json",
                    6,
                    24,
                ),
                ("test_full_python_reader_and_writer_enforce_strict_size_and_regular_files", 1, 0),
                ("test_full_python_missing_failed_and_unrun_receipts_fail_all_controls", 1, 0),
                ("test_full_python_protocol_size_is_bounded_at_node_ceiling", 1, 0),
                ("test_full_python_plugin_is_inert_outside_contained_mode", 1, 0),
                ("test_full_python_plugin_seals_hashed_inventory_before_reports", 1, 0),
                ("test_full_python_plugin_normalizes_only_exact_skip_reason", 2, 40),
                ("test_full_python_plugin_rejects_out_of_order_and_duplicate_reports", 1, 0),
                ("test_full_python_expected_context_uses_checkout_and_job_outputs", 1, 0),
                ("test_full_python_aggregate_never_falls_back_and_allow_blocked_cannot_pass", 2, 8),
            ),
        ),
        (
            "tests/operations/test_ci_contract.py",
            (
                ("test_ci_workflow_runs_repository_backend_frontend_and_contract_checks", 1, 0),
                ("test_ci_supports_manual_dispatch_and_exports_generated_lockfiles", 1, 0),
                ("test_direct_browser_evidence_upload_immediately_follows_e2e", 1, 0),
            ),
        ),
        (
            "tests/repository/test_repository_contract.py",
            (
                ("test_ci_and_v01_verifier_execute_api_client_behavior_tests", 1, 0),
                ("test_root_scripts_and_ci_use_normative_uv_and_static_quality_gates", 1, 0),
                ("test_ci_postgres_service_healthcheck_matches_the_e2e_database_name", 1, 0),
                ("test_ci_publishes_a_v01_qualification_artifact", 1, 0),
            ),
        ),
    ),
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
    "sqlite_repository24": (
        (
            "services/platform/tests/quotes/test_quote_repository.py",
            (
                ("test_create_load_and_explicit_caller_commit", 1, 64),
                (
                    "test_restart_exact_replay_returns_original_receipt_and_current_projection",
                    1,
                    64,
                ),
                ("test_operation_id_reuse_with_changed_semantics_conflicts", 4, 64),
                ("test_stale_or_missing_lineage_has_no_effect", 3, 64),
                ("test_single_lineage_and_three_part_cas", 1, 64),
                ("test_correction_withdrawal_retains_all_evidence_without_order_effects", 1, 64),
                ("test_admission_required_and_transaction_scoped_even_on_replay", 1, 64),
                ("test_narrow_actor_location_scope_and_wrong_order_refused", 1, 64),
                ("test_new_part_reference_is_scoped_but_replay_keeps_original_snapshot", 1, 64),
                ("test_published_outbox_delivery_metadata_does_not_change_receipt", 1, 64),
                ("test_corrupt_outbox_content_fails_closed", 1, 64),
                (
                    "test_late_outbox_failure_rolls_back_entire_operation_"
                    "and_keeps_outer_transaction",
                    1,
                    64,
                ),
                ("test_new_revision_and_correction_cannot_precede_history", 1, 64),
                ("test_late_expiry_rolls_back_new_operation", 1, 64),
                ("test_load_rechecks_admission_after_waits_and_reconstruction", 2, 64),
                ("test_outbox_decision_contract_has_distinct_delivery_and_domain_identity", 1, 64),
                ("test_receipt_collisions_outside_order_scope_do_not_read_foreign_proof", 2, 64),
            ),
        ),
    ),
    "sqlite_reconstruction_corrupt37": (
        (
            "services/platform/tests/quotes/test_quote_reconstruction.py",
            (("test_corrupt_result_or_receipt_is_rejected", 37, 96),),
        ),
    ),
    "sqlite_reconstruction_other20": (
        (
            "services/platform/tests/quotes/test_quote_reconstruction.py",
            (
                ("test_complete_rows_reconstruct_in_operation_order", 1, 48),
                ("test_missing_financial_evidence_or_receipt_rows_are_rejected", 6, 48),
                ("test_duplicate_financial_evidence_or_receipt_rows_are_rejected", 6, 48),
                ("test_reordered_operations_are_not_sorted_into_a_different_history", 1, 48),
                ("test_altered_proof_does_not_rewrite_financial_history", 1, 48),
                ("test_unknown_proof_field_and_bool_result_are_refused", 1, 48),
                ("test_boolean_operation_numbers_cannot_equal_integer_receipt_fields", 4, 48),
            ),
        ),
    ),
    "sqlite_single_pass26": (
        (
            "services/platform/tests/quotes/test_quote_single_pass.py",
            (
                ("test_no_complete_prefix_advance_and_exact_old_result", 1, 64),
                ("test_corruption_rejection_matches_frozen_oracle", 7, 64),
                ("test_constant_final_constructors_and_every_operation_checked", 1, 64),
                ("test_later_revision_prefix_preconditions_cannot_be_repaired", 3, 64),
                (
                    "test_correction_updates_latest_customer_time_and_withdrawal_preserves_it",
                    1,
                    64,
                ),
                ("test_exact_and_one_byte_over_limits_match_old_path", 2, 64),
                ("test_byte_failure_and_outer_rollback_on_both_paths", 2, 64),
                ("test_oracle_and_new_formatters_are_not_shared", 2, 64),
                ("test_frozen_advance_is_independent_of_new_path", 1, 64),
                ("test_out_of_order_and_duplicate_commands_fail_closed", 4, 64),
                ("test_correction_withdrawal_revision_and_new_initial_are_per_quote", 1, 64),
                ("test_coherent_reordering_reaches_current_head_rejection", 1, 64),
            ),
        ),
    ),
    "sqlite_codec15": (
        (
            "services/platform/tests/quotes/test_quote_result_codec_once.py",
            (
                ("test_frozen_pr55_oracle_has_exact_reviewed_source_bytes", 1, 0),
                ("test_one_codec_per_result_retains_predecessor_and_final_codecs", 1, 8),
                ("test_exact_lowered_limits_and_one_byte_over_match_pr55", 2, 32),
                ("test_malformed_prefixes_keep_public_error_and_inputs", 6, 32),
                ("test_pr55_local_formatters_are_bidirectionally_independent", 2, 32),
                ("test_unicode_mixed_correction_withdrawal_revision_and_initial", 1, 8),
                ("test_corrupt_history_rejection_has_zero_database_writes", 2, 24),
            ),
        ),
    ),
    "sqlite_bytes_reads25": (
        (
            "services/platform/tests/quotes/test_quote_history_byte_reuse.py",
            (
                ("test_count_matches_canonical_array_and_exact_boundary", 3, 24),
                ("test_public_snapshot_shape_is_unchanged", 1, 0),
                ("test_locked_count_matches_operation_time_oracle_and_avoids_second_replay", 1, 8),
                ("test_candidate_byte_boundary_preserves_error_and_rows", 1, 8),
                ("test_private_and_public_reconstruction_normalize_same_errors", 5, 24),
                ("test_decision_correction_withdrawal_count_matches_joined_oracle", 1, 8),
                ("test_later_revision_does_not_replace_historical_decision_result", 1, 8),
                ("test_candidate_keeps_history_array_nesting_validation", 1, 8),
            ),
        ),
        (
            "services/platform/tests/quotes/test_quote_reads.py",
            (
                ("test_detail_preserves_immutable_financial_revision_and_current_lineage", 1, 8),
                ("test_metadata_pages_are_bounded_scoped_and_immutable", 1, 8),
                ("test_repository_validates_corruption_outside_requested_page_or_detail", 6, 128),
                ("test_load_requires_current_transaction_and_scope_before_projection", 1, 8),
                (
                    "test_decision_sequence_invalidates_cursor_without_changing_financial_revision",
                    1,
                    8,
                ),
                ("test_unicode_bytes_read_only_effects_and_incoming_principal_narrowing", 1, 8),
            ),
        ),
    ),
    "sqlite_schema_constraints21": (
        (
            "services/platform/tests/quotes/test_quote_schema.py",
            (
                ("test_financial_history_update_delete_are_refused", 10, 64),
                ("test_operation_result_proof_and_effect_completeness", 11, 32),
            ),
        ),
    ),
    "sqlite_schema_other11": (
        (
            "services/platform/tests/quotes/test_quote_schema.py",
            (
                ("test_additive_quote_migration_and_forward_only_retention", 1, 8),
                ("test_model_schema_and_migration_columns_match", 1, 8),
                ("test_downgrade_refuses_before_changes", 1, 8),
                (
                    "test_complete_order_effect_tuple_is_retained_"
                    "but_delivery_bookkeeping_can_change",
                    1,
                    8,
                ),
                ("test_sqlite_replace_cannot_erase_financial_evidence", 6, 32),
                ("test_sqlite_replace_alternate_keys_cannot_discard_other_rows", 1, 8),
            ),
        ),
    ),
    "sqlite_metadata_writer_heads21": (
        (
            "services/platform/tests/quotes/test_quote_effect_metadata.py",
            (
                ("test_empty_upgrade_has_generated_dialect_schema", 1, 8),
                ("test_seeded_upgrade_preserves_bytes_and_regenerates_counts", 1, 8),
                ("test_legacy_populated_tuple_refuses_before_any_ddl", 1, 8),
                ("test_effect_version_constraint_retains_dependencies_and_immutability", 1, 8),
                ("test_upgrade_failure_rolls_back_all_added_columns", 1, 8),
                ("test_runtime_count_verifier_accepts_fresh_metadata", 1, 8),
                ("test_sqlite_temp_shadow_refused", 8, 64),
            ),
        ),
        (
            "services/platform/tests/sync/test_prepared_order_change.py",
            (
                ("test_prepared_writer_retains_both_exact_raw_copies_and_generated_counts", 1, 8),
                ("test_prepared_inserts_are_owned_by_caller_rollback", 3, 32),
                ("test_ordinary_dictionary_writers_keep_payload_and_unbounded_contract", 1, 8),
            ),
        ),
        (
            "services/platform/tests/identity/test_cutover_migration.py",
            (
                (
                    "test_cutover_initializes_unique_canonical_incarnations_"
                    "without_changing_tenancy",
                    1,
                    8,
                ),
            ),
        ),
        (
            "services/platform/tests/branding/test_profile_migration.py",
            (("test_branding_upgrade_preserves_accounts_and_qualifies_cutover_recovery", 1, 8),),
        ),
    ),
    "generic_callers17": (
        (
            "services/platform/tests/events/test_outbox.py",
            (("test_enqueue_outbox_persists_an_unpublished_event_in_same_session", 1, 0),),
        ),
        (
            "services/platform/tests/sync/test_rest_change_feed.py",
            (
                ("test_rest_writes_publish_complete_projections_and_outbox_once", 1, 0),
                (
                    "test_rest_failure_after_feed_append_rolls_back_domain_feed_outbox_and_event",
                    1,
                    0,
                ),
                ("test_rest_create_feed_failure_preserves_no_partial_domain_row", 3, 32),
            ),
        ),
        (
            "services/platform/tests/service_orders/test_order_sync_service.py",
            (
                ("test_order_create_starts_at_intake_and_feeds_change_record", 1, 0),
                ("test_order_create_requires_existing_customer", 1, 0),
                ("test_order_transition_applies_and_appends_timeline_event", 1, 0),
                ("test_order_transition_refuses_payload_actor_without_trusted_context", 1, 0),
                ("test_invalid_transition_is_a_permanent_sync_conflict", 1, 0),
                ("test_order_transition_with_stale_base_version_conflicts", 1, 0),
                ("test_update_without_transition_and_without_fields_is_rejected", 1, 0),
            ),
        ),
        (
            "services/platform/tests/sync/test_sync_service.py",
            (
                ("test_duplicate_mutation_id_is_applied_exactly_once", 1, 0),
                ("test_change_feed_cursor_is_incremental_and_tenant_scoped", 1, 0),
                ("test_customer_mutation_writes_outbox_event_in_same_transaction", 1, 0),
                ("test_workshop_core_entities_feed_entries_and_scope_isolation", 1, 0),
            ),
        ),
    ),
    "cutover_basics17": (
        (
            "services/platform/tests/ops/test_cutover_cli.py",
            (
                ("test_activation_is_explicit_enabled_and_idempotent_with_honest_audit", 4, 8),
                ("test_recovery_requires_active_floor_and_exact_precondition", 4, 8),
                ("test_recovery_audit_failure_rolls_back_rotation", 4, 8),
                ("test_cli_reports_status_and_requires_recovery_precondition", 4, 8),
                ("test_cutover_cli_refuses_fallback_database_configuration", 1, 0),
            ),
        ),
    ),
    "cutover_preconditions16": (
        (
            "services/platform/tests/ops/test_cutover_cli.py",
            (("test_recovery_rejects_noncanonical_precondition_without_changes", 16, 64),),
        ),
    ),
    "cutover_schema20": (
        (
            "services/platform/tests/ops/test_cutover_cli.py",
            (("test_operator_refuses_unqualified_schema_without_effects", 20, 24),),
        ),
    ),
    "cutover_cas_audit16": (
        (
            "services/platform/tests/ops/test_cutover_cli.py",
            (
                ("test_recovery_uuid_collision_refuses_without_a_second_audit", 4, 8),
                ("test_activation_audit_failure_rolls_back_floor", 4, 8),
                (
                    "test_activation_optional_incarnation_cas_is_checked_before_floor_or_audit",
                    4,
                    8,
                ),
                ("test_activation_cas_refuses_target_changed_after_snapshot_inspection", 4, 8),
            ),
        ),
    ),
}
GROUP_COUNTS = {
    "aggregate_mocks214": 214,
    "service27": 27,
    "atomic18_corruption": 18,
    "atomic18_other": 18,
    "response50": 50,
    "response64": 64,
    "static6": 6,
    "selection_static12": 12,
    "sqlite_repository24": 24,
    "sqlite_reconstruction_corrupt37": 37,
    "sqlite_reconstruction_other20": 20,
    "sqlite_single_pass26": 26,
    "sqlite_codec15": 15,
    "sqlite_bytes_reads25": 25,
    "sqlite_schema_constraints21": 21,
    "sqlite_schema_other11": 11,
    "sqlite_metadata_writer_heads21": 21,
    "generic_callers17": 17,
    "cutover_basics17": 17,
    "cutover_preconditions16": 16,
    "cutover_schema20": 20,
    "cutover_cas_audit16": 16,
}
EXISTING_GROUPS = (
    "sqlite_repository24",
    "sqlite_reconstruction_corrupt37",
    "sqlite_reconstruction_other20",
    "sqlite_single_pass26",
    "sqlite_codec15",
    "sqlite_bytes_reads25",
    "sqlite_schema_constraints21",
    "sqlite_schema_other11",
    "sqlite_metadata_writer_heads21",
    "generic_callers17",
    "cutover_basics17",
    "cutover_preconditions16",
    "cutover_schema20",
    "cutover_cas_audit16",
    "selection_static12",
)
ORACLE_GROUPS = (
    "sqlite_single_pass26",
    "sqlite_codec15",
    "sqlite_bytes_reads25",
    "selection_static12",
)
SQLITE_GROUPS = (
    "sqlite_repository24",
    "sqlite_reconstruction_corrupt37",
    "sqlite_reconstruction_other20",
    "sqlite_single_pass26",
    "sqlite_codec15",
    "sqlite_bytes_reads25",
    "sqlite_schema_constraints21",
    "sqlite_schema_other11",
    "sqlite_metadata_writer_heads21",
)
GROUP_KEY = os.environ.get("OCWP_INTEGRITY_GROUP", "")
SELECTION = GROUPS.get(GROUP_KEY, ())
NODES = tuple(f"{path}::{name}" for path, cases in SELECTION for name, _, _ in cases)
EXPECTED_COUNTS = {name: count for _, cases in SELECTION for name, count, _ in cases}
CLASS_NAMES = [SOURCE_CLASSES[path] for path, _ in SELECTION]
CASE_COUNT = GROUP_COUNTS.get(GROUP_KEY, 0)
RECORD_LIMIT = 64 * 1024 if GROUP_KEY == "aggregate_mocks214" else LIMIT
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
    *(["-k", "not postgres"] if GROUP_KEY in SQLITE_GROUPS else []),
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
    elif os.environ.get("GITHUB_REF") == SEMANTIC_FORMAT_BRANCH:
        require(GROUP_KEY == "static6")
        branch, workflow = SEMANTIC_FORMAT_BRANCH, SEMANTIC_FORMAT_WORKFLOW
    elif os.environ.get("GITHUB_REF") == SEMANTIC_BRANCH:
        require(GROUP_KEY == "selection_static12")
        branch, workflow = SEMANTIC_BRANCH, SEMANTIC_WORKFLOW
    elif os.environ.get("GITHUB_REF") == EXISTING_BRANCH:
        require(GROUP_KEY in EXISTING_GROUPS)
        branch, workflow = EXISTING_BRANCH, EXISTING_WORKFLOW
    elif os.environ.get("GITHUB_REF") == ORACLE_BRANCH:
        require(GROUP_KEY in ORACLE_GROUPS)
        branch, workflow = ORACLE_BRANCH, ORACLE_WORKFLOW
    elif os.environ.get("GITHUB_REF") == FULL_CHECKS_BRANCH:
        require(GROUP_KEY in FULL_CHECKS_GROUPS)
        branch, workflow = FULL_CHECKS_BRANCH, FULL_CHECKS_WORKFLOW
    else:
        require(GROUP_KEY not in EXISTING_GROUPS and GROUP_KEY != "aggregate_mocks214")
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
        **(INTENDED_SOURCE if os.environ.get("GITHUB_REF") == FULL_CHECKS_BRANCH else {}),
    }


def write_report(name: str, value: dict) -> None:
    raw = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
    require(len(raw.encode("utf-8")) < RECORD_LIMIT)
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
    require(0 < len(raw.encode("utf-8")) < RECORD_LIMIT)
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
                # Only this fixed larger inventory uses the reviewed 64-KiB reader.
                # Restore the frozen helper's 16-KiB control limit before any parser,
                # resource observation, cancellation or cleanup call, including errors.
                require(helper.LIMIT == LIMIT)
                helper.LIMIT = RECORD_LIMIT
                try:
                    raw = final_read(
                        [
                            "docker",
                            "exec",
                            worker,
                            "/app/.venv/bin/python",
                            "-c",
                            "from pathlib import Path; import sys; "
                            f"data=Path({JUNIT_PATH!r}).open('rb').read({RECORD_LIMIT}); "
                            f"sys.exit(2) if len(data)>={RECORD_LIMIT} "
                            "else sys.stdout.buffer.write(data)",
                        ]
                    )
                finally:
                    helper.LIMIT = LIMIT
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
