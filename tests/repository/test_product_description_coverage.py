"""Plan coverage contracts; these tests never qualify product behavior."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/10-spec-development"
MATRIX = BASE / "product-description-coverage.json"
MASTER = (
    BASE
    / "open-cycling-workshop-platform-phase-10-spec-development-master-execution-system-v0.1.md"
)
CLAIMS = {
    "open_source",
    "offline_first",
    "modular",
    "white_label",
    "business_profiles",
    "customers",
    "bicycles",
    "service_orders",
    "mechanics",
    "inventory",
    "sales",
    "purchases",
    "communication",
    "documentation",
    "scheduling",
    "staff",
    "metrics",
    "automation",
    "accessibility",
    "multiplatform",
}


def matrix() -> dict:
    return json.loads(MATRIX.read_text())


def test_description_has_complete_unique_planning_coverage() -> None:
    data = matrix()
    assert data["schema"] == 1
    assert data["coverage_kind"] == "planning_not_product_completion"
    assert data["source_commit"] == "7cf38e17e1981607287b0d5a41abedeead3bcf5e"
    rows = data["claims"]
    assert len(rows) == len(CLAIMS)
    assert {row["id"] for row in rows} == CLAIMS
    for row in rows:
        assert row["product_status"] in {"partial", "planned", "blocked"}
        assert row["requirements"] and row["tasks"] and row["acceptance"]
        assert row["remaining"] and row["evidence_paths"] and row["stage"]
        assert len(row["acceptance"]) >= 2


def test_references_and_task_dependencies_are_real_and_acyclic() -> None:
    data = matrix()
    master = MASTER.read_text()
    for row in data["claims"]:
        for ref in row["requirements"]:
            path, token = ref.split("#", 1)
            assert token in (ROOT / path).read_text(), ref
        for task in row["tasks"]:
            assert f"| {task} " in master, task
        for path in row["evidence_paths"]:
            assert (ROOT / path).exists(), path
    canonical = {}
    for line in master.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 7 and re.fullmatch(r"R\d{2}-T\d{3}", cells[1]):
            assert cells[1] not in canonical
            canonical[cells[1]] = re.findall(r"R\d{2}-T\d{3}", cells[4])
    new = data["added_tasks"]
    assert set(new) == {f"R02-T{number:03}" for number in range(24, 30)}
    for task, dependencies in new.items():
        assert dependencies and task not in dependencies
        assert dependencies == canonical[task]
        assert f"| {task} " in master
        for dependency in dependencies:
            assert f"| {dependency} " in master

    def visit(task: str, visiting: set[str]) -> None:
        assert task not in visiting, f"cycle at {task}"
        for dependency in canonical.get(task, []):
            visit(dependency, visiting | {task})

    for task in canonical:
        visit(task, set())
    assert "R02-T029 proves the workshop scheduling/staff subset only" in master
    assert "does not close\nFR-BIZ-003" in master


def test_new_requirements_are_unique_and_referenced() -> None:
    data = matrix()
    text = (ROOT / data["supplement"]).read_text()
    ids = re.findall(r"^- `(FR-(?:SCH|STF|MET|DOC|BIZ)-\d{3})`", text, re.M)
    assert len(ids) == len(set(ids)) == 24
    referenced = {ref.split("#", 1)[1] for row in data["claims"] for ref in row["requirements"]}
    assert set(ids) <= referenced
    assert "nómina" in text and "no incluye" in text
    assert "provisional" in text and "UTC" in text


def test_planning_is_discoverable_without_completing_release_gates() -> None:
    path = "docs/10-spec-development/2026-11-02-product-description-alignment.md"
    for source in ("README.md", "AGENTS.md", "MANUAL-ACTIONS-CHECKLIST.md"):
        assert path in (ROOT / source).read_text()
    state = (BASE / "execution-state.yaml").read_text()
    assert "product_description_alignment_20261102:" in state
    assert "active_release: V0.1" in state
    assert "R01_T035: blocked" in state
    assert "historical_cleanup_41011497919: UNKNOWN" in state
    assert "runtime_implementation: unchanged" in state
    assert "PR79: merged_candidate_qualified_fresh_main_pending" in state


def test_cross_cutting_claims_retain_security_and_truthfulness_boundaries() -> None:
    text = (BASE / "2026-11-02-product-description-alignment.md").read_text()
    for token in (
        "online-only",
        "AGPL-3.0-only",
        "WCAG 2.2 AA",
        "no automatic replay",
        "M0",
        "M1",
        "not a plugin runtime",
        "not full white label",
        "R01-T035",
        "UNKNOWN",
        "SPENT",
        "PR79",
        "planning coverage",
    ):
        assert token in text
