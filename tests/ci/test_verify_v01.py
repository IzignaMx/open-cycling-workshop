from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("verify_v01", ROOT / "scripts/ci/verify_v01.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_probe_tool_requires_the_executable_to_run_successfully() -> None:
    passing = MODULE.probe_tool("python", sys.executable, ["--version"], "python unavailable")
    failing = MODULE.probe_tool(
        "broken", sys.executable, ["-c", "raise SystemExit(3)"], "tool cannot execute"
    )

    assert passing.status == "pass"
    assert failing.status == "blocked"
    assert "tool cannot execute" in failing.detail


def test_browser_runtime_checks_are_explicitly_blocked_without_pnpm_or_e2e_database() -> None:
    checks, blockers = MODULE.browser_runtime_checks(
        MODULE.Check("tool_pnpm", "blocked", "registry unavailable"),
        {},
    )

    assert checks == []
    assert {item.name for item in blockers} == {"pwa_build", "browser_e2e"}
    assert all(item.status == "blocked" for item in blockers)


def test_indexeddb_runtime_check_preserves_environment_blockers(monkeypatch) -> None:
    class Result:
        returncode = 2
        stdout = (
            '{"status":"blocked","reason":"chromium managed URLBlocklist blocks all navigations"}'
        )
        stderr = ""

    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: Result())

    check = MODULE.indexeddb_runtime_check()

    assert check.name == "indexeddb_100k"
    assert check.status == "blocked"
    assert "URLBlocklist" in check.detail


def test_static_analysis_checks_run_available_python_and_frontend_tools(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_run_check(name: str, command: list[str], *, env=None):
        calls.append((name, tuple(command)))
        return MODULE.Check(name, "pass", "ok")

    monkeypatch.setattr(MODULE, "run_check", fake_run_check)

    checks, blockers = MODULE.static_analysis_checks(
        pnpm_probe=MODULE.Check("tool_pnpm", "pass", "pnpm 11.17.0"),
        ruff_probe=MODULE.Check("tool_ruff", "pass", "ruff 0.12"),
        mypy_probe=MODULE.Check("tool_mypy", "pass", "mypy 1.17"),
        env={"PATH": "/tmp"},
    )

    assert blockers == []
    assert {check.name for check in checks} == {
        "python_ruff",
        "python_format",
        "python_mypy",
        "frontend_eslint",
        "frontend_prettier",
    }
    assert (
        "python_ruff",
        ("ruff", "check", "services/platform/src", "services/platform/tests", "tests", "scripts"),
    ) in calls
    # Frontend tools run through node with explicit workspace bin paths so
    # they do not depend on pnpm's environment handling.
    assert any(
        name == "frontend_eslint"
        and command[0] == "node"
        and command[1].replace("\\", "/").endswith("eslint/bin/eslint.js")
        for name, command in calls
    )


def test_static_analysis_checks_report_blocked_groups_without_executing_commands(
    monkeypatch,
) -> None:
    def unexpected(*args, **kwargs):
        raise AssertionError("run_check must not execute for unavailable toolchains")

    monkeypatch.setattr(MODULE, "run_check", unexpected)

    checks, blockers = MODULE.static_analysis_checks(
        pnpm_probe=MODULE.Check("tool_pnpm", "blocked", "registry unavailable"),
        ruff_probe=MODULE.Check("tool_ruff", "blocked", "ruff missing"),
        mypy_probe=MODULE.Check("tool_mypy", "blocked", "mypy missing"),
        env={},
    )

    assert checks == []
    assert {blocker.name for blocker in blockers} == {
        "python_static_analysis",
        "frontend_static_analysis",
    }
    assert all(blocker.status == "blocked" for blocker in blockers)


def test_qualification_metadata_identifies_commit_and_runtime(monkeypatch) -> None:
    class Result:
        returncode = 0
        stdout = "abc123\n"
        stderr = ""

    monkeypatch.setattr(MODULE.subprocess, "run", lambda *args, **kwargs: Result())
    monkeypatch.setattr(MODULE.platform, "platform", lambda: "test-platform")

    metadata = MODULE.qualification_metadata()

    assert metadata["git_sha"] == "abc123"
    assert metadata["python"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}.")
    assert metadata["platform"] == "test-platform"
    assert "ci" in metadata


def test_postgresql_runtime_checks_block_when_driver_or_database_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(MODULE.importlib.util, "find_spec", lambda name: None)

    checks, blockers = MODULE.postgresql_runtime_checks({})

    assert checks == []
    assert {item.name for item in blockers} == {"python_psycopg", "postgresql_integration"}
    assert all(item.status == "blocked" for item in blockers)


def test_postgresql_runtime_checks_execute_integration_when_ready(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr(MODULE.importlib.util, "find_spec", lambda name: object())

    def fake_run_check(name: str, command: list[str], *, env=None):
        calls.append((name, tuple(command)))
        return MODULE.Check(name, "pass", "ok")

    monkeypatch.setattr(MODULE, "run_check", fake_run_check)

    checks, blockers = MODULE.postgresql_runtime_checks(
        {"OCWP_TEST_DATABASE_URL": "postgresql://example.invalid/ocwp_e2e"}
    )

    assert blockers == []
    assert {item.name for item in checks} == {"python_psycopg", "postgresql_integration"}
    assert any(
        name == "postgresql_integration" and "test_postgres_integration.py" in " ".join(command)
        for name, command in calls
    )


def test_qualifier_browser_evidence_is_isolated_even_with_inherited_direct_paths(monkeypatch):
    calls = []
    env = {
        "OCWP_E2E_DATABASE_URL": "postgresql://example.invalid/ocwp_e2e",
        "OCWP_PLAYWRIGHT_OUTPUT_DIR": "test-results/direct",
        "PLAYWRIGHT_HTML_OUTPUT_DIR": "playwright-report/direct",
    }
    original = dict(env)

    def fake_run_check(name, command, *, env=None, cwd=None):
        calls.append((name, command, env, cwd))
        return MODULE.Check(name, "pass", "ok")

    monkeypatch.setattr(MODULE, "run_check", fake_run_check)
    checks, blockers = MODULE.browser_runtime_checks(MODULE.Check("tool_pnpm", "pass", "ok"), env)

    assert blockers == []
    assert all(check.status == "pass" for check in checks)
    browser = next(call for call in calls if call[0] == "browser_e2e")
    web = ROOT / "apps/web"
    assert browser[2]["OCWP_PLAYWRIGHT_OUTPUT_DIR"] == str(web / "test-results/qualification")
    assert browser[2]["PLAYWRIGHT_HTML_OUTPUT_DIR"] == str(web / "playwright-report/qualification")
    assert browser[1][-1] == "test"
    assert env == original


def test_qualifier_requires_real_pinned_old_build_before_browser_setup(monkeypatch):
    calls = []

    def fake_run_check(name, command, *, env=None, cwd=None):
        calls.append((name, command))
        if "scripts/e2e/build_legacy_client.mjs" in command:
            return MODULE.Check(name, "fail", "pinned dependency mismatch")
        return MODULE.Check(name, "pass", "ok")

    monkeypatch.setattr(MODULE, "run_check", fake_run_check)
    checks, blockers = MODULE.browser_runtime_checks(
        MODULE.Check("tool_pnpm", "pass", "ok"),
        {"OCWP_E2E_DATABASE_URL": "postgresql://example.invalid/ocwp_e2e"},
    )
    assert not blockers
    assert any(check.name == "pwa_build" and check.status == "fail" for check in checks)
    assert any(check.name == "browser_e2e" and check.status == "fail" for check in checks)
    assert not any(name in {"browser_e2e_prepare", "browser_e2e"} for name, _ in calls)


def full_python_receipt():
    """Synthetic protocol data only; this fixture never starts a worker or test run."""
    identity = MODULE.full_python_identity(
        commit="a" * 40,
        tree="b" * 40,
        image_id="sha256:" + "c" * 64,
        pg_image_id="sha256:" + "d" * 64,
        nonce="e" * 32,
        run_id="1234567",
        run_attempt="1",
    )
    nodes, outcomes = [], []
    for index, case in enumerate((*MODULE.FULL_CASES, None)):
        key = hashlib.sha256(f"synthetic-node-{index}".encode()).hexdigest()
        case_id = case.case if case is not None else None
        nodes.append({"node_sha256": key, "case": case_id})
        phases = [["passed", 1, None], ["passed", 1, None], ["passed", 1, None]]
        if case is not None and case.reason is not None:
            phases[case.phase] = ["skipped", 1, case.case]
            if case.phase == 0:
                phases[1] = None
        outcomes.append({"node_sha256": key, "phases": phases})
    collection = {
        "schema": 1,
        "kind": "ocwp.full_python.collection",
        "identity": identity,
        "policy": deepcopy(MODULE.FULL_POLICY),
        "collection_errors": 0,
        "deselected": 0,
        "nodes": nodes,
        "count": len(nodes),
        "inventory_sha256": hashlib.sha256(MODULE._full_json(nodes)).hexdigest(),
    }
    result = {
        "schema": 1,
        "kind": "ocwp.full_python.result",
        "identity": deepcopy(identity),
        "policy": deepcopy(MODULE.FULL_POLICY),
        "inventory_sha256": collection["inventory_sha256"],
        "session_finished": True,
        "exit_code": 0,
        "collection_errors": 0,
        "deselected": 0,
        "preflight": deepcopy(MODULE.FULL_PREFLIGHT),
        "outcomes": outcomes,
        "counts": {
            "collected": 70,
            "passed": 12,
            "failed": 0,
            "error": 0,
            "expected_skipped": 58,
            "unexpected_skipped": 0,
            "unrun": 0,
        },
    }
    return {
        "schema": 1,
        "kind": "ocwp.full_python.receipt",
        "identity": deepcopy(identity),
        "policy": deepcopy(MODULE.FULL_POLICY),
        "status": "passed",
        "failure": None,
        "collection": collection,
        "result": result,
        "containment": {
            "canary": "passed",
            "worker_exit": 0,
            "deadline": "completed",
            "stdout_bytes": 123,
            "source_read_only": True,
            "closed_network": True,
            "scratch_verified": True,
            "worker_stopped": True,
            "creation_uncertain": False,
            "resource_samples": {"worker": 2, "db": 2},
            "pressure_events": {"worker": 0, "db": 0},
            "final_probe": "passed",
        },
        "primary_cleanup": "verified_absent",
        "independent_cleanup": "verified_absent",
    }


def refresh_inventory(receipt):
    collection = receipt["collection"]
    collection["count"] = len(collection["nodes"])
    collection["inventory_sha256"] = hashlib.sha256(
        MODULE._full_json(collection["nodes"])
    ).hexdigest()
    receipt["result"]["inventory_sha256"] = collection["inventory_sha256"]


def test_full_python_receipt_consumes_all_three_controls_once(tmp_path):
    receipt = full_python_receipt()
    path = tmp_path / "receipt.json"
    MODULE.write_full_python_json(path, receipt)

    checks = MODULE.consume_full_python_receipt(path, receipt["identity"])

    assert [check.name for check in checks] == list(MODULE.FULL_CHECK_NAMES)
    assert all(check.status == "pass" for check in checks)
    counts = MODULE.validate_full_python_receipt(receipt, receipt["identity"])
    assert counts["expected_skipped"] == 58


@pytest.mark.parametrize(
    "field,value",
    [
        ("commit", "f" * 40),
        ("tree", "f" * 40),
        ("image_id", "sha256:" + "f" * 64),
        ("pg_image_id", "sha256:" + "f" * 64),
        ("nonce", "f" * 32),
        ("run_id", "7654321"),
        ("run_attempt", "2"),
        ("command_sha256", "f" * 64),
        ("workflow_sha256", "f" * 64),
        ("helper_sha256", "f" * 64),
        ("verifier_sha256", "f" * 64),
        ("uv_lock_sha256", "f" * 64),
        ("pnpm_lock_sha256", "f" * 64),
        ("job", "verify"),
        ("clean_source", False),
    ],
)
def test_full_python_receipt_rejects_stale_or_wrong_context(field, value):
    receipt = full_python_receipt()
    expected = deepcopy(receipt["identity"])
    receipt["identity"][field] = value

    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, expected)


@pytest.mark.parametrize("location", ["collection", "result"])
def test_full_python_receipt_requires_inner_source_identity(location):
    receipt = full_python_receipt()
    expected = deepcopy(receipt["identity"])
    receipt[location]["identity"]["tree"] = "f" * 40

    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, expected)


@pytest.mark.parametrize(
    "case",
    [
        "required.proof_record.sqlite",
        "required.proof_record.postgres",
        "required.page25.sqlite",
        "required.page25.postgres",
        "required.restore.database",
        "required.restore.branding.current",
        "required.restore.branding.legacy",
        "required.restore.quote_repository",
        "required.restore.generated_counts",
        "required.restore.service",
        "required.database",
    ],
)
def test_full_python_receipt_requires_every_large_restore_and_database_case(case):
    receipt = full_python_receipt()
    index = next(
        index for index, node in enumerate(receipt["collection"]["nodes"]) if node["case"] == case
    )
    receipt["collection"]["nodes"].pop(index)
    receipt["result"]["outcomes"].pop(index)
    refresh_inventory(receipt)

    with pytest.raises(MODULE.FullPythonEvidenceError, match="required_cases_missing"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_collection",
        "duplicate_result",
        "omitted_result",
        "extra_result",
        "reordered_result",
    ],
)
def test_full_python_receipt_requires_unique_bijective_inventory(mutation):
    receipt = full_python_receipt()
    nodes = receipt["collection"]["nodes"]
    outcomes = receipt["result"]["outcomes"]
    if mutation == "duplicate_collection":
        nodes[-1] = deepcopy(nodes[0])
        refresh_inventory(receipt)
    elif mutation == "duplicate_result":
        outcomes[-1] = deepcopy(outcomes[0])
    elif mutation == "omitted_result":
        outcomes.pop()
    elif mutation == "extra_result":
        outcomes.append(deepcopy(outcomes[0]))
    else:
        outcomes[0], outcomes[1] = outcomes[1], outcomes[0]

    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("session_finished", False),
        ("session_finished", 1),
        ("exit_code", 1),
        ("exit_code", False),
        ("collection_errors", 1),
        ("deselected", 1),
        ("collection_errors", False),
        ("deselected", False),
    ],
)
def test_full_python_exit_zero_alone_never_proves_completion(field, value):
    receipt = full_python_receipt()
    receipt["result"][field] = value

    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize("duration", [True, -1, 900000001, 0.1, float("nan"), float("inf")])
def test_full_python_phase_duration_is_strict_bounded_microseconds(duration):
    receipt = full_python_receipt()
    receipt["result"]["outcomes"][-1]["phases"][1][1] = duration

    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize("phases", [[None, None, None], [["passed", 1, None], None, None]])
def test_full_python_fail_fast_tail_is_unrun_not_passed(phases):
    receipt = full_python_receipt()
    receipt["result"]["outcomes"][-1]["phases"] = phases
    counts = MODULE._full_counts(receipt["result"]["outcomes"], receipt["collection"]["nodes"])
    assert counts["unrun"] == 1 and counts["passed"] == 11
    receipt["result"]["counts"] = counts

    with pytest.raises(MODULE.FullPythonEvidenceError, match="result_incomplete"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize(
    "case", [case.case for case in MODULE.FULL_CASES if case.case.startswith("required.restore.")]
)
def test_full_python_restore_dependency_skips_are_never_allowed(case):
    receipt = full_python_receipt()
    index = next(
        index for index, node in enumerate(receipt["collection"]["nodes"]) if node["case"] == case
    )
    receipt["result"]["outcomes"][index]["phases"] = [
        ["skipped", 1, "unexpected"],
        None,
        ["passed", 1, None],
    ]
    receipt["result"]["counts"] = MODULE._full_counts(
        receipt["result"]["outcomes"], receipt["collection"]["nodes"]
    )

    with pytest.raises(MODULE.FullPythonEvidenceError, match="result_incomplete"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_full_python_exact_skip_ledger_rejects_replacement_or_wrong_phase():
    assert len(MODULE.FULL_SKIP_CASES) == 58
    assert sum(case.phase == 0 for case in MODULE.FULL_CASES) == 2
    assert sum(case.phase == 1 for case in MODULE.FULL_CASES) == 56
    receipt = full_python_receipt()
    # The count remains58, but a different semantic node cannot replace a skip.
    original = receipt["result"]["outcomes"][0]["phases"]
    original[1] = ["passed", 1, None]
    receipt["result"]["outcomes"][-1]["phases"][1] = ["skipped", 1, "skip.gitleaks.pinned"]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="skip_identity"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])

    receipt = full_python_receipt()
    receipt["result"]["outcomes"][0]["phases"] = [
        ["skipped", 1, "skip.gitleaks.pinned"],
        None,
        ["passed", 1, None],
    ]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="skip_identity"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_full_python_classifier_uses_complete_typed_parameters_not_nodeid_spelling():
    for case in MODULE.FULL_CASES:
        assert MODULE.full_python_case(case.source, case.function, dict(case.params)) == case.case
        with pytest.raises(MODULE.FullPythonEvidenceError, match="case_matrix_changed"):
            MODULE.full_python_case(case.source, case.function, {**case.params, "unreviewed": True})
    legacy = MODULE.FULL_CASE_BY_ID["required.restore.branding.legacy"]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="case_matrix_changed"):
        MODULE.full_python_case(legacy.source, legacy.function, {"legacy_source": 1})
    metadata = MODULE.FULL_CASE_BY_ID["skip.metadata.temp.sync_changes.TABLE.upper"]
    with pytest.raises(MODULE.FullPythonEvidenceError, match="case_matrix_changed"):
        MODULE.full_python_case(
            metadata.source, metadata.function, {**metadata.params, "uppercase": 1}
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_exit", 1),
        ("worker_exit", False),
        ("deadline", "timed_out"),
        ("stdout_bytes", 1048576),
        ("stdout_bytes", True),
        ("worker_stopped", False),
        ("source_read_only", False),
        ("closed_network", False),
        ("scratch_verified", False),
        ("creation_uncertain", True),
        ("canary", "failed"),
        ("final_probe", "unavailable"),
        ("resource_samples", {"worker": 0, "db": 1}),
        ("resource_samples", {"worker": 1, "db": 2}),
        ("resource_samples", {"worker": 2, "db": 1}),
        ("pressure_events", {"worker": 1, "db": 0}),
    ],
)
def test_full_python_containment_is_required_for_success(field, value):
    receipt = full_python_receipt()
    receipt["containment"][field] = value
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize("field", ["primary_cleanup", "independent_cleanup"])
def test_full_python_both_cleanup_proofs_are_required(field):
    receipt = full_python_receipt()
    receipt[field] = "failed"
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_full_python_finalizer_can_only_accept_exact_provisional_success():
    receipt = full_python_receipt()
    receipt.update(
        status="failed", failure="independent_cleanup_pending", independent_cleanup="pending"
    )
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])
    counts = MODULE.validate_full_python_receipt(
        receipt, receipt["identity"], allow_pending_cleanup=True
    )
    assert counts["passed"] == 12
    for failure in ("wall_budget", "result_failed", "unrun", None):
        broken = deepcopy(receipt)
        broken["failure"] = failure
        with pytest.raises(MODULE.FullPythonEvidenceError):
            MODULE.validate_full_python_receipt(
                broken, broken["identity"], allow_pending_cleanup=True
            )


@pytest.mark.parametrize("field", ["passed", "collected", "unrun", "expected_skipped"])
def test_full_python_count_reconciliation_rejects_booleans_and_wrong_totals(field):
    for value in (False, 8192):
        receipt = full_python_receipt()
        receipt["result"]["counts"][field] = value
        with pytest.raises(MODULE.FullPythonEvidenceError):
            MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize(
    "raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e9999}', '{"a":', "[]"]
)
def test_full_python_reader_rejects_duplicate_nonfinite_truncated_or_wrong_json(tmp_path, raw):
    path = tmp_path / "receipt.json"
    path.write_text(raw)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.read_full_python_json(path)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.read_full_python_value(raw)


def test_full_python_reader_and_writer_enforce_strict_size_and_regular_files(tmp_path):
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * MODULE.FULL_RECORD_LIMIT)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.read_full_python_json(path)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.write_full_python_json(path, {"large": "x" * MODULE.FULL_RECORD_LIMIT})
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.read_full_python_json(link)
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.read_full_python_json(tmp_path)


def test_full_python_missing_failed_and_unrun_receipts_fail_all_controls(tmp_path):
    receipt = full_python_receipt()
    path = tmp_path / "receipt.json"
    for state in ("missing", "failed", "unrun"):
        if state != "missing":
            current = deepcopy(receipt)
            current.update(status="failed", failure=state if state == "unrun" else "result_failed")
            if state == "unrun":
                current.update(collection=None, result=None)
            MODULE.write_full_python_json(path, current)
        checks = MODULE.consume_full_python_receipt(path, receipt["identity"])
        assert {check.name for check in checks} == set(MODULE.FULL_CHECK_NAMES)
        assert all(check.status == "fail" for check in checks)


def test_full_python_protocol_size_is_bounded_at_node_ceiling():
    receipt = full_python_receipt()
    nodes = receipt["collection"]["nodes"]
    outcomes = receipt["result"]["outcomes"]
    for index in range(len(nodes), MODULE.FULL_MAX_NODES):
        key = hashlib.sha256(f"maximum-node-{index}".encode()).hexdigest()
        nodes.append({"node_sha256": key, "case": None})
        outcomes.append(
            {"node_sha256": key, "phases": [["passed", 900000000, None] for _ in range(3)]}
        )
    refresh_inventory(receipt)
    receipt["result"]["counts"]["collected"] = MODULE.FULL_MAX_NODES
    receipt["result"]["counts"]["passed"] = MODULE.FULL_MAX_NODES - 58
    assert len(MODULE._full_json(receipt)) + 1 < MODULE.FULL_RECORD_LIMIT
    assert len(MODULE._full_json(receipt)) + 1 < MODULE.FULL_MAX_SERIALIZED_BYTES
    assert MODULE.validate_full_python_receipt(receipt, receipt["identity"])["collected"] == 8192
    receipt["collection"]["count"] = 8193
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


def test_full_python_plugin_is_inert_outside_contained_mode(monkeypatch):
    assert MODULE.FULL_PYTHON_ARGS[-7:] == (
        "--capture=fd",
        "--show-capture=no",
        "--no-showlocals",
        "--tb=short",
        "-q",
        "tests",
        "services/platform/tests",
    )
    monkeypatch.delenv("OCWP_FULL_PYTHON", raising=False)
    monkeypatch.setattr(MODULE, "_FullPythonPlugin", lambda config: pytest.fail("plugin activated"))
    MODULE.pytest_configure(SimpleNamespace())


def fake_full_python_plugin():
    plugin = MODULE._FullPythonPlugin.__new__(MODULE._FullPythonPlugin)
    plugin.identity = full_python_receipt()["identity"]
    plugin.preflight = deepcopy(MODULE.FULL_PREFLIGHT)
    plugin.collection_errors = 0
    plugin.deselected = 0
    plugin.collection = None
    plugin.outcomes = {}
    plugin.cases = {}
    plugin.protocol_error = False
    return plugin


def test_full_python_plugin_seals_hashed_inventory_before_reports(monkeypatch):
    plugin = fake_full_python_plugin()
    written = []
    monkeypatch.setattr(
        MODULE,
        "write_full_python_json",
        lambda path, value: written.append((path, deepcopy(value))),
    )
    items = []
    for index, case in enumerate(MODULE.FULL_CASES):
        items.append(
            SimpleNamespace(
                path=MODULE.ROOT / case.source,
                originalname=case.function,
                nodeid=f"{case.source}::{case.function}[arbitrary-generated-id-{index}]",
                callspec=SimpleNamespace(params=case.params),
            )
        )
    # Arbitrarily verbose generated IDs are hashed rather than exported.
    items.append(
        SimpleNamespace(
            path=MODULE.ROOT / "tests/ci/test_verify_v01.py",
            originalname="test_ordinary_synthetic_case",
            nodeid="ordinary[" + "sensitive-synthetic-payload" * 10000 + "]",
            callspec=None,
        )
    )
    session = SimpleNamespace(items=items)
    plugin.pytest_collection_finish(session)
    assert len(written) == 1
    assert written[0][0] == Path("/tmp/ocwp-proof/collection.json")
    assert all(node["phases"] == [None, None, None] for node in plugin.outcomes.values())
    assert "sensitive-synthetic-payload" not in MODULE._full_json(written[0][1]).decode()

    for item, case in zip(items, (*MODULE.FULL_CASES, None), strict=True):
        for phase, when in enumerate(("setup", "call", "teardown")):
            if case is not None and case.phase == 0 and phase == 1:
                continue
            skipped = case is not None and case.reason is not None and case.phase == phase
            plugin.pytest_runtest_logreport(
                SimpleNamespace(
                    nodeid=item.nodeid,
                    when=when,
                    outcome="skipped" if skipped else "passed",
                    duration=0.001,
                    longrepr=(case.source, 1, "Skipped: " + case.reason) if skipped else None,
                )
            )
    plugin.pytest_sessionfinish(session, 0)
    assert written[1][0] == Path("/tmp/ocwp-proof/result.json")
    counts = MODULE.validate_full_python_result(written[1][1], plugin.identity, written[0][1])
    assert counts["passed"] == 12


@pytest.mark.parametrize("reason", ["missing PostgreSQL", "host containment preflight required "])
def test_full_python_plugin_normalizes_only_exact_skip_reason(reason):
    plugin = fake_full_python_plugin()
    nodeid = "synthetic-opt-in-node"
    key = hashlib.sha256(nodeid.encode()).hexdigest()
    plugin.outcomes[key] = {"node_sha256": key, "phases": [None, None, None]}
    plugin.cases[key] = "skip.micro.three_operations"
    plugin.pytest_runtest_logreport(
        SimpleNamespace(
            nodeid=nodeid,
            when="setup",
            outcome="skipped",
            duration=0.001,
            longrepr=("synthetic.py", 1, "Skipped: " + reason),
        )
    )
    assert plugin.outcomes[key]["phases"][0] == ["skipped", 1000, "unexpected"]


def test_full_python_plugin_rejects_out_of_order_and_duplicate_reports():
    for reports in (("call",), ("setup", "setup"), ("setup", "teardown", "call")):
        plugin = fake_full_python_plugin()
        nodeid = "synthetic-node"
        key = hashlib.sha256(nodeid.encode()).hexdigest()
        plugin.outcomes[key] = {"node_sha256": key, "phases": [None, None, None]}
        plugin.cases[key] = None
        with pytest.raises(MODULE.FullPythonEvidenceError):
            for phase in reports:
                plugin.pytest_runtest_logreport(
                    SimpleNamespace(
                        nodeid=nodeid,
                        when=phase,
                        outcome="passed",
                        duration=0.001,
                        longrepr=None,
                    )
                )
        assert plugin.protocol_error


def test_full_python_expected_context_uses_checkout_and_job_outputs(monkeypatch):
    outputs = {
        ("status", "--porcelain", "--untracked-files=normal"): "",
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "HEAD^{tree}"): "b" * 40,
    }
    calls = []

    def git(command, **kwargs):
        calls.append(command)
        assert command[:2] == ["git", "--no-optional-locks"]
        kwargs["stdout"].write(outputs[tuple(command[2:])].encode())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(MODULE.subprocess, "run", git)
    env = {
        "OCWP_FULL_PYTHON_IMAGE_ID": "sha256:" + "c" * 64,
        "OCWP_FULL_PYTHON_PG_IMAGE_ID": "sha256:" + "d" * 64,
        "OCWP_FULL_PYTHON_NONCE": "e" * 32,
        "GITHUB_RUN_ID": "1234567",
        "GITHUB_RUN_ATTEMPT": "1",
    }
    identity = MODULE.full_python_expected_identity(env)
    assert identity == full_python_receipt()["identity"]
    assert len(calls) == 3
    outputs[("status", "--porcelain", "--untracked-files=normal")] = " M modified"
    with pytest.raises(MODULE.FullPythonEvidenceError, match="identity_dirty"):
        MODULE.full_python_expected_identity(env)


@pytest.mark.parametrize("case", ["short", "truncated", "query_cap"])
def test_dirty_source_paths_are_bounded_and_never_admit_a_receipt(monkeypatch, case):
    raw = b" M tracked.py\n?? var/\n"
    if case == "truncated":
        raw += b"?? synthetic-runtime-path/\n" * 200
    elif case == "query_cap":
        raw = b"x" * 16384

    def git(command, **kwargs):
        assert command == [
            "git",
            "--no-optional-locks",
            "status",
            "--porcelain",
            "--untracked-files=normal",
        ]
        kwargs["stdout"].write(raw)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(MODULE.subprocess, "run", git)
    monkeypatch.setattr(
        MODULE, "consume_full_python_receipt", lambda *args: pytest.fail("dirty receipt admitted")
    )
    checks = MODULE.full_python_route_checks(Path("unread-receipt.json"), {})
    assert [item.name for item in checks] == list(MODULE.FULL_CHECK_NAMES)
    assert all(item.status == "fail" for item in checks)
    assert len({item.detail for item in checks}) == 1
    if case == "query_cap":
        assert checks[0].detail == "Required full-Python evidence rejected: source_output_limit"
        return
    prefix = "Required full-Python evidence rejected: identity_dirty; bounded source status: "
    assert checks[0].detail.startswith(prefix)
    diagnostic = json.loads(checks[0].detail[len(prefix) :])
    assert diagnostic == {
        "kind": "git_porcelain_paths_only",
        "observed_bytes": len(raw),
        "retained_bytes": min(len(raw), 4096),
        "limit_bytes": 4096,
        "truncated": len(raw) > 4096,
        "encoding": "utf-8-with-replacement",
        "porcelain": raw[:4096].decode("utf-8", errors="replace"),
    }
    assert diagnostic["porcelain"].startswith(" M tracked.py\n?? var/\n")
    assert len(checks[0].detail) < 25000


@pytest.mark.parametrize("with_path", [False, True])
def test_full_python_aggregate_never_falls_back_and_allow_blocked_cannot_pass(
    monkeypatch, tmp_path, with_path
):
    commands = []

    def run_check(name, command, **kwargs):
        commands.append(command)
        assert "pytest" not in command
        return MODULE.Check(name, "pass", "mocked independent control")

    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(MODULE, "run_check", run_check)
    monkeypatch.setattr(
        MODULE, "full_python_expected_identity", lambda env: full_python_receipt()["identity"]
    )
    monkeypatch.setattr(
        MODULE, "postgresql_runtime_checks", lambda env: pytest.fail("duplicate pytest")
    )
    monkeypatch.setattr(
        MODULE, "probe_tool", lambda name, *args: MODULE.Check(name, "blocked", "mocked")
    )
    monkeypatch.setattr(MODULE, "static_analysis_checks", lambda **kwargs: ([], []))
    monkeypatch.setattr(
        MODULE,
        "indexeddb_runtime_check",
        lambda: MODULE.Check("indexeddb_100k", "blocked", "mocked"),
    )
    monkeypatch.setattr(MODULE, "browser_runtime_checks", lambda *args: ([], []))
    monkeypatch.setattr(MODULE, "qualification_metadata", lambda: {})
    report = tmp_path / "aggregate.json"
    arguments = ["verify_v01.py", "--allow-blocked", "--json-out", str(report)]
    if with_path:
        arguments += ["--full-python-receipt", str(tmp_path / "missing.json")]
    monkeypatch.setattr(sys, "argv", arguments)

    assert MODULE.main() == 1
    decoded = json.loads(report.read_text())
    assert decoded["status"] == "failed"
    required = [item for item in decoded["checks"] if item["name"] in MODULE.FULL_CHECK_NAMES]
    assert len(required) == 3 and all(item["status"] == "fail" for item in required)
    assert commands


@pytest.mark.parametrize(
    "field,value",
    [
        ("postgres_memory_mib", 768),
        ("postgres_memory_mib", 2048),
        ("postgres_tmpfs_bytes", [67108864, 268435456, 16777216]),
        ("postgres_tmpfs_bytes", [67108864, 1073741824, 16777216]),
    ],
)
def test_full_python_rejects_old_or_widened_postgres_budget(field, value):
    receipt = full_python_receipt()
    receipt["policy"][field] = value
    with pytest.raises(MODULE.FullPythonEvidenceError):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize("field", list(MODULE.FULL_POSTGRES_SETTINGS))
def test_full_python_rejects_changed_postgres_runtime_setting(field):
    receipt = full_python_receipt()
    receipt["result"]["preflight"]["database"]["settings"][field] = "unexpected"
    with pytest.raises(MODULE.FullPythonEvidenceError, match="preflight_failed"):
        MODULE.validate_full_python_receipt(receipt, receipt["identity"])


@pytest.mark.parametrize("fault", [None, "missing", "duplicate", "wider", "durability", "type"])
def test_postgres_runtime_readback_is_closed_and_exact(fault):
    rows = list(MODULE.FULL_POSTGRES_SETTINGS.items())
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(rows[0])
    elif fault == "wider":
        rows[0] = ("max_wal_size", "1GB")
    elif fault == "durability":
        rows[4] = ("fsync", "off")
    elif fault == "type":
        rows[0] = ("max_wal_size", 128)
    if fault:
        with pytest.raises(MODULE.FullPythonEvidenceError, match="database_settings"):
            MODULE.full_postgres_settings(rows)
    else:
        assert MODULE.full_postgres_settings(rows) == MODULE.FULL_POSTGRES_SETTINGS
