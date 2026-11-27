"""Planning contracts only: these checks do not execute or qualify inventory."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/10-spec-development"
PLAN = BASE / "inventory-scope-plan.json"
MASTER = BASE / (
    "open-cycling-workshop-platform-phase-10-spec-development-master-execution-system-v0.1.md"
)
CANONICAL_TASKS = {
    *(f"R03-T{number:03}" for number in range(1, 18)),
    *(f"R04-T{number:03}" for number in range(1, 15)),
}
SCENARIOS = {
    "shared_stock_workshop_and_retail",
    "partial_purchase_receipts",
    "location_transfer",
    "physical_count",
    "nonstock_service",
    "last_unit_competition",
}


def plan() -> dict:
    assert PLAN.is_file(), "Inventory scope must have a machine-readable planning matrix"
    return json.loads(PLAN.read_text())


def canonical_dependencies() -> dict[str, list[str]]:
    result = {}
    for line in MASTER.read_text().splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 7 and re.fullmatch(r"R\d{2}-T\d{3}", cells[1]):
            assert cells[1] not in result
            result[cells[1]] = re.findall(r"R\d{2}-T\d{3}|V\d+\.\d+", cells[4])
    return result


def assert_reference(reference: str) -> None:
    path, separator, token = reference.partition("#")
    target = ROOT / path
    assert target.is_file(), reference
    if separator:
        assert token and token in target.read_text(), reference


def test_plan_keeps_current_release_and_evidence_boundaries() -> None:
    data = plan()
    assert data["schema"] == 1
    assert data["coverage_kind"] == "planning_not_product_completion"
    assert data["source_commit"] == "b49f10b1b21240c8682cf3a9ba7ca0f3c9ce4ea8"
    boundary = data["release_boundary"]
    assert boundary["active_release"] == "V0.1"
    assert boundary["active_release_status"] == "partial"
    assert boundary["planned_integration"] == ["V0.3", "V0.4"]
    for key in (
        "runtime_changed",
        "release_closed",
        "deployment_qualified",
        "physical_stock_verified",
    ):
        assert boundary[key] is False
    current = data["current_contract"]
    assert current["movement_kinds"] == ["ADJUST", "RESERVE", "RELEASE", "CONSUME"]
    assert current["quantity_type"] == "signed_int32"
    assert current["fractional_units_supported"] is False
    assert current["fractional_units_prerequisites"] == [
        "quantity_precision_adr",
        "validated_fixed_point",
        "precision_policy",
        "unit_conversion_policy",
        "versioned_contract",
        "migration",
    ]
    assert current["product_location_cardinality"] == 1
    assert current["stock_response"] == "available_quantity_only"
    assert current["inventory_ui"] == "connected_read_only"
    assert current["offline_inventory_commands"] is False


def test_every_inventory_requirement_retains_an_explicit_unfinished_scope() -> None:
    rows = plan()["requirements"]
    expected = {f"FR-INV-{number:03}" for number in range(1, 13)}
    assert len(rows) == len(expected)
    assert {row["id"] for row in rows} == expected
    partial = {"FR-INV-001", "FR-INV-002", "FR-INV-003", "FR-INV-004", "FR-INV-010"}
    for row in rows:
        assert row["implementation_state"] == ("partial" if row["id"] in partial else "planned")
        assert row["requirement_ref"].endswith(f"#{row['id']}")
        assert row["current"] and row["missing"] and row["source_evidence"]
        assert row["parent_tasks"] and row["acceptance"]
    compatibility = next(row for row in rows if row["id"] == "FR-INV-012")
    assert compatibility["parent_tasks"] == ["R03-T001", "R07-T004"]
    assert compatibility["later_stage"] == "V0.7"


def test_all_references_name_existing_sources_requirements_and_parent_tasks() -> None:
    data = plan()
    canonical = canonical_dependencies()
    for reference in data["source_refs"].values():
        assert_reference(reference)
    for row in data["requirements"]:
        assert_reference(row["requirement_ref"])
        for evidence in row["source_evidence"]:
            assert_reference(evidence)
        for task in row["parent_tasks"]:
            assert task in canonical, task
    for row in data["business_profiles"] + data["scenarios"]:
        for task in row["parent_tasks"]:
            assert task in canonical, task
    for profile in data["business_profiles"]:
        for reference in profile["requirement_refs"]:
            assert_reference(reference)


def test_task_coverage_matches_canonical_dependencies_without_advancing_releases() -> None:
    rows = plan()["task_matrix"]
    canonical = canonical_dependencies()
    assert len(rows) == len(CANONICAL_TASKS)
    assert {row["id"] for row in rows} == CANONICAL_TASKS
    for row in rows:
        task = row["id"]
        assert row["status"] == "planned_acceptance"
        assert row["release"] == ("V0.3" if task.startswith("R03-") else "V0.4")
        assert row["depends_on"] == canonical[task]
        assert row["acceptance"]
        assert len(row["depends_on"]) == len(set(row["depends_on"]))
        if task.startswith("R03-"):
            assert not any(dep.startswith("R04-") for dep in row["depends_on"])

    def visit(task: str, visiting: set[str], visited: set[str]) -> None:
        assert task not in visiting, f"dependency cycle at {task}"
        if task in visited or task.startswith("V"):
            return
        assert task in canonical
        for dependency in canonical[task]:
            visit(dependency, visiting | {task}, visited)
        visited.add(task)

    visited: set[str] = set()
    for task in canonical:
        visit(task, set(), visited)


def test_shared_stock_purchase_and_pos_dependencies_cannot_be_dropped_together() -> None:
    rows = {row["id"]: row for row in plan()["task_matrix"]}
    minimum = {
        "R03-T006": {"R03-T004", "R03-T005"},
        "R03-T009": {"R03-T008", "R03-T003", "R03-T005"},
        "R03-T011": {"R03-T002", "R03-T003", "R03-T004", "R03-T005", "V0.2"},
        "R03-T012": {"R03-T002", "R03-T004", "R03-T005"},
        "R03-T014": {"R03-T004", "R03-T005", "R03-T006", "R03-T010", "R03-T012", "R03-T013"},
        "R03-T015": {"R03-T002", "R03-T005", "R03-T009", "R03-T011", "R03-T012"},
        "R03-T016": {
            "R03-T004",
            "R03-T005",
            "R03-T009",
            "R03-T010",
            "R03-T011",
            "R03-T012",
            "R03-T015",
        },
        "R04-T006": {"R04-T003", "R04-T004", "R04-T007", "V0.3"},
        "R04-T007": {"R04-T003", "R03-T003", "R03-T004", "R03-T005"},
        "R04-T008": {"R04-T003", "R04-T004", "R04-T007", "R03-T011", "V0.2"},
        "R04-T011": {"R04-T004", "R04-T007", "R03-T015"},
        "R04-T014": {
            "R04-T005",
            "R04-T006",
            "R04-T007",
            "R04-T008",
            "R04-T009",
            "R04-T010",
            "R04-T012",
            "R04-T013",
            "R03-T016",
        },
    }
    for task, required in minimum.items():
        assert required <= set(rows[task]["depends_on"]), task


def test_four_business_profiles_do_not_issue_authority_or_discard_data() -> None:
    rows = plan()["business_profiles"]
    profiles = {row["id"]: row for row in rows}
    assert len(rows) == 4
    assert set(profiles) == {"workshop", "retail-only", "combined", "service-cooperative"}
    for row in rows:
        assert row["status"] == "planned_acceptance"
        assert row["grants_permissions"] is False
        assert row["discards_data_or_pending_work"] is False
        assert row["acceptance"] and row["parent_tasks"]
        assert {ref.rsplit("#", 1)[1] for ref in row["requirement_refs"]} == {
            "FR-BIZ-001",
            "FR-BIZ-002",
            "FR-BIZ-003",
        }
    assert profiles["workshop"]["requires_pos"] is False
    assert profiles["retail-only"]["requires_service_order"] is False
    assert profiles["retail-only"]["requires_bicycle"] is False
    assert profiles["combined"]["shared_product_identity"] is True
    service = profiles["service-cooperative"]
    assert service["inventory_optional"] is True
    assert service["requires_pos"] is False
    assert service["requires_service_order"] is False
    assert service["requires_bicycle"] is False


@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_planned_numeric_scenarios_distinguish_physical_holds_and_availability(
    scenario_id: str,
) -> None:
    scenarios = plan()["scenarios"]
    assert len(scenarios) == len(SCENARIOS)
    assert {row["id"] for row in scenarios} == SCENARIOS
    scenario = next(row for row in scenarios if row["id"] == scenario_id)
    assert scenario["status"] == "planned_acceptance"
    assert scenario["synthetic"] is True
    assert scenario["release"] in {"V0.3", "V0.4"}
    assert scenario["runtime_evidence"] is False
    if scenario_id == "nonstock_service":
        assert scenario["availability"] is None
        for key in ("inventory_movements", "physical_delta", "reservation_delta"):
            assert type(scenario[key]) is int
        assert scenario["inventory_movements"] == 0
        assert scenario["physical_delta"] == scenario["reservation_delta"] == 0
        return
    physical = {key: value["physical"] for key, value in scenario["initial"].items()}
    reserved = {key: value["reserved"] for key, value in scenario["initial"].items()}
    for location, initial in scenario["initial"].items():
        assert set(initial) == {"physical", "reserved", "available"}
        assert all(type(value) is int for value in initial.values())
        assert initial["available"] == physical[location] - reserved[location]
        assert physical[location] >= reserved[location] >= 0
    assert scenario["steps"]
    received = 0
    for step in scenario["steps"]:
        assert set(step["deltas"]) <= set(physical)
        for location, delta in step["deltas"].items():
            assert type(delta["physical"]) is type(delta["reserved"]) is int
            physical[location] += delta["physical"]
            reserved[location] += delta["reserved"]
        assert set(step["expected"]) == set(physical)
        for location, expected in step["expected"].items():
            assert all(type(value) is int for value in expected.values())
            assert physical[location] >= reserved[location] >= 0
            assert expected == {
                "physical": physical[location],
                "reserved": reserved[location],
                "available": physical[location] - reserved[location],
            }
        if scenario_id == "location_transfer":
            assert type(scenario["conserved_physical"]) is int
            assert sum(delta["physical"] for delta in step["deltas"].values()) == 0
            assert sum(physical.values()) == scenario["conserved_physical"]
        if scenario_id == "partial_purchase_receipts":
            assert type(scenario["ordered"]) is int
            assert type(step["received_delta"]) is type(step["expected_received"]) is int
            received += step["received_delta"]
            assert received == step["expected_received"]
            assert 0 <= received <= scenario["ordered"]
            assert sum(physical.values()) == received
    if scenario_id == "shared_stock_workshop_and_retail":
        billing = next(step for step in scenario["steps"] if step["event"] == "bill_consumed_order")
        assert billing["deltas"] == {"A": {"physical": 0, "reserved": 0}}
        assert scenario["shared_product_identity"] is True
    if scenario_id == "physical_count":
        assert type(scenario["counted_physical"]) is int
        assert physical["A"] == scenario["counted_physical"]
        assert scenario["ledger_rewritten"] is False
    if scenario_id == "last_unit_competition":
        rejected = next(
            step for step in scenario["steps"] if step["event"] == "competing_retail_sale_rejected"
        )
        assert rejected["deltas"] == {"A": {"physical": 0, "reserved": 0}}
        assert rejected["expected"] == {"A": {"physical": 1, "reserved": 1, "available": 0}}


def test_description_coverage_retains_original_claims_and_adds_scope_links() -> None:
    data = json.loads((BASE / "product-description-coverage.json").read_text())
    assert data["source_commit"] == "7cf38e17e1981607287b0d5a41abedeead3bcf5e"
    assert len(data["claims"]) == 20
    refinement = data["scope_refinement"]
    assert refinement["path"] == str(PLAN.relative_to(ROOT))
    assert refinement["source_commit"] == plan()["source_commit"]
    assert refinement["coverage_kind"] == "planning_not_product_completion"
    assert_reference(refinement["path"])
    claims = {row["id"]: row for row in data["claims"]}
    assert {f"R03-T{number:03}" for number in range(1, 18)} <= set(claims["inventory"]["tasks"])
    assert {"R04-T006", "R04-T007", "R04-T008", "R04-T013", "R04-T014"} <= set(
        claims["inventory"]["tasks"]
    )
    assert {f"R04-T{number:03}" for number in range(1, 15)} <= set(claims["sales"]["tasks"])
    assert {
        "R03-T003",
        "R03-T005",
        "R03-T007",
        "R03-T008",
        "R03-T009",
        "R03-T010",
        "R03-T016",
    } <= set(claims["purchases"]["tasks"])
    assert {"R03-T011", "R04-T007", "R04-T008", "R04-T014"} <= set(
        claims["business_profiles"]["tasks"]
    )
    for name in ("inventory", "sales", "purchases", "business_profiles"):
        assert claims[name]["scope_refinement"] == refinement["path"]
        assert len(claims[name]["acceptance"]) >= 3
    # Existing normative requirements and accepted scope remain present; additions
    # can evolve without pinning every original sentence or array formatting.
    for name in ("inventory", "purchases"):
        assert {ref.rsplit("#", 1)[1] for ref in claims[name]["requirements"]} == {
            f"FR-INV-{number:03}" for number in range(1, 13)
        }
    assert {ref.rsplit("#", 1)[1] for ref in claims["sales"]["requirements"]} == {
        f"FR-POS-{number:03}" for number in range(1, 10)
    }
    assert {ref.rsplit("#", 1)[1] for ref in claims["business_profiles"]["requirements"]} == {
        f"FR-BIZ-{number:03}" for number in range(1, 4)
    }
    assert claims["inventory"]["product_status"] == "partial"
    for name in ("sales", "purchases", "business_profiles"):
        assert claims[name]["product_status"] == "planned"
    existing_acceptance = {
        "inventory": [
            "All named movement kinds reconcile stock projection to append-only ledger; "
            "adjustments/returns are compensating.",
            "Concurrent last-unit sale/reservation and two-device offline intents produce "
            "explicit policy results without stock or tenant leakage.",
        ],
        "sales": [
            "Independent/service sale with partial/multi-method receipts, tax/discount and "
            "return reconciles exact inventory and payment ledgers.",
        ],
        "purchases": [
            "Supplier PO admits partial/full receipts with exact ordered/received balance, "
            "cost snapshots and atomic ledger effects.",
        ],
        "business_profiles": [
            "Profile switch never deletes records/pending work or grants capabilities; "
            "unsupported specialty modules stay visibly unavailable.",
        ],
    }
    for name, acceptance in existing_acceptance.items():
        assert set(acceptance) <= set(claims[name]["acceptance"])
