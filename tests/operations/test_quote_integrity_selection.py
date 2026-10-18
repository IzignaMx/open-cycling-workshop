"""Six synthetic selection regressions for the fixed contained integrity groups.

Source preparation is not execution evidence. These hooks and receipts launch no
subprocess, open no database and never run the selected product tests themselves.
"""

import importlib.util
import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
METADATA = "services/platform/tests/quotes/test_quote_effect_metadata.py"
BRIDGE = "services/platform/tests/quotes/test_quote_application_service_postgres.py"
WRITER = "services/platform/tests/sync/test_prepared_order_change.py"
BOUNDED = "services/platform/tests/quotes/test_quote_bounded_effects_postgres.py"
DECISIONS = "services/platform/tests/quotes/test_quote_service_decisions_postgres.py"
PAYLOAD = "services/platform/tests/quotes/test_quote_payload_integrity_postgres.py"
ATOMICITY = "services/platform/tests/quotes/test_quote_service_atomicity_postgres.py"
RACES = "services/platform/tests/quotes/test_quote_service_races_postgres.py"
SCHEMA = "services/platform/tests/quotes/test_quote_schema.py"
REPOSITORY = "services/platform/tests/quotes/test_quote_repository_postgres.py"
SETUP_IDENTITY_GROUPS = {
    "service_bridge",
    "decision7",
    "mismatch_a7",
    "mismatch_b7",
    "storage6",
    "atomic8",
    "races5",
}
MALFORMED = "test_runtime_count_verifier_refuses_malformed_postgres_metadata"
RELATIONS = "test_runtime_count_verifier_refuses_nonordinary_relations"
SHADOWS = "test_runtime_count_verifier_refuses_shadowed_generated_dependencies"
DEPENDENCIES = "test_postgres_generated_dependency_rows_are_exact"
PG_SELECTIONS = {
    "metadata_sync": (METADATA, ((MALFORMED, 7),), "not sqlite and sync_changes"),
    "metadata_outbox": (METADATA, ((MALFORMED, 7),), "not sqlite and outbox_events"),
    "metadata_relations": (
        METADATA,
        ((RELATIONS, 6), (SHADOWS, 2), (DEPENDENCIES, 1)),
        "not sqlite",
    ),
    "service_bridge": (
        BRIDGE,
        (
            ("test_create_decide_replay_commits_one_complete_tuple", 1),
            ("test_expired_deadline_refuses_before_writer_or_effects", 1),
            ("test_historical_quote_only_decision_replay_does_not_invent_transition", 1),
            ("test_response_failure_rolls_back_all_decision_effects", 1),
        ),
        "not sqlite",
    ),
    "writer5": (
        WRITER,
        (
            ("test_prepared_writer_retains_both_exact_raw_copies_and_generated_counts", 1),
            ("test_prepared_inserts_are_owned_by_caller_rollback", 3),
            ("test_ordinary_dictionary_writers_keep_payload_and_unbounded_contract", 1),
        ),
        "not sqlite",
    ),
    "admission9": (
        BOUNDED,
        (
            ("test_common_repository_create_checks_source_before_first_write", 1),
            ("test_invalid_part_reference_refuses_before_order_text_admission", 1),
            ("test_exhausted_version_refuses_new_enrollment_but_preserves_replay", 2),
            ("test_actual_projection_preparation_refuses_before_savepoint_or_write", 1),
            ("test_quote_writer_never_calls_generic_order_save", 1),
            ("test_source_utf8_boundary_is_checked_before_enrollment", 3),
        ),
        "not sqlite",
    ),
    "history9": (
        BOUNDED,
        (
            ("test_historical_replay_does_not_hydrate_oversized_current_text", 1),
            ("test_invalid_version_refuses_before_generic_payload_fetch", 6),
            ("test_two_transition_claims_refuse_before_generic_payload_fetch", 1),
            ("test_quote_outbox_pointer_cannot_prefetch_generic_order_json", 1),
        ),
        "not sqlite",
    ),
    "guards9": (
        BOUNDED,
        (
            ("test_order_timestamp_guard_refuses_before_driver_conversion", 3),
            ("test_order_row_lock_is_retained_during_prepare_and_persist", 1),
            ("test_small_compressed_text_is_refused_by_length_without_hydration", 1),
            ("test_bypassed_prepared_projection_refuses_before_any_write", 4),
        ),
        "not sqlite",
    ),
    "decision7": (
        DECISIONS,
        (
            ("test_service_decision_and_fresh_exact_replay", 2),
            ("test_service_enrollment_refuses_and_preserves_baseline", 3),
            ("test_service_post_consent_refuses_current_cas_without_writes", 2),
        ),
        "not sqlite",
    ),
    "mismatch_a7": (
        PAYLOAD,
        (("test_pg_derived_detached_identity_projection_mismatch", 7),),
        "not sqlite",
    ),
    "mismatch_b7": (
        PAYLOAD,
        (("test_pg_derived_detached_content_projection_mismatch", 7),),
        "not sqlite",
    ),
    "storage6": (
        PAYLOAD,
        (
            ("test_pg_derived_detached_note_nullness_requires_exact_true", 2),
            ("test_external_text_sql_preflight_refuses_without_hydration", 1),
            ("test_compressed_json_sql_pair_refuses_with_both_guarded_values_null", 1),
            ("test_asymmetric_sql_count_guard_nulls_both_raw_values", 2),
        ),
        "not sqlite",
    ),
    "atomic8": (
        ATOMICITY,
        (
            ("test_reached_write_failure_rolls_back_and_fresh_same_id_applies_once", 7),
            ("test_synthetic_commit_success_ack_loss_is_unknown_and_fresh_replay_is_exact", 1),
        ),
        "not sqlite",
    ),
    "races5": (
        RACES,
        (
            ("test_two_service_decisions_serialize_one_complete_effect_set", 3),
            ("test_waiting_service_rechecks_revoked_quote_grant_for_new_and_exact_replay", 2),
        ),
        "not sqlite",
    ),
    "pg_schema_immutable10": (
        "services/platform/tests/quotes/test_quote_schema.py",
        (("test_financial_history_update_delete_are_refused", 10),),
        "not sqlite",
    ),
    "pg_schema_operations11": (
        "services/platform/tests/quotes/test_quote_schema.py",
        (("test_operation_result_proof_and_effect_completeness", 11),),
        "not sqlite",
    ),
    "pg_schema_other5": (
        "services/platform/tests/quotes/test_quote_schema.py",
        (
            ("test_additive_quote_migration_and_forward_only_retention", 1),
            ("test_model_schema_and_migration_columns_match", 1),
            ("test_downgrade_refuses_before_changes", 1),
            (
                "test_complete_order_effect_tuple_is_retained_but_delivery_bookkeeping_can_change",
                1,
            ),
            ("test_postgres_truncate_guards", 1),
        ),
        "not sqlite",
    ),
    "pg_cutover_head1": (
        "services/platform/tests/identity/test_cutover_migration.py",
        (("test_cutover_initializes_unique_canonical_incarnations_without_changing_tenancy", 1),),
        "not sqlite",
    ),
    "pg_branding_head1": (
        "services/platform/tests/branding/test_profile_migration.py",
        (("test_branding_upgrade_preserves_accounts_and_qualifies_cutover_recovery", 1),),
        "not sqlite",
    ),
    "pg_repository_create3": (
        "services/platform/tests/quotes/test_quote_repository_postgres.py",
        (
            ("test_concurrent_same_operation_replays_once_or_refuses_changed_proof", 2),
            ("test_two_first_creations_keep_exactly_one_lineage", 1),
        ),
        "not sqlite",
    ),
    "pg_repository_append4": (
        "services/platform/tests/quotes/test_quote_repository_postgres.py",
        (("test_current_head_and_sequence_allow_only_one_competing_append", 4),),
        "not sqlite",
    ),
    "pg_repository_rollback4": (
        "services/platform/tests/quotes/test_quote_repository_postgres.py",
        (
            ("test_rollback_releases_first_create_without_publishing_any_partial_effect", 1),
            ("test_late_failure_rolls_back_savepoint_even_if_caller_commits", 3),
        ),
        "not sqlite",
    ),
}
PG_COUNTS = {
    "metadata_sync": 7,
    "metadata_outbox": 7,
    "metadata_relations": 9,
    "service_bridge": 4,
    "writer5": 5,
    "admission9": 9,
    "history9": 9,
    "guards9": 9,
    "decision7": 7,
    "mismatch_a7": 7,
    "mismatch_b7": 7,
    "storage6": 6,
    "atomic8": 8,
    "races5": 5,
    "pg_schema_immutable10": 10,
    "pg_schema_operations11": 11,
    "pg_schema_other5": 5,
    "pg_cutover_head1": 1,
    "pg_branding_head1": 1,
    "pg_repository_create3": 3,
    "pg_repository_append4": 4,
    "pg_repository_rollback4": 4,
}
JUNIT_COUNTS = {
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
EXISTING_JUNIT_SELECTIONS = {
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
CHECK_NAMES = (
    "test_fixed_postgres_selection_and_argv",
    "test_typed_postgres_collection_contract",
    "test_closed_postgres_reports_and_identities",
    "test_metadata_observer_and_bridge_registration",
    "test_numeric_failure_bounds_and_static_exactness",
    "test_fixed_junit_maps_and_parser",
)
STATIC_NAMES = (
    "test_repository_contract",
    "test_python_lint",
    "test_python_format",
    "test_production_types",
    "test_openapi_contract",
    "test_generated_client_contract",
)


def load_recipe(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ci" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg(monkeypatch):
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    return load_recipe("quote_integrity_postgres")


def pg_items(module):
    source, functions, _ = module.selection()
    names = [name for name, count in functions for _ in range(count)]
    parameters = zip(names, module.expected_parameters(), strict=True)
    items = []
    for index, (name, params) in enumerate(parameters):
        suffix = "[postgres]" if source == BRIDGE else f"[observed-{index}]"
        if source == REPOSITORY and not params:
            items.append(
                SimpleNamespace(path=ROOT / source, originalname=name, nodeid=f"{source}::{name}")
            )
            continue
        items.append(
            SimpleNamespace(
                path=ROOT / source,
                originalname=name,
                nodeid=f"{source}::{name}{suffix}",
                callspec=SimpleNamespace(params=params.copy()),
            )
        )
    return items


def pg_identity(node, index=0):
    prefix = "ocwp_access_" if node.startswith(REPOSITORY + "::") else "ocwp_identity_migration_"
    schema = f"{prefix}{index:032x}"
    return {
        "node": node,
        "dialect": "postgresql",
        "driver": "psycopg",
        "driver_version": "3.3.4",
        "database": "ocwp_quote_micro_test",
        "server_version_num": 180004,
        "server_encoding": "UTF8",
        "client_encoding": "UTF8",
        "schema_revision": "0013",
        "probe_connection_closed": True,
        "schema": schema,
        "search_path": schema,
    }


def pg_report(module):
    nodes = [item.nodeid for item in pg_items(module)]
    return {
        "schema": 1,
        "nodes": nodes,
        "postgres_identities": [pg_identity(node, i) for i, node in enumerate(nodes)],
        "collection_count": len(nodes),
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "session_finished": True,
        "session_exitstatus": 0,
        "reports": [
            {"node": node, "when": when, "outcome": "passed", "seconds": 0.01}
            for node in nodes
            for when in ("setup", "call", "teardown")
        ],
    }


def failure_summary(count):
    return {
        "schema": 1,
        "stage": 3,
        "session_exitstatus": 1,
        "collection_count": count,
        "collection_errors": 0,
        "unhandled_errors": 0,
        "protocol_errors": 0,
        "report_count": count * 3,
        "setup_reports": count,
        "call_reports": count,
        "teardown_reports": count,
        "failed_reports": 1,
        "skipped_reports": 0,
    }


def marker(prefix, value):
    return (
        prefix
        + json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        + b"\n"
    )


def test_fixed_postgres_selection_and_argv(pg, monkeypatch):
    assert pg.PG_GROUPS == PG_SELECTIONS
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PGHOST", "PGOPTIONS"):
        monkeypatch.setenv(name, "untrusted-setting")
    fixture = {"identity_migration_database": "postgres"}
    pairs = (("sync_changes", "entity_type"), ("outbox_events", "aggregate_type"))
    faults = (
        "mutable",
        "wrong_type",
        "wrong_expression",
        "wrong_discriminator",
        "jsonb",
        "virtual",
        "inherited",
    )
    expected = {
        group: [
            fixture | {"table": table, "discriminator": discriminator, "fault": fault}
            for fault in faults
        ]
        for group, (table, discriminator) in zip(
            ("metadata_sync", "metadata_outbox"), pairs, strict=True
        )
    }
    expected["metadata_relations"] = [
        fixture | {"table": table, "discriminator": discriminator, "replacement": replacement}
        for table, discriminator in pairs
        for replacement in ("partitioned", "view", "missing")
    ]
    expected["metadata_relations"].extend(
        fixture | {"shadow": shadow} for shadow in ("function", "operator")
    )
    expected["metadata_relations"].append(fixture)
    expected["service_bridge"] = [fixture] * 4
    expected["writer5"] = [
        fixture,
        fixture | {"failure_after": "sync_changes"},
        fixture | {"failure_after": "outbox_events"},
        fixture | {"failure_after": "caller"},
        fixture,
    ]
    expected["admission9"] = [
        fixture,
        fixture,
        fixture | {"replay": False},
        fixture | {"replay": True},
        fixture,
        fixture,
        fixture | {"delta": -1},
        fixture | {"delta": 0},
        fixture | {"delta": 1},
    ]
    expected["history9"] = [
        fixture,
        fixture | {"version": None},
        fixture | {"version": 0},
        fixture | {"version": 2},
        fixture | {"version": -1},
        fixture | {"version": True},
        fixture | {"version": "1"},
        fixture,
        fixture,
    ]
    expected["guards9"] = [
        fixture | {"value": "infinity"},
        fixture | {"value": "-infinity"},
        fixture | {"value": "10000-01-01 00:00:00+00"},
        fixture,
        fixture,
        fixture | {"field": "raw_json", "value": "{}"},
        fixture | {"field": "raw_octets", "value": 1},
        fixture | {"field": "canonical_utf8", "value": b"{}"},
        fixture | {"field": "payload", "value": {"version": True}},
    ]
    expected["decision7"] = [
        fixture
        | {
            "outcome": "APPROVE",
            "selected": (10, 11),
            "state": "AUTHORIZED",
            "action": "authorize",
        },
        fixture | {"outcome": "REJECT", "selected": (), "state": "REJECTED", "action": "reject"},
        fixture | {"reason": "prior_inventory"},
        fixture | {"reason": "progressed_history"},
        fixture | {"reason": "non_diagnosis"},
        fixture | {"kind": "revision"},
        fixture | {"kind": "decision"},
    ]
    expected["mismatch_a7"] = [
        fixture | {"field": "order_id", "value": "other-order"},
        fixture | {"field": "customer_id", "value": "other-customer"},
        fixture | {"field": "bicycle_id", "value": "other-bicycle"},
        fixture | {"field": "organization_id", "value": "other-organization"},
        fixture | {"field": "location_id", "value": "other-location"},
        fixture | {"field": "state", "value": "REJECTED"},
        fixture | {"field": "version", "value": 3},
    ]
    expected["mismatch_b7"] = [
        fixture | {"field": "reported_problem", "value": "Other reported problem"},
        fixture | {"field": "intake_condition", "value": "Other intake condition"},
        fixture | {"field": "accessories", "value": "Other accessories"},
        fixture | {"field": "priority", "value": "high"},
        fixture | {"field": "diagnosis", "value": "Other diagnosis"},
        fixture | {"field": "created_at", "value": "2026-10-14T00:00:00+00:00"},
        fixture | {"field": "updated_at", "value": "2026-10-15T12:00:01+00:00"},
    ]
    expected["storage6"] = [
        fixture | {"note_is_null": False},
        fixture | {"note_is_null": 1},
        fixture,
        fixture,
        fixture | {"oversized_side": "change"},
        fixture | {"oversized_side": "outbox"},
    ]
    expected["atomic8"] = [
        fixture | {"stage": "decision_flush"},
        fixture | {"stage": "lineage_cas"},
        fixture | {"stage": "order_cas"},
        fixture | {"stage": "order_event_flush"},
        fixture | {"stage": "quote_outbox_flush"},
        fixture | {"stage": "receipt_flush"},
        fixture | {"stage": "response_serialization"},
        fixture,
    ]
    expected["races5"] = [
        fixture | {"contender": "same_proof"},
        fixture | {"contender": "changed_proof"},
        fixture | {"contender": "distinct_decision"},
        fixture | {"replay": False},
        fixture | {"replay": True},
    ]
    expected["pg_schema_immutable10"] = [
        {"identity_migration_database": "postgres", "table": "quote_decisions", "verb": "UPDATE"},
        {"identity_migration_database": "postgres", "table": "quote_decisions", "verb": "DELETE"},
        {
            "identity_migration_database": "postgres",
            "table": "quote_line_targets",
            "verb": "UPDATE",
        },
        {
            "identity_migration_database": "postgres",
            "table": "quote_line_targets",
            "verb": "DELETE",
        },
        {"identity_migration_database": "postgres", "table": "quote_lines", "verb": "UPDATE"},
        {"identity_migration_database": "postgres", "table": "quote_lines", "verb": "DELETE"},
        {"identity_migration_database": "postgres", "table": "quote_operations", "verb": "UPDATE"},
        {"identity_migration_database": "postgres", "table": "quote_operations", "verb": "DELETE"},
        {"identity_migration_database": "postgres", "table": "quote_revisions", "verb": "UPDATE"},
        {"identity_migration_database": "postgres", "table": "quote_revisions", "verb": "DELETE"},
    ]
    expected["pg_schema_operations11"] = [
        {"identity_migration_database": "postgres", "changes": {"kind": "unknown"}},
        {"identity_migration_database": "postgres", "changes": {"proof_version": 2}},
        {"identity_migration_database": "postgres", "changes": {"decision_id": "decision-b"}},
        {"identity_migration_database": "postgres", "changes": {"actor_id": "actor-b"}},
        {"identity_migration_database": "postgres", "changes": {"ordinal": 4}},
        {
            "identity_migration_database": "postgres",
            "changes": {"resulting_decision_sequence": -1},
        },
        {
            "identity_migration_database": "postgres",
            "changes": {"kind": "decision", "decision_id": None},
        },
        {
            "identity_migration_database": "postgres",
            "changes": {"kind": "create", "quote_version": 2},
        },
        {"identity_migration_database": "postgres", "changes": {"order_event_id": "event"}},
        {"identity_migration_database": "postgres", "changes": {"change_cursor": 1}},
        {"identity_migration_database": "postgres", "changes": {"quote_outbox_id": None}},
    ]
    expected["pg_schema_other5"] = [
        {"identity_migration_database": "postgres"},
        {"identity_migration_database": "postgres"},
        {"identity_migration_database": "postgres"},
        {"identity_migration_database": "postgres"},
        {"identity_migration_database": "postgres"},
    ]
    expected["pg_cutover_head1"] = [
        {"identity_migration_database": "postgres"},
    ]
    expected["pg_branding_head1"] = [
        {"identity_migration_database": "postgres"},
    ]
    expected["pg_repository_create3"] = [
        {"changed_proof": False},
        {"changed_proof": True},
        {},
    ]
    expected["pg_repository_append4"] = [
        {"contenders": "revisions"},
        {"contenders": "revision_decision"},
        {"contenders": "decisions"},
        {"contenders": "corrections"},
    ]
    expected["pg_repository_rollback4"] = [
        {},
        {"failure_stage": "outbox"},
        {"failure_stage": "receipt"},
        {"failure_stage": "after_flush"},
    ]
    for group, selection in PG_SELECTIONS.items():
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        source, functions, expression = selection
        assert pg.selection() == selection
        assert pg.case_count() == PG_COUNTS[group]
        assert pg.expected_parameters() == expected[group]
        for actual, wanted in zip(pg.expected_parameters(), expected[group], strict=True):
            assert type(actual) is dict and actual.keys() == wanted.keys()
            assert all(type(key) is str for key in actual)
            for key, value in wanted.items():
                assert type(actual[key]) is type(value)
                if type(value) is tuple:
                    assert len(actual[key]) == len(value)
                    assert all(type(item) is int for item in actual[key])
                if type(value) is dict:
                    if group == "pg_schema_operations11":
                        assert actual[key].keys() == value.keys()
                        assert all(type(field) is str for field in actual[key])
                        assert all(
                            type(actual[key][field]) is type(item) for field, item in value.items()
                        )
                    else:
                        assert list(actual[key]) == ["version"]
                        assert type(next(iter(actual[key]))) is str
                        assert actual[key]["version"] is True
        args = pg.service_argv("a" * 64)
        assert args[:5] == ["docker", "exec", "a" * 64, "env", "-i"]
        assert args[-len(functions) :] == [f"{source}::{name}" for name, _ in functions]
        assert args[args.index("-k") + 1] == expression
        assert f"OCWP_INTEGRITY_GROUP={group}" in args
        assert "scripts.ci.quote_integrity_postgres" in args
        assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in args
        assert {
            "--tb=short",
            "--no-showlocals",
            "--show-capture=no",
            "--capture=fd",
            "--maxfail=1",
        } <= set(args)
        assert [arg for arg in args if arg.startswith("OCWP_TEST_DATABASE_URL=")] == [
            "OCWP_TEST_DATABASE_URL=postgresql+psycopg://ocwp:ocwp-synthetic"
            "@127.0.0.1:5432/ocwp_quote_micro_test"
        ]
        assert "untrusted-setting" not in " ".join(args)
        assert not any("[postgres]" in arg for arg in args)
    for group in ("", "metadata", "postgres", "static6", "service27", "selection_static12"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        with pytest.raises(pg.ProofFailure, match="service_selection"):
            pg.selection()


def test_typed_postgres_collection_contract(pg, monkeypatch):
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        offset = 0
        for _, count in PG_SELECTIONS[group][1]:
            items[offset : offset + count] = reversed(items[offset : offset + count])
            offset += count
        hook = pg.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == [item.nodeid for item in items]
        assert hook.value["collection_count"] == PG_COUNTS[group]
        assert hook.value["protocol_errors"] == 0
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    for fault in (
        "source",
        "function",
        "keys",
        "duplicate_row",
        "missing",
        "extra",
        "duplicate_node",
        "function_order",
        "missing_callspec",
        "wrong_pair",
        "wrong_shadow",
    ):
        items = pg_items(pg)
        if fault == "source":
            items[0].path = ROOT / BRIDGE
        elif fault == "function":
            items[0].originalname = MALFORMED
        elif fault == "keys":
            items[0].callspec.params["extra"] = "postgres"
        elif fault == "duplicate_row":
            items[1].callspec.params = items[0].callspec.params.copy()
        elif fault == "missing":
            items.pop()
        elif fault == "extra":
            items.append(deepcopy(items[-1]))
        elif fault == "duplicate_node":
            items[1].nodeid = items[0].nodeid
        elif fault == "function_order":
            items[0], items[6] = items[6], items[0]
        elif fault == "missing_callspec":
            del items[0].callspec
        elif fault == "wrong_pair":
            items[0].callspec.params["discriminator"] = "aggregate_type"
        else:
            items[6].callspec.params["shadow"] = "unknown"
        hook = pg.ServiceReportHook()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == []
        assert hook.value["protocol_errors"] == 1
    for value in (True, 1, b"postgres", ["postgres"], "sqlite"):
        items = pg_items(pg)
        items[0].callspec.params["identity_migration_database"] = value
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))

    class OtherString(str):
        pass

    for replace_key in (False, True):
        items = pg_items(pg)
        params = items[0].callspec.params
        if replace_key:
            params[OtherString("table")] = params.pop("table")
        else:
            params["table"] = OtherString(params["table"])
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    prefix = f"{METADATA}::{RELATIONS}"
    assert pg.selected_node(prefix + "[" + "x" * 62 + "]", RELATIONS)
    for suffix in ("[" + "x" * 63 + "]", "[" + "\\" * 32 + "]", "[é]", "[x\n]", "x"):
        assert not pg.selected_node(prefix + suffix, RELATIONS)
    for group in ("metadata_sync", "metadata_outbox"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        for value in (True, "unknown"):
            items = pg_items(pg)
            items[0].callspec.params["fault"] = value
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
        items = pg_items(pg)
        items[1].callspec.params = items[0].callspec.params.copy()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "service_bridge")
    function = PG_SELECTIONS["service_bridge"][1][0][0]
    assert pg.selected_node(f"{BRIDGE}::{function}[postgres]", function)
    assert not pg.selected_node(f"{BRIDGE}::{function}[sqlite]", function)
    for group, index, key, value in (
        ("writer5", 1, "failure_after", True),
        ("writer5", 1, "failure_after", "unknown"),
        ("admission9", 2, "replay", 0),
        ("admission9", 3, "replay", 1),
        ("admission9", 2, "replay", "False"),
        ("admission9", 6, "delta", -1.0),
        ("admission9", 7, "delta", False),
        ("admission9", 8, "delta", True),
        ("admission9", 8, "delta", 2),
        ("history9", 1, "version", "None"),
        ("history9", 2, "version", False),
        ("history9", 3, "version", 2.0),
        ("history9", 4, "version", -1.0),
        ("history9", 5, "version", 1),
        ("history9", 6, "version", 1),
        ("guards9", 0, "value", b"infinity"),
        ("guards9", 0, "value", "unknown"),
        ("guards9", 5, "field", OtherString("raw_json")),
        ("guards9", 5, "value", b"{}"),
        ("guards9", 5, "value", bytearray(b"{}")),
        ("guards9", 6, "value", True),
        ("guards9", 6, "value", 1.0),
        ("guards9", 7, "value", "{}"),
        ("guards9", 7, "value", bytearray(b"{}")),
        ("guards9", 7, "value", b"{ }"),
        ("guards9", 8, "value", {"version": 1}),
        ("guards9", 8, "value", {"version": False}),
        ("guards9", 8, "value", {"version": "true"}),
        ("guards9", 8, "value", {"other": True}),
        ("guards9", 8, "value", {b"version": True}),
        ("guards9", 8, "value", {OtherString("version"): True}),
        ("guards9", 8, "value", {"version": True, "extra": True}),
        ("guards9", 8, "value", []),
        ("decision7", 0, "selected", [10, 11]),
        ("decision7", 0, "selected", (10.0, 11)),
        ("decision7", 0, "selected", (True, 11)),
        ("decision7", 0, "selected", (10,)),
        ("decision7", 0, "selected", (10, 12)),
        ("decision7", 1, "selected", []),
        ("decision7", 0, "action", "reject"),
        ("decision7", 0, "state", "REJECTED"),
        ("decision7", 0, "outcome", "REJECT"),
        ("decision7", 2, "reason", "unknown"),
        ("decision7", 5, "kind", True),
        ("mismatch_a7", 0, "value", "other-customer"),
        ("mismatch_a7", 6, "value", 3.0),
        ("mismatch_a7", 6, "value", True),
        ("mismatch_b7", 0, "value", "Other intake condition"),
        ("mismatch_b7", 5, "value", b"2026-10-14T00:00:00+00:00"),
        ("storage6", 0, "note_is_null", 0),
        ("storage6", 1, "note_is_null", True),
        ("storage6", 4, "oversized_side", "unknown"),
        ("atomic8", 0, "stage", "unknown"),
        ("races5", 0, "contender", "unknown"),
        ("races5", 3, "replay", 0),
        ("races5", 4, "replay", 1),
        ("pg_schema_immutable10", 0, "table", "quote_lineages"),
        ("pg_schema_immutable10", 0, "verb", "TRUNCATE"),
        ("pg_schema_operations11", 1, "changes", {"proof_version": True}),
        ("pg_schema_operations11", 1, "changes", {"proof_version": 2.0}),
        ("pg_schema_operations11", 1, "changes", {b"proof_version": 2}),
        ("pg_schema_operations11", 1, "changes", {OtherString("proof_version"): 2}),
        ("pg_schema_operations11", 1, "changes", {"proof_version": 2, "extra": None}),
        ("pg_schema_operations11", 6, "changes", {"kind": "decision", "decision_id": "None"}),
        ("pg_schema_operations11", 6, "changes", {"kind": "decision"}),
        ("pg_schema_operations11", 0, "changes", {"kind": OtherString("unknown")}),
        ("pg_schema_operations11", 10, "changes", {"quote_outbox_id": False}),
        ("pg_schema_operations11", 0, "changes", []),
        ("pg_repository_create3", 0, "changed_proof", 0),
        ("pg_repository_create3", 1, "changed_proof", 1),
        ("pg_repository_append4", 0, "contenders", "unknown"),
        ("pg_repository_rollback4", 1, "failure_stage", "unknown"),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        items[index].callspec.params[key] = value
        hook = pg.ServiceReportHook()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            hook.pytest_collection_finish(SimpleNamespace(items=items))
        assert hook.value["nodes"] == [] and hook.value["protocol_errors"] == 1
    for group, first, second in (
        ("writer5", 1, 2),
        ("admission9", 2, 3),
        ("admission9", 6, 7),
        ("history9", 1, 2),
        ("guards9", 0, 1),
        ("guards9", 5, 6),
        ("guards9", 5, 7),
        ("guards9", 5, 8),
        ("guards9", 6, 7),
        ("guards9", 6, 8),
        ("guards9", 7, 8),
        ("decision7", 0, 1),
        ("decision7", 2, 3),
        ("decision7", 5, 6),
        ("mismatch_a7", 0, 1),
        ("mismatch_b7", 5, 6),
        ("storage6", 0, 1),
        ("storage6", 4, 5),
        ("atomic8", 0, 1),
        ("races5", 0, 1),
        ("races5", 3, 4),
        ("pg_schema_immutable10", 0, 1),
        ("pg_schema_operations11", 0, 1),
        ("pg_repository_create3", 0, 1),
        ("pg_repository_append4", 0, 1),
        ("pg_repository_rollback4", 1, 2),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        items[second].callspec.params = items[first].callspec.params.copy()
        with pytest.raises(pytest.UsageError, match="service_selection"):
            pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
        if group == "guards9" and first >= 5:
            items = pg_items(pg)
            left, right = items[first].callspec.params, items[second].callspec.params
            left["value"], right["value"] = right["value"], left["value"]
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))
    for group in (
        "writer5",
        "admission9",
        "history9",
        "guards9",
        "decision7",
        "storage6",
        "atomic8",
        "races5",
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        for fault in ("function_order", "extra_key", "missing_key"):
            items = pg_items(pg)
            if fault == "function_order":
                items[0], items[-1] = items[-1], items[0]
            elif fault == "extra_key":
                items[0].callspec.params["extra"] = True
            else:
                del items[0].callspec.params["identity_migration_database"]
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=items))

    for group in ("pg_repository_create3", "pg_repository_rollback4"):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        items = pg_items(pg)
        bare = next(item for item in items if not hasattr(item, "callspec"))
        assert pg.selected_node(bare.nodeid, bare.originalname)
        assert not pg.selected_node(bare.nodeid + "[postgres]", bare.originalname)
        for fault in ("unexpected_params", "missing_parameterized_callspec", "foreign_function"):
            bad = deepcopy(items)
            if fault == "unexpected_params":
                next(
                    item for item in bad if not hasattr(item, "callspec")
                ).callspec = SimpleNamespace(params={"identity_migration_database": "postgres"})
            elif fault == "missing_parameterized_callspec":
                del next(item for item in bad if hasattr(item, "callspec")).callspec
            else:
                bad[0].originalname = "test_unselected_function"
            with pytest.raises(pytest.UsageError, match="service_selection"):
                pg.ServiceReportHook().pytest_collection_finish(SimpleNamespace(items=bad))
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "pg_schema_operations11")
    function = PG_SELECTIONS["pg_schema_operations11"][1][0][0]
    prefix = f"{SCHEMA}::{function}"
    assert pg.selected_node(prefix + "[" + "x" * 30 + "]", function)
    assert not pg.selected_node(prefix + "[" + "x" * 31 + "]", function)
    for value in ("[" + "x" * 30 + "]", "[" + "x" * 31 + "]"):
        report = pg_report(pg)
        old = report["nodes"][0]
        new = prefix + value
        report["nodes"][0] = new
        report["postgres_identities"][0]["node"] = new
        for phase in report["reports"]:
            if phase["node"] == old:
                phase["node"] = new
        if len(value) == 32:
            pg.service_result(json.dumps(report))
        else:
            with pytest.raises(pg.ProofFailure, match="service_selection"):
                pg.service_result(json.dumps(report))


def test_closed_postgres_reports_and_identities(pg, monkeypatch, tmp_path):
    assert pg.LIMIT == 16 * 1024
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        good = pg_report(pg)
        assert pg.service_result(json.dumps(good)) == good
        assert len(good["reports"]) == PG_COUNTS[group] * 3
    for group, prefix in (
        ("pg_repository_create3", "ocwp_identity_migration_"),
        ("pg_schema_immutable10", "ocwp_access_"),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        bad = pg_report(pg)
        for field in ("schema", "search_path"):
            bad["postgres_identities"][0][field] = prefix + "0" * 32
        with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
            pg.service_result(json.dumps(bad))
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    good = pg_report(pg)
    for field, value in (
        ("collection_count", True),
        ("collection_errors", 1),
        ("protocol_errors", 1),
        ("unhandled_errors", 1),
        ("session_finished", False),
        ("session_exitstatus", 1),
    ):
        with pytest.raises(pg.ProofFailure):
            pg.service_result(json.dumps(good | {field: value}))
    for field, value in (
        ("when", "teardown"),
        ("node", good["nodes"][1]),
        ("outcome", "skipped"),
        ("outcome", "failed"),
        ("seconds", True),
        ("seconds", 20),
        ("captured", "private"),
    ):
        bad = deepcopy(good)
        bad["reports"][0][field] = value
        with pytest.raises(pg.ProofFailure):
            pg.service_result(json.dumps(bad))
    for field in ("reports", "nodes", "postgres_identities"):
        for duplicate in (False, True):
            bad = deepcopy(good)
            if duplicate:
                bad[field][1] = deepcopy(bad[field][0])
            else:
                bad[field].pop()
            with pytest.raises(pg.ProofFailure):
                pg.service_result(json.dumps(bad))
    for field, value in (
        ("node", good["nodes"][1]),
        ("database", "external_test"),
        ("server_version_num", "180004"),
        ("schema_revision", "0012"),
        ("probe_connection_closed", 1),
        ("client_encoding", "LATIN1"),
        ("search_path", "public"),
        ("payload", "private"),
    ):
        bad = deepcopy(good)
        bad["postgres_identities"][0][field] = value
        with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
            pg.service_result(json.dumps(bad))
    bad = deepcopy(good)
    for key in ("schema", "search_path"):
        bad["postgres_identities"][1][key] = bad["postgres_identities"][0][key]
    with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
        pg.service_result(json.dumps(bad))
    raw = json.dumps(good)
    assert pg.service_result(raw + " " * (pg.LIMIT - len(raw) - 1)) == good
    for invalid in (raw + " " * (pg.LIMIT - len(raw)), raw[:-1] + ', "schema": 1}'):
        with pytest.raises(pg.ProofFailure):
            pg.service_result(invalid)
    hook = pg.ServiceReportHook()
    hook.pytest_collection_finish(SimpleNamespace(items=pg_items(pg)))
    by_node = {identity["node"]: identity for identity in good["postgres_identities"]}
    for row in good["reports"]:
        hook.pytest_runtest_logreport(
            SimpleNamespace(
                nodeid=row["node"],
                when=row["when"],
                outcome="passed",
                duration=0.01,
                user_properties=[("ocwp_postgres_identity", by_node[row["node"]])],
                longrepr="private",
                capstdout="private",
            )
        )
    target = tmp_path / "closed.json"
    monkeypatch.setattr(pg, "SERVICE_REPORT", str(target))
    hook.pytest_sessionfinish(SimpleNamespace(), 0)
    assert pg.service_result(target.read_text()) == good
    assert len(hook.value["reports"]) == 27 and hook.value["protocol_errors"] == 0
    assert "private" not in target.read_text()
    hook.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid=good["nodes"][-1],
            when="call",
            outcome="passed",
            duration=0.01,
        )
    )
    assert len(hook.value["reports"]) == 27 and hook.value["protocol_errors"] == 1
    for fault in ("missing", "duplicate", "foreign", "xfail"):
        node = good["nodes"][0]
        properties = [("ocwp_postgres_identity", pg_identity(node))]
        if fault == "missing":
            properties = []
        elif fault == "duplicate":
            properties *= 2
        elif fault == "foreign":
            properties[0][1]["node"] = good["nodes"][1]
        row = SimpleNamespace(
            nodeid=node,
            when="teardown",
            outcome="passed",
            duration=0.01,
            user_properties=properties,
        )
        if fault == "xfail":
            row.wasxfail = "private"
        hook = pg.ServiceReportHook()
        hook.pytest_collection_finish(SimpleNamespace(items=pg_items(pg)))
        hook.pytest_runtest_logreport(row)
        assert hook.value["protocol_errors"] == 1
        assert hook.value["postgres_identities"] == []


def test_metadata_observer_and_bridge_registration(pg, monkeypatch):
    engine = object()
    events = []

    def probe(actual_engine, actual_node):
        assert actual_engine is engine and actual_node == node
        events.append("final_probe")
        return pg_identity(node)

    monkeypatch.setattr(pg, "probe_postgres_identity", probe)
    for group in PG_SELECTIONS:
        if group in SETUP_IDENTITY_GROUPS:
            continue
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        node = pg_items(pg)[0].nodeid
        events.clear()
        request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
        observer = pg.observe_postgres((object(), engine), request)
        next(observer)
        assert events == [] and request.node.user_properties == []
        events.append("body_transaction_closed")
        with pytest.raises(StopIteration):
            next(observer)
        assert events == ["body_transaction_closed", "final_probe"]
        assert request.node.user_properties == [("ocwp_postgres_identity", pg_identity(node))]
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    node = pg_items(pg)[0].nodeid
    request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
    monkeypatch.setattr(
        pg,
        "probe_postgres_identity",
        lambda *_args: pg_identity(node) | {"schema_revision": "0012"},
    )
    request.node.user_properties.clear()
    observer = pg.observe_postgres((object(), engine), request)
    next(observer)
    with pytest.raises(pg.ProofFailure, match="service_postgres_identity"):
        next(observer)
    assert request.node.user_properties == []
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "pg_repository_create3")
    node = pg_items(pg)[0].nodeid
    events.clear()
    monkeypatch.setattr(pg, "probe_postgres_identity", probe)
    request = SimpleNamespace(node=SimpleNamespace(nodeid=node, user_properties=[]))
    with monkeypatch.context() as local:
        local.setattr(pytest, "fixture", lambda **_options: lambda function: function)
        plugin = pg.postgres_observer_plugin()
    observer = plugin.ocwp_postgres_observer(SimpleNamespace(engine=engine), request)
    next(observer)
    assert events == [] and request.node.user_properties == []
    events.append("body_transaction_closed")
    with pytest.raises(StopIteration):
        next(observer)
    assert events == ["body_transaction_closed", "final_probe"]
    assert request.node.user_properties == [("ocwp_postgres_identity", pg_identity(node))]
    request.node.user_properties.clear()
    for group in PG_SELECTIONS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        calls = []
        observer_plugin = object()
        monkeypatch.setattr(pg, "postgres_observer_plugin", lambda plugin=observer_plugin: plugin)
        config = SimpleNamespace(
            pluginmanager=SimpleNamespace(register=lambda *args, saved=calls: saved.append(args))
        )
        monkeypatch.delenv("OCWP_QUOTE_SERVICE_INITIAL", raising=False)
        with pytest.raises(pg.ProofFailure, match="service_hook_context"):
            pg.pytest_configure(config)
        assert calls == []
        monkeypatch.setenv("OCWP_QUOTE_SERVICE_INITIAL", "contained")
        pg.pytest_configure(config)
        assert isinstance(calls[0][0], pg.ServiceReportHook)
        assert calls[0][1] == "quote-service-closed-report"
        expected = (
            [] if group in SETUP_IDENTITY_GROUPS else [(observer_plugin, "quote-postgres-observer")]
        )
        assert calls[1:] == expected
    for group in SETUP_IDENTITY_GROUPS:
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        request.node.nodeid = pg_items(pg)[0].nodeid
        with pytest.raises(pg.ProofFailure, match="service_selection"):
            next(pg.observe_postgres((object(), engine), request))
        assert request.node.user_properties == []


def test_numeric_failure_bounds_and_static_exactness(pg, monkeypatch):
    from test_quote_integrity_static_contracts import COMMANDS

    assert pg.STATIC_FAILURE_LIMIT == 24 * 1024
    assert "services/platform/tests/quotes/test_quote_history_byte_reuse.py" in COMMANDS[1]
    assert "services/platform/tests/quotes/test_quote_history_byte_reuse.py" in COMMANDS[2]
    for group, ceiling in (
        ("metadata_sync", 21),
        ("metadata_outbox", 21),
        ("metadata_relations", 27),
        ("service_bridge", 18),
        ("writer5", 18),
        ("admission9", 27),
        ("history9", 27),
        ("guards9", 27),
        ("decision7", 21),
        ("mismatch_a7", 21),
        ("mismatch_b7", 21),
        ("storage6", 18),
        ("atomic8", 24),
        ("races5", 18),
        ("pg_schema_immutable10", 30),
        ("pg_schema_operations11", 33),
        ("pg_schema_other5", 18),
        ("pg_cutover_head1", 18),
        ("pg_branding_head1", 18),
        ("pg_repository_create3", 18),
        ("pg_repository_append4", 18),
        ("pg_repository_rollback4", 18),
    ):
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        boundary = failure_summary(ceiling // 3) | {"collection_count": PG_COUNTS[group]}
        raw = marker(pg.SERVICE_FAILURE_MARKER, boundary)
        assert pg.service_failure_diagnostic(raw, returncode=1) == boundary
        overflow = boundary | {
            "report_count": ceiling + 1,
            "setup_reports": boundary["setup_reports"] + 1,
        }
        with pytest.raises(pg.ProofFailure):
            pg.service_failure_diagnostic(marker(pg.SERVICE_FAILURE_MARKER, overflow), returncode=1)
    monkeypatch.setenv("OCWP_INTEGRITY_GROUP", "metadata_relations")
    good = failure_summary(9)
    assert good["report_count"] == 27
    raw = marker(pg.SERVICE_FAILURE_MARKER, good)
    assert pg.service_failure_diagnostic(raw, returncode=1) == good
    for change in (
        {"report_count": 28, "setup_reports": 10},
        {"report_count": True},
        {"failed_reports": 28},
        {"skipped_reports": -1},
        {"report_count": 26},
        {"private": "text"},
    ):
        with pytest.raises(pg.ProofFailure):
            pg.service_failure_diagnostic(
                marker(pg.SERVICE_FAILURE_MARKER, good | change), returncode=1
            )
    for tool in range(6):
        output = {
            "schema": 2,
            "tool": tool,
            "kind": 1,
            "returncode": 1,
            "output_bytes": 0,
            "output_truncated": False,
            "output_base64": "",
        }
        protocol = failure_summary(tool + 1) | {"collection_count": 6}
        raw = marker(pg.STATIC_FAILURE_MARKER, output)
        assert pg.static_failure_diagnostic(raw, failure=protocol) == output
        for change in (
            {"collection_count": 9},
            {"report_count": 27, "setup_reports": 9, "call_reports": 9, "teardown_reports": 9},
            {"failed_reports": 2},
            {"schema": True},
        ):
            with pytest.raises(pg.ProofFailure, match="static_diagnostic_protocol"):
                pg.static_failure_diagnostic(raw, failure=protocol | change)
    assert protocol["report_count"] == 18


def junit_document(module):
    root = ET.Element("testsuites", name="pytest tests")
    suite = ET.SubElement(
        root,
        "testsuite",
        name="pytest",
        errors="0",
        failures="0",
        skipped="0",
        tests=str(module.CASE_COUNT),
        time="0.010",
        timestamp="2026-10-17T00:00:00",
        hostname="synthetic",
    )
    for path, cases in module.SELECTION:
        for name, count, suffix_limit in cases:
            for index in range(count):
                ET.SubElement(
                    suite,
                    "testcase",
                    classname=module.SOURCE_CLASSES[path],
                    name=f"{name}[{index}]" if suffix_limit else name,
                    time="0.000",
                )
    return root


def xml_text(root):
    return ET.tostring(root, encoding="unicode")


def test_fixed_junit_maps_and_parser(monkeypatch, tmp_path):
    modules = {}
    base = "services/platform/tests/quotes/"
    sources = {
        "service27": (
            base + "test_quote_application_service.py",
            "tests/operations/test_quote_integrity_selection.py",
        ),
        "atomic18_corruption": (base + "test_quote_atomic_effects.py",),
        "atomic18_other": (base + "test_quote_atomic_effects.py",),
        "response50": (base + "test_quote_command_response.py",),
        "response64": (base + "test_quote_command_response.py",),
        "static6": ("tests/operations/test_quote_integrity_static_contracts.py",),
        "selection_static12": (
            "tests/operations/test_quote_integrity_selection.py",
            "tests/operations/test_quote_integrity_static_contracts.py",
        ),
    }
    sources.update(
        {
            group: tuple(path for path, _ in selection)
            for group, selection in EXISTING_JUNIT_SELECTIONS.items()
        }
    )
    for group, count in JUNIT_COUNTS.items():
        # The JUnit recipe freezes group constants at import time.
        monkeypatch.setenv("OCWP_INTEGRITY_GROUP", group)
        module = load_recipe("quote_integrity_checks")
        modules[group] = module
        assert module.GROUP_COUNTS == JUNIT_COUNTS
        assert set(module.GROUPS) == set(JUNIT_COUNTS)
        assert group == module.GROUP_KEY and count == module.CASE_COUNT
        assert sum(module.EXPECTED_COUNTS.values()) == count
        assert tuple(path for path, _ in module.SELECTION) == sources[group]
        assert [
            path.removesuffix(".py").replace("/", ".") for path in sources[group]
        ] == module.CLASS_NAMES
        assert (
            tuple(f"{path}::{name}" for path, cases in module.SELECTION for name, _, _ in cases)
            == module.NODES
        )
        assert module.PYTEST[-len(module.NODES) :] == list(module.NODES)
        assert module.PYTEST[:2] == ["env", "-i"]
        if group in EXISTING_JUNIT_SELECTIONS:
            assert EXISTING_JUNIT_SELECTIONS[group] == module.SELECTION
        if group.startswith("sqlite_"):
            assert module.PYTEST[module.PYTEST.index("-k") + 1] == "not postgres"
        else:
            assert "-k" not in module.PYTEST
        static = group in ("static6", "selection_static12")
        assert module.LIMIT == 16 * 1024
        assert (32 * 1024 if static else 16 * 1024) == module.SPOOL_LIMIT
        assert ("OCWP_QUOTE_SERVICE_INITIAL=contained" in module.PYTEST) is static
        assert not any(
            "DATABASE_URL=" in arg or "quote_integrity_postgres" in arg for arg in module.PYTEST
        )
        assert all("[" not in node for node in module.NODES)
        root = junit_document(module)
        value = module.parse_junit(xml_text(root))
        assert value["tests"] == count and value["expected_counts"] == module.EXPECTED_COUNTS
        assert value["class_names"] == module.CLASS_NAMES
        assert value["observed_cases"] == [case.attrib["name"] for case in root[0]]
        assert value["failures"] == value["errors"] == value["skipped"] == 0
        assert value["session_finished"] is True
        for fault in (
            "missing",
            "duplicate",
            "source",
            "function",
            "order",
            "skipped",
            "failure",
            "duration",
            "capture",
            "extra_attribute",
            "text",
        ):
            bad = deepcopy(root)
            suite = bad[0]
            if fault == "missing":
                suite.remove(suite[-1])
            elif fault == "duplicate":
                suite[1].attrib["name"] = suite[0].attrib["name"]
            elif fault == "source":
                suite[0].attrib["classname"] = "tests.foreign"
            elif fault == "function":
                suite[0].attrib["name"] = "test_foreign[0]"
            elif fault == "order":
                if len(module.NODES) > 1:
                    suite[0], suite[-1] = suite[-1], suite[0]
                else:
                    # The sole function has no function sequence to swap.
                    suite[0].attrib["name"] = "test_foreign[0]"
            elif fault == "skipped":
                suite.attrib["skipped"] = "1"
            elif fault == "failure":
                ET.SubElement(suite[0], "failure", message="private")
            elif fault == "duration":
                suite[0].attrib["time"] = "20.000"
            elif fault == "capture":
                ET.SubElement(suite[0], "system-out").text = "private"
            elif fault == "extra_attribute":
                suite[0].attrib["file"] = "foreign.py"
            else:
                suite[0].text = "private"
            with pytest.raises(module.Refusal):
                module.parse_junit(xml_text(bad))
        function, _, suffix_limit = module.SELECTION[0][1][0]
        bad = deepcopy(root)
        if suffix_limit:
            bad[0][0].attrib["name"] = function + "[" + "x" * (suffix_limit - 2) + "]"
            module.parse_junit(xml_text(bad))
            bad[0][0].attrib["name"] = function + "[" + "x" * (suffix_limit - 1) + "]"
        else:
            bad[0][0].attrib["name"] = function + "[0]"
        with pytest.raises(module.Refusal):
            module.parse_junit(xml_text(bad))
        raw = xml_text(root)
        size = len(raw.encode("utf-8"))
        assert size < module.LIMIT
        module.parse_junit(raw + " " * (module.LIMIT - size - 1))
        for invalid in (
            raw + " " * (module.LIMIT - size),
            '<!DOCTYPE testsuites [<!ENTITY value "private">]>' + raw,
        ):
            with pytest.raises(module.Refusal):
                module.parse_junit(invalid)
    service = modules["service27"]
    assert service.EXPECTED_COUNTS["test_nul_order_reference_refuses_before_text_hydration"] == 2
    assert service.SELECTION[1] == (
        "tests/operations/test_quote_integrity_selection.py",
        tuple((name, 1, 0) for name in CHECK_NAMES),
    )
    assert service.CLASS_NAMES == [
        "services.platform.tests.quotes.test_quote_application_service",
        "tests.operations.test_quote_integrity_selection",
    ]
    combined = modules["selection_static12"]
    assert (
        (
            "tests/operations/test_quote_integrity_selection.py",
            tuple((name, 1, 0) for name in CHECK_NAMES),
        ),
        (
            "tests/operations/test_quote_integrity_static_contracts.py",
            tuple((name, 1, 0) for name in STATIC_NAMES),
        ),
    ) == combined.SELECTION
    assert dict.fromkeys((*CHECK_NAMES, *STATIC_NAMES), 1) == combined.EXPECTED_COUNTS
    assert combined.CLASS_NAMES == [
        "tests.operations.test_quote_integrity_selection",
        "tests.operations.test_quote_integrity_static_contracts",
    ]
    assert (combined.SELECTION[1],) == modules["static6"].SELECTION
    assert modules["response50"].EXPECTED_COUNTS == {
        "test_numeric_fields_refuse_coercion_and_unsafe_values": 50
    }
    response_counts = modules["response64"].EXPECTED_COUNTS
    assert response_counts["test_service_projector_preserves_four_digit_receipt_year"] == 8
    for left, right in (("response50", "response64"), ("atomic18_corruption", "atomic18_other")):
        assert set(modules[left].NODES).isdisjoint(modules[right].NODES)
    original_junit = (
        "service27",
        "atomic18_corruption",
        "atomic18_other",
        "response50",
        "response64",
        "static6",
        "selection_static12",
    )
    original_pg = (
        "metadata_sync",
        "metadata_outbox",
        "metadata_relations",
        "service_bridge",
        "writer5",
        "admission9",
        "history9",
        "guards9",
        "decision7",
        "mismatch_a7",
        "mismatch_b7",
        "storage6",
        "atomic8",
        "races5",
    )
    assert (
        sum(JUNIT_COUNTS[key] for key in original_junit)
        + sum(PG_COUNTS[key] for key in original_pg)
        == 294
    )
    assert sum(JUNIT_COUNTS.values()) + sum(PG_COUNTS.values()) == 619
    assert (
        sum(JUNIT_COUNTS[key] for key in EXISTING_JUNIT_SELECTIONS)
        + sum(PG_COUNTS[key] for key in PG_COUNTS if key.startswith("pg_"))
        + JUNIT_COUNTS["selection_static12"]
        == 337
    )
    assert (
        sum(PG_COUNTS[group] for group in ("writer5", "admission9", "history9", "guards9"))
        + JUNIT_COUNTS["selection_static12"]
        == 44
    )
    assert (
        sum(JUNIT_COUNTS[group] for group in original_junit if group != "selection_static12")
        + sum(
            PG_COUNTS[group]
            for group in (
                "metadata_sync",
                "metadata_outbox",
                "metadata_relations",
                "service_bridge",
            )
        )
        == 210
    )
    assert (
        sum(
            PG_COUNTS[group]
            for group in (
                "decision7",
                "mismatch_a7",
                "mismatch_b7",
                "storage6",
                "atomic8",
                "races5",
            )
        )
        + JUNIT_COUNTS["selection_static12"]
        == 52
    )
    assert combined.EXISTING_BRANCH == "refs/heads/codex/quote-existing-integration-checks"
    assert combined.EXISTING_WORKFLOW == ".github/workflows/quote-existing-integration-checks.yml"
    assert (*EXISTING_JUNIT_SELECTIONS, "selection_static12") == combined.EXISTING_GROUPS
    assert combined.ORACLE_BRANCH == "refs/heads/codex/quote-oracle-adapter-checks"
    assert combined.ORACLE_WORKFLOW == ".github/workflows/quote-oracle-adapter-checks.yml"
    assert combined.ORACLE_GROUPS == (
        "sqlite_single_pass26",
        "sqlite_codec15",
        "sqlite_bytes_reads25",
        "selection_static12",
    )
    assert sum(JUNIT_COUNTS[group] for group in combined.ORACLE_GROUPS) == 78
    assert (
        tuple(key for key in EXISTING_JUNIT_SELECTIONS if key.startswith("sqlite_"))
        == combined.SQLITE_GROUPS
    )
    assert combined.SEMANTIC_FORMAT_BRANCH == "refs/heads/codex/quote-semantic-format-checks"
    assert combined.SEMANTIC_FORMAT_WORKFLOW == ".github/workflows/quote-semantic-format-checks.yml"
    assert combined.SEMANTIC_STYLE_BRANCH == "refs/heads/codex/quote-semantic-style-checks"
    assert combined.SEMANTIC_STYLE_WORKFLOW == ".github/workflows/quote-semantic-style-checks.yml"
    assert combined.SEMANTIC_BRANCH == "refs/heads/codex/quote-semantic-closure-checks"
    assert combined.SEMANTIC_WORKFLOW == ".github/workflows/quote-semantic-closure-checks.yml"
    assert combined.LOADER_BRANCH == "refs/heads/codex/quote-loader-writer-checks"
    assert combined.LOADER_WORKFLOW == ".github/workflows/quote-loader-writer-checks.yml"
    monkeypatch.chdir(ROOT)
    for key, value in (
        ("GITHUB_EVENT_NAME", "push"),
        ("GITHUB_REPOSITORY", "synthetic/ocwp"),
        ("GITHUB_RUN_ID", "123"),
        ("GITHUB_RUN_NUMBER", "1"),
        ("GITHUB_RUN_ATTEMPT", "1"),
        ("GITHUB_SHA", "a" * 40),
        ("RUNNER_TEMP", str(tmp_path)),
    ):
        monkeypatch.setenv(key, value)
    branches = (
        (combined.BRANCH, combined.WORKFLOW),
        (combined.STYLE_BRANCH, combined.STYLE_WORKFLOW),
        (combined.FORMAT_BRANCH, combined.FORMAT_WORKFLOW),
        (combined.LOADER_BRANCH, combined.LOADER_WORKFLOW),
        (combined.LOADER_STATIC_BRANCH, combined.LOADER_STATIC_WORKFLOW),
        (combined.LOADER_FORMAT_BRANCH, combined.LOADER_FORMAT_WORKFLOW),
        (combined.SEMANTIC_BRANCH, combined.SEMANTIC_WORKFLOW),
        (combined.SEMANTIC_STYLE_BRANCH, combined.SEMANTIC_STYLE_WORKFLOW),
        (combined.SEMANTIC_FORMAT_BRANCH, combined.SEMANTIC_FORMAT_WORKFLOW),
        (combined.EXISTING_BRANCH, combined.EXISTING_WORKFLOW),
        (combined.ORACLE_BRANCH, combined.ORACLE_WORKFLOW),
    )
    for group, module in modules.items():
        for branch, workflow in branches:
            monkeypatch.setenv("GITHUB_REF", branch)
            monkeypatch.setenv("GITHUB_WORKFLOW_REF", f"synthetic/ocwp/{workflow}@{branch}")
            accepted = (
                (
                    branch == combined.BRANCH
                    and group in original_junit
                    and group != "selection_static12"
                )
                or (
                    branch
                    in (
                        combined.STYLE_BRANCH,
                        combined.FORMAT_BRANCH,
                        combined.LOADER_STATIC_BRANCH,
                        combined.LOADER_FORMAT_BRANCH,
                        combined.SEMANTIC_STYLE_BRANCH,
                        combined.SEMANTIC_FORMAT_BRANCH,
                    )
                    and group == "static6"
                )
                or (
                    branch in (combined.LOADER_BRANCH, combined.SEMANTIC_BRANCH)
                    and group == "selection_static12"
                )
                or (branch == combined.EXISTING_BRANCH and group in combined.EXISTING_GROUPS)
                or (branch == combined.ORACLE_BRANCH and group in combined.ORACLE_GROUPS)
            )
            if accepted:
                module.gate()
            else:
                with pytest.raises(module.Refusal):
                    module.gate()
            for _, foreign_workflow in branches:
                if foreign_workflow != workflow:
                    monkeypatch.setenv(
                        "GITHUB_WORKFLOW_REF", f"synthetic/ocwp/{foreign_workflow}@{branch}"
                    )
                    with pytest.raises(module.Refusal):
                        module.gate()
