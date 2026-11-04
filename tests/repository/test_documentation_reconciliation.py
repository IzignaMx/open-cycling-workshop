"""Bounded documentation contracts, not runtime or release qualification."""

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "docs/10-spec-development/"
RECORD = BASE + "2026-11-01-documentation-reconciliation.md"
MASTER = (
    BASE
    + "open-cycling-workshop-platform-phase-10-spec-development-master-execution-system-v0.1.md"
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_historical_checkpoint_preserves_source_and_unqualified_gates() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "\ndocumentation_reconciliation_20261101:\n" in state
    assert "  accepted_baseline: cdb44aac572df65489fb95a15c0a813cd5445d95" in state
    assert f"  evidence: {RECORD}" in state
    record = read(RECORD)
    for token in (
        "cdb44aac572df65489fb95a15c0a813cd5445d95",
        "41225378078",
        "13052328859",
        "T1\u2013T8",
        "R01-T035",
        "40927223929",
        "41011497919",
        "UNKNOWN",
        "reconstruction",
        "not byte-identical",
        "second environment replacement",
    ):
        assert token in record
    assert "active_release: V0.1\n" in state
    assert "status: partial\n" in state


def test_local_plan_ids_do_not_impersonate_canonical_tasks() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("v02_plan:\n", 1)[1].split("v02_increment_1_evidence:", 1)[0]
    assert not re.search(r"^    R02-T\d{3}:", block, re.M)
    assert re.findall(r"^    W02-I1-T(\d{3}):", block, re.M) == [f"{i:03}" for i in range(1, 11)]
    assert "canonical_completion_not_implied" in block


def test_traceability_has_real_sources_tests_and_evidence() -> None:
    path = ROOT / BASE / "traceability.csv"
    assert path.is_file(), "bounded traceability ledger missing"
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    assert set(rows[0]) == {
        "requirement_id",
        "requirement_source",
        "release",
        "epic",
        "task_id",
        "test_id",
        "status",
        "evidence",
    }
    master = read(MASTER)
    for row in rows:
        assert all(row.values())
        assert row["requirement_id"] in read(row["requirement_source"])
        assert row["task_id"] in master
        assert row["status"] in {"partial", "blocked", "verified"}
        assert (ROOT / row["test_id"].split("::", 1)[0]).is_file()
        assert (ROOT / row["evidence"]).is_file()
    assert len({(r["requirement_id"], r["task_id"]) for r in rows}) == len(rows)
    assert all(r["status"] != "verified" for r in rows if r["release"] == "V0.2")
    assert any(r["task_id"] == "R01-T035" and r["status"] == "blocked" for r in rows)


def test_readme_captures_are_historical_not_deployment() -> None:
    text = read("README.md")
    assert "Historical captures" in text
    assert "These captures match the application source at this documentation increment" not in text
    assert "3c6513d" in text
    assert "not an operational workshop deployment" in text


def test_checklist_current_receipt_does_not_replay_history() -> None:
    text = read("MANUAL-ACTIONS-CHECKLIST.md")
    assert RECORD in text
    assert "PR77" in text.split("## 2026-10-31", 1)[0]
    assert "Historical checkpoint — superseded for source qualification" in text


def test_license_task_has_actual_repository_evidence() -> None:
    assert read("LICENSE") == read("LICENSES/AGPL-3.0-only.txt")
    assert 'SPDX-License-Identifier = "AGPL-3.0-only"' in read("REUSE.toml")
    state = read(BASE + "execution-state.yaml")
    block = state.split("locally_verified_tasks:\n", 1)[1].split(
        "implemented_evidence_pending:", 1
    )[0]
    assert "  - R01-T002\n" in block
    assert "R01-T002" in read(RECORD)


def test_historical_capture_visit_checkpoint_preserves_authority_and_pending_proof() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "\ncapture_visit_continuity_20261102:\n" in state
    block = state.split("capture_visit_continuity_20261102:\n", 1)[1].split("\n\n", 1)[0]
    assert "status: planned" in block or "status: implemented_pending_evidence" in block
    assert "publication: not_authorized_for_this_package" in block
    assert "browser: pending_actual_execution" in block
    record = read(BASE + "2026-11-02-capture-visit-continuity.md")
    for token in ("b88c4eee78d0603bb47368bcec83cd9567eac495", "41372646038", "13110609454"):
        assert token in record
    for token in ("UNKNOWN", "40927223929", "R01-T035", "full reload", "not redownloaded"):
        assert token in record


def test_pr78_source_receipt_supersedes_not_deletes_pending_history() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "pr78_source_acceptance_20261102:" in state
    assert "  source_status: verified" in state
    assert "  prior_source_receipt: pr78_source_acceptance_20261102" in state
    assert "  new_source_hosted: pending_exact_candidate_and_fresh_main" in state
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    assert "2026-11-02-capture-visit-continuity.md" in checklist
    assert "PR78" in checklist.split("## 2026-11-01", 1)[0]


def test_capture_requirement_rows_retain_unique_partial_canonical_mappings() -> None:
    with (ROOT / BASE / "traceability.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for requirement, task in (("FR-CUS-001", "R01-T030"), ("FR-SVC-001", "R02-T005")):
        selected = [r for r in rows if (r["requirement_id"], r["task_id"]) == (requirement, task)]
        assert len(selected) == 1
        assert selected[0]["status"] == "partial"
        assert selected[0]["test_id"] == "apps/web/e2e/capture-reload-recovery.spec.ts"
        assert selected[0]["evidence"] == BASE + "2026-11-02-capture-reload-recovery.md"


def test_historical_reload_checkpoint_separates_publication_from_acceptance() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "\ncapture_reload_recovery_20261102:\n" in state
    block = state.split("capture_reload_recovery_20261102:\n", 1)[1].split("\n\n", 1)[0]
    assert "status: in_progress" in block or "status: implemented_pending_evidence" in block
    assert "publication: authorized_draft_PR81_published_corrective_CI_pending" in block
    assert "integration: only_after_full_pass_and_review_then_fresh_main" in block
    record = read(BASE + "2026-11-02-capture-reload-recovery.md")
    for token in (
        "24 hours",
        "first successful persistence",
        "not sliding",
        "PROTECTED",
        "not redownloaded",
        "07:25",
        "full crash",
        "40927223929",
        "UNKNOWN",
    ):
        assert token in record
    assert "OFF-007" in record and "partial" in record


def test_pr79_pr80_acceptance_is_separate_from_new_reload_source() -> None:
    state = read(BASE + "execution-state.yaml")
    for receipt in ("pr79_source_acceptance_20261102", "pr80_source_acceptance_20261102"):
        assert receipt + ":" in state
    record = read(BASE + "2026-11-02-capture-reload-recovery.md")
    for token in ("41391295843", "41399878499", "02ec2f059e610768cb58ce20812fed33999bfa7a"):
        assert token in record
    assert "historical_pending_fields" in state
    assert "fresh_main: pending_separate_exact_source_qualification" in state


def test_quote_v8_reservation_is_explicitly_nonbinding_not_quote_activation() -> None:
    text = read("docs/superpowers/plans/2026-09-01-v0.2-increment-2-budgets-inventory.md")
    assert "future quotes reserve SQL `0012` / local `8`" in text
    assert "Nonbinding historical local-v8 reservation" in text
    assert "capture-reload-recovery" in text
    assert "does not implement quote storage" in text


def test_historical_m1_checkpoint_is_partial_and_has_separate_publication_authority() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_pending_fields: superseded_by_pr82_source_acceptance_20261102" in state
    block = state.split("official_module_reference_20261102:\n", 1)[1].split("\n\n", 1)[0]
    assert "publication: separately_authorized_PR82_draft_corrective_CI_pending" in block
    assert "canonical_SDK_tasks: prerequisite_only_not_complete" in block
    record = read(BASE + "2026-11-02-official-module-reference.md")
    for token in (
        "FR-PLG-003",
        "FR-PLG-005",
        "FR-PLG-008",
        "FR-PLG-009",
        "R09-T020",
        "R10-T014",
        "R01-T035",
        "UNKNOWN",
        "40927223929",
        "not a plugin runtime",
    ):
        assert token in record


def test_pr81_final_receipt_does_not_rewrite_failed_history() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "pr81_source_acceptance_20261102:" in state
    assert "prior_failed_ci: [41413376026, 41423509534]" in state
    record = read(BASE + "2026-11-02-official-module-reference.md")
    for token in (
        "41439571738",
        "aa432060aedd170e6d52bb93004fbc79f33953bb",
        "libfile_84d64ec919e08191bc56f9170456edde",
        "stale PR body",
        "not redownloaded",
    ):
        assert token in record


def test_m1_static_offline_metadata_does_not_grant_operational_offline_support() -> None:
    strategy = read("docs/08-open-source/2026-10-27-compatible-modules.md")
    assert "M1 host-only metadata clarification" in strategy
    assert "not operational offline support" in strategy
    assert "M0 is already source-qualified" in strategy
    with (ROOT / BASE / "traceability.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for requirement, task in (
        ("FR-PLG-003", "R09-T020"),
        ("FR-PLG-005", "R09-T020"),
        ("FR-PLG-008", "R09-T020"),
        ("FR-PLG-009", "R09-T020"),
        ("FR-PLG-009", "R10-T014"),
    ):
        selected = [r for r in rows if (r["requirement_id"], r["task_id"]) == (requirement, task)]
        assert len(selected) == 1
        assert selected[0]["status"] == "partial"
        assert selected[0]["evidence"] == BASE + "2026-11-02-official-module-reference.md"


def test_m2_local_laboratory_does_not_claim_runtime_or_production_admission() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "m2_synthetic_laboratory_20261102:" in state
    block = state.split("m2_synthetic_laboratory_20261102:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "status: partial_local_functional_only",
        "publication: not_authorized",
        "runtime: blocked_no_Docker_or_PostgreSQL",
        "production_access: none",
    ):
        assert token in block
    record = read(BASE + "2026-11-02-m2-synthetic-laboratory.md")
    for token in (
        "SQLite",
        "ASGI",
        "not PostgreSQL",
        "not a separate-process",
        "R01-T035",
        "UNKNOWN",
        "SPENT",
        "41463493290",
        "27/27",
        "e9c11ad11a564c80add99f4dc901ffe2d583c8e6",
        "SEC-002",
        "FR-PLG-008",
    ):
        assert token in record


def test_m2_hosted_preparation_keeps_execution_and_physical_gates_open() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "m2_tls_certificate_repair_20261103:" in state
    block = state.split("m2_hosted_preparation_20261102:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "status: local_preparation_runtime_unqualified",
        "production_changes: none",
        "actual_PostgreSQL_TLS_process_execution: not_performed",
        "publication_and_execution: require_separate_explicit_approval",
        "V01_physical_and_release_gates: unchanged_partial",
        "build_disk_peak: inherited_runner_capacity_not_separate_hard_quota",
    ):
        assert token in block
    record = read(BASE + "2026-11-02-m2-hosted-preparation.md")
    for token in (
        "SPENT",
        "UNKNOWN",
        "T1\u2013T8",
        "not a hard quota",
        "not secure erasure",
        "same-repository PR",
        "database_cleanup_complete",
        "15-minute",
    ):
        assert token in record


def test_m2_diagnostics_preserves_failed_attempts_and_authority_boundary() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("m2_incremental_diagnostics_20261102:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "status: local_implementation_runtime_unqualified",
        "third_runtime: failed_cause_UNKNOWN",
        "third_cleanup: verified_current_attempt_only",
        "publication_fourth_attempt_merge: not_authorized",
        "production_changes: none",
    ):
        assert token in block
    record = read(BASE + "2026-11-02-m2-incremental-diagnostics.md")
    for token in (
        "41518365154",
        "41527723967",
        "41541751810",
        "41541751816",
        "5851",
        "58",
        "27/27",
        "UNKNOWN",
        "not secure erasure",
        "all-or-nothing",
        "closed",
        "1 MiB",
        "one day",
        "no fourth attempt",
        "SPENT",
        "T1\u2013T8",
    ):
        assert token in record


def test_m2_local_certificate_repair_keeps_hosted_cause_unproven() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "m2_tls_certificate_repair_20261103:" in state
    block = state.split("m2_tls_certificate_repair_20261103:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "fourth_hosted_cause: UNKNOWN",
        "offline_current_CA: strict_error92_missing_key_usage",
        "offline_explicit_CA: strict_verification_passed",
        "offline_cleanup: verified",
        "publication_fifth_attempt_merge: not_authorized",
    ):
        assert token in block
    record = read(BASE + "2026-11-02-m2-incremental-diagnostics.md")
    for token in (
        "41552838556",
        "41552838539",
        "5954",
        "error92",
        "OpenSSL3.5.7",
        "not the hosted root cause",
    ):
        assert token in record


def test_m2_acceptance_checkpoint_separates_tree_qualified_lab_and_fresh_main() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_m2_acceptance_checkpoint: m2_laboratory_acceptance_20261103" in state
    block = state.split("m2_laboratory_acceptance_20261103:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "status: bounded_synthetic_lab_accepted_full_M2_incomplete",
        "main: 35f88e0f2a9a9e7b0f0dece03498cc6265205b91",
        "tree: 106e11df74b4e656c4b6227610648b3466c3e436",
        "fifth_M2_run: 41568644741",
        "fresh_main_CI: 41656497568",
        "sixth_M2_run: not_authorized_not_executed",
        "next_proposal_implementation_authority: not_granted",
        "first_hosted_failure: known_image_preparation_BuildKit_boundary",
        "second_third_fourth_hosted_causes: UNKNOWN_unchanged",
        "first_second_cleanup: unproven_historical",
        "V01_physical_and_release_gates: unchanged_partial",
    ):
        assert token in block
    assert (
        "historical_completed_lab_active_plan: "
        "docs/superpowers/plans/2026-11-02-m2-hosted-preparation.md"
    ) in state


def test_m2_acceptance_record_binds_receipts_without_claiming_full_release() -> None:
    record = read(BASE + "2026-11-03-m2-laboratory-acceptance.md")
    for token in (
        "35f88e0f2a9a9e7b0f0dece03498cc6265205b91",
        "106e11df74b4e656c4b6227610648b3466c3e436",
        "40740e51b1d24d04af49479b24d2eb0d01483d24",
        "cabae2c7b36dff39d32b2a70c5e52b35aa10466e864ca6fcc2e74a529fc01f58",
        "3d2f9274ce2df1ee5638b4b0f7bc548d2c567729a1164a10f4a6fdafd5167463",
        "2997aafa6be6e674d813560c62c35778b629cfc46d1b91efcf6a1054515fafd0",
        "b555bf1aada493bebabdd900823a5d296ed54c55667c79f2402774c1ad5adfe0",
        "27/27",
        "5971",
        "58",
        "1237",
        "126",
        "20/9/5/10",
        "kernel 14",
        "not downloaded",
        "not tracked repository files",
        "not secure erasure",
        "full M2 remains incomplete",
        "R09-T020",
        "R10-T014",
        "T1\u2013T8",
        "R01-T035",
        "SPENT40927223929",
        "UNKNOWN41011497919",
        "Pages",
        "first and second",
        "no sixth",
    ):
        assert token in record
    for run in (41568644741, 41656497568, 41656497424, 41656497409, 41656497803):
        assert f"https://github.com/IzignaMx/open-cycling-workshop/actions/runs/{run}" in record


def test_checklist_supersedes_historical_permissions_without_rewriting_them() -> None:
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    current = checklist.split("## 2026-11-03 · PR83 accepted bounded laboratory and fresh main", 1)[
        1
    ].split("\n## ", 1)[0]
    assert "full M2 remains incomplete" in current
    assert "no sixth" in current
    assert "5971" in current and "27/27" in current
    assert "Historical source-stage snapshots" in checklist
    assert "Obtain separate publication and single-run permission before a fifth" in checklist


def test_selected_restore_policy_keeps_runtime_and_authority_gates_closed() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_restore_policy_checkpoint: m2_restore_policy_20261103" in state
    block = state.split("m2_restore_policy_20261103:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "policy: explicit_fresh_connector_enrollment_after_database_restore",
        "ordinary_service_restart: not_restore_no_destructive_reenrollment_or_incarnation_rotation",
        "production_machine_authority: absent_implementation_pending",
        "authority_characterization: fake_SQL_control_flow_only_not_native_PostgreSQL_restore",
        "native_restore_qualification: not_established",
        "sixth_M2_run: not_authorized_not_executed",
        "publication: not_authorized_for_this_local_increment",
        "V01_physical_and_release_gates: unchanged_partial",
    ):
        assert token in block
    design = block.split("  design: ", 1)[1].splitlines()[0]
    assert (ROOT / design).is_file()


def test_pr84_main_receipt_is_separate_from_local_policy_characterization() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("pr84_fresh_main_acceptance_20261103:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "main: c0fe501a9f93393c106c49aece4a27af495b79e9",
        "tree: bbb9b6e4d140c96df54ee18ac4890f64a4a4be51",
        "CI: 41713827892",
        "counts: 27_of27_Python5974_plus58_exact_skips_frontend1237_API1",
        "large_browser_archives: not_downloaded_not_byte_trace_or_screenshot_reviewed",
        "ec46275af1fa1fda87c19be9bc2200638020dca6ec891f3d5a0298ef86d7f8ef",
    ):
        assert token in block
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    current = checklist.split(
        "## 2026-11-03 · Selected restore policy, local characterization only", 1
    )[1]
    current = current.split("\n## ", 1)[0]
    assert "Ordinary service restart is not database restoration" in current
    assert "fake SQL" in current and "not native PostgreSQL restore proof" in current
    assert "production machine authority remains absent" in current
    assert "no sixth" in current


def test_customer_limits_checkpoint_preserves_admission_and_evidence_boundary() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_customer_limits_checkpoint: customer_field_limits_20261104" in state
    assert "historical_customer_limits_last_checkpoint: customer_field_limits_20261104" in state
    assert "customer_field_limits_20261104:\n" in state
    block = state.split("customer_field_limits_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "status: locally_validated_independently_reviewed_hosted_pending",
        "local_Python_scope: before_final_documentation_stamp_only",
        "native_browser: three_new_cases_thirteen_file_cases_collected_zero_executed",
        "requirement: FR-CUS-001",
        "canonical_task: R01-T030",
        "normalization: unchanged_no_truncation_codepoint_limits",
        "runtime_qualification: pending_not_inherited_from_PR85",
        "publication: not_authorized",
        "seventh_M2_run: not_authorized",
    ):
        assert token in block
    assert (ROOT / block.split("  evidence: ", 1)[1].splitlines()[0]).is_file()
    record = read(BASE + "2026-11-04-customer-field-limits.md")
    for token in ("200", "320", "64", "FR-CUS-001", "R01-T030", "no truncation"):
        assert token in record


def test_pr85_main_receipt_does_not_qualify_customer_fix() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "pr85_fresh_main_acceptance_20261104:\n" in state
    block = state.split("pr85_fresh_main_acceptance_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "4b3b886c0f9c91b3732595b44db926b6fcf6bbf9",
        "6a1e9d2a1a3f9c28b7c42a4f1c109652645f6954",
        "41757541938",
        "5987",
        "04aad320c1fc887fd6436fd518c40952c378a8dcaf93ac6d12087af2bb79283d",
        "large_browser_archives: not_downloaded_not_byte_trace_or_screenshot_reviewed",
    ):
        assert token in block


def test_customer_admissibility_checkpoint_preserves_new_command_scope() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_customer_admissibility_checkpoint: customer_admissibility_20261104" in state
    assert (
        "historical_customer_admissibility_last_checkpoint: customer_admissibility_20261104"
        in state
    )
    block = state.split("customer_admissibility_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "requirement: FR-CUS-001",
        "canonical_task: R01-T030",
        "status: locally_validated_independently_reviewed_hosted_pending",
        "local_Python_scope: before_final_documentation_stamp_only",
        "local_Python: 5432_passed_671_environment_skips_12_warnings_384_99s_exit0",
        "native_browser: one_new_case_fourteen_file_cases_collected_zero_executed",
        "normalization: existing_prepared_values_unchanged_no_truncation",
        "replay: historical_receipt_first_unchanged",
        "nullable_contacts: explicit_null_clears_omission_preserves",
        "create_unknown_keys: compatibility_unchanged",
        "publication: not_authorized",
        "runtime_qualification: pending_not_inherited_from_PR86",
        "physical_capacity_SPENT_UNKNOWN_Pages: unchanged",
    ):
        assert token in block
    evidence = block.split("  evidence: ", 1)[1].splitlines()[0]
    assert "historical_customer_admissibility_plan: " + evidence in state
    assert (ROOT / evidence).is_file()


def test_customer_admissibility_record_bounds_projection_and_evidence() -> None:
    record = read(BASE + "2026-11-04-customer-admissibility.md")
    for token in (
        "FR-CUS-001",
        "R01-T030",
        "FR-CUS-002",
        "R02-T001",
        "Python whitespace",
        "U+0085",
        "U+001C",
        "U+FEFF",
        "existing prepared values",
        "receipt-first",
        "explicit null",
        "omission",
        "unknown keys",
        "NoReferencedTableError",
        "not valid behavioral RED",
        "native browser",
        "not PostgreSQL",
        "SPENT40927223929",
        "UNKNOWN41011497919",
        "R01-T035",
    ):
        assert token in record
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    section = checklist.split("## 2026-11-04 · Customer command admissibility", 1)[1]
    section = section.split("\n## ", 1)[0]
    assert "not search or V0.2 completion" in section
    assert "No publication" in section


def test_pr86_main_acceptance_does_not_qualify_admissibility_candidate() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("pr86_fresh_main_acceptance_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "23def8f45bc02e16b9f7f0b3263ed34f97a2da02",
        "409a61aa3a33e4f4c3ad19a03cd572c64c052599",
        "41780887753",
        "6004",
        "1246",
        "b32b210d3ab0c28895b1d9f11b79cc7f290e40c9a9cc0fe6c88bf5501ee5636c",
        "large_browser_archives: not_downloaded_not_byte_trace_or_screenshot_reviewed",
        "status: accepted_baseline_not_admissibility_candidate_evidence",
    ):
        assert token in block


def test_intake_admissibility_is_existing_integrity_prerequisite_not_release_expansion() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "historical_intake_admissibility_checkpoint: intake_admissibility_20261104" in state
    assert "historical_intake_admissibility_last_checkpoint: intake_admissibility_20261104" in state
    block = state.split("intake_admissibility_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "canonical_pairs: FR-BIK-003_R02-T002_and_FR-SVC-001_R02-T005",
        "admission: existing_shipped_integrity_prerequisite_V01_physical_partial",
        "limits: bicycle120_120_60_30_2000_priority30_codepoints",
        "status: locally_validated_independently_reviewed_hosted_pending",
        "local_Python: 5510_passed_671_environment_skips_12_warnings_395_46s_exit0",
        "local_Python_scope: before_final_documentation_stamp_only",
        "native_browser: two_new_cases_sixteen_file_cases_collected_zero_executed",
        "normalization: existing_prepared_values_unchanged_no_truncation",
        "replay: historical_receipt_first_unchanged",
        "priority: omitted_defaults_normal_supplied_null_or_nonstring_rejected_"
        "frontend_blank_default_unchanged",
        "excluded: REST_only_order_Text_caps_transition_notes_ID_authority",
        "runtime_qualification: pending_not_inherited_from_PR87",
        "publication: not_authorized",
        "physical_capacity_SPENT_UNKNOWN_Pages: unchanged",
    ):
        assert token in block
    evidence = block.split("  evidence: ", 1)[1].splitlines()[0]
    assert "historical_intake_admissibility_plan: " + evidence in state
    assert (ROOT / evidence).is_file()


def test_intake_record_preserves_atomicity_defaults_and_evidence_limits() -> None:
    record = " ".join(read(BASE + "2026-11-04-intake-admissibility.md").split())
    for token in (
        "FR-BIK-003",
        "R02-T002",
        "FR-SVC-001",
        "R02-T005",
        "not R01-T030",
        "Python whitespace",
        "120/120/60/30/2000",
        "priority",
        "omission",
        "explicit null",
        "receipt-first",
        "no orphan",
        "per-item",
        "Text",
        "transition notes",
        "four real-controller",
        "not native PostgreSQL",
        "existing priority UI allowlist",
        "SPENT40927223929",
        "UNKNOWN41011497919",
        "R01-T035",
    ):
        assert token in record
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    assert "## 2026-11-04 · Existing intake admissibility prerequisite" in checklist


def test_pr87_acceptance_is_historical_not_intake_candidate_qualification() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("pr87_fresh_main_acceptance_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "2f9abe5c8e74887177882032c8ba474f6e9bf761",
        "a64e063d9ae91c36b53286d9e62e9f8b73b9af29",
        "41793841607",
        "6045",
        "1256",
        "1595e284d9c1079647b636ede9c4b48b9d9c9ec3640a4a7904512cc8f730f43b",
        "large_browser_archives: not_downloaded_not_byte_trace_or_screenshot_reviewed",
    ):
        assert token in block


def test_local_customer_lookup_is_bounded_partial_prerequisite() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "current_checkpoint: local_customer_lookup_20261104" in state
    assert "last_checkpoint: local_customer_lookup_20261104" in state
    block = state.split("local_customer_lookup_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "canonical_pair: FR-CUS-002_R02-T001_partial",
        "admission: S2_existing_picker_local_read_prerequisite_V01_physical_partial",
        "status: locally_validated_independently_reviewed_hosted_pending",
        "local_Python: 5513_passed_671_environment_skips_12_warnings_389_21s_exit0",
        "local_Python_scope: frozen_product_before_final_documentation_stamp",
        "native_browser: one_case_collected_typechecked_zero_executed",
        "scan: one_existing_kernel_page50_per_explicit_action",
        "query: volatile_case_insensitive_name_substring_only",
        "selection: explicit_ID_stable_authorized_no_auto_first",
        "completeness: local_cursor_only_not_global_snapshot_or_all_server_customers",
        "excluded: contact_ID_tag_search_index_schema_API_storage_authority",
        "runtime_qualification: pending_not_inherited_from_PR88",
        "publication: not_authorized",
        "physical_capacity_SPENT_UNKNOWN_Pages: unchanged",
    ):
        assert token in block
    evidence = block.split("  evidence: ", 1)[1].splitlines()[0]
    assert "active_plan: " + evidence in state
    assert (ROOT / evidence).is_file()


def test_lookup_record_requires_cursor_authority_and_honest_completeness() -> None:
    record = " ".join(read(BASE + "2026-11-04-local-customer-lookup.md").split())
    for token in (
        "FR-CUS-002",
        "R02-T001",
        "S2",
        "50",
        "zero matches",
        "returned cursor",
        "explicit continuation",
        "restart",
        "volatile",
        "no global snapshot",
        "not all server customers",
        "selected customer",
        "draft",
        "generation",
        "no automatic first selection",
        "contact",
        "tags",
        "R01-T035",
        "SPENT40927223929",
        "UNKNOWN41011497919",
    ):
        assert token in record
    checklist = read("MANUAL-ACTIONS-CHECKLIST.md")
    assert "## 2026-11-04 · Bounded local customer-name lookup" in checklist


def test_pr88_baseline_acceptance_does_not_qualify_new_lookup() -> None:
    state = read(BASE + "execution-state.yaml")
    block = state.split("pr88_fresh_main_acceptance_20261104:\n", 1)[1].split("\n\n", 1)[0]
    for token in (
        "5f5c0e3eab6af6693016781184e387d442106af9",
        "a5ff0e33250206d8f6ea8dc66a9df3d0ad79481a",
        "41810260574",
        "6123",
        "1272",
        "ed97f1fc5ec0af44cf8a5a5dd90d4e8a6ca6742acdafa2d90b6adb94b34b3255",
        "large_browser_archives: not_downloaded_not_byte_trace_or_screenshot_reviewed",
    ):
        assert token in block
