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
    assert "current_checkpoint: m2_tls_certificate_repair_20261103" in state
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
