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


def test_current_capture_visit_checkpoint_preserves_authority_and_pending_proof() -> None:
    state = read(BASE + "execution-state.yaml")
    assert "current_checkpoint: capture_visit_continuity_20261102" in state
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
        assert selected[0]["test_id"] == "apps/web/e2e/capture-visit-continuity.spec.ts"
        assert selected[0]["evidence"] == BASE + "2026-11-02-capture-visit-continuity.md"
