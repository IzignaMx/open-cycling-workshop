"""Fail closed on incomplete native expiry repetitions; no browser surrogate claim."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.ci import inventory_expiry_repeat as gate


def report():
    test = {
        "expectedStatus": "passed",
        "status": "expected",
        "projectName": "chromium",
        "timeout": 45000,
        "results": [{"status": "passed", "retry": 0, "errors": []}],
    }
    return {
        "config": {
            "workers": 1,
            "projects": [{"name": "chromium", "repeatEach": 5, "retries": 0, "timeout": 45000}],
        },
        "suites": [
            {
                "file": "inventory.spec.ts",
                "specs": [
                    {
                        "title": title,
                        "file": "inventory.spec.ts",
                        "ok": True,
                        "tests": [copy.deepcopy(test) for _ in range(5)],
                    }
                    for title in gate.TITLES
                ],
            }
        ],
        "errors": [],
        "stats": {
            "startTime": "2026-10-15T08:00:01Z",
            "expected": 10,
            "unexpected": 0,
            "flaky": 0,
            "skipped": 0,
        },
    }


def test_exact_two_by_five_retry_free_passes_are_required():
    gate.validate_report(report())


def test_reporter_unmerged_repeat_specs_still_require_five_of_each_title():
    value = report()
    value["suites"][0]["specs"] = [
        {**spec, "tests": [test]} for spec in value["suites"][0]["specs"] for test in spec["tests"]
    ]
    assert len(value["suites"][0]["specs"]) == 10
    gate.validate_report(value)


@pytest.mark.parametrize(
    "fault",
    [
        "skipped",
        "failed",
        "flaky",
        "missing",
        "extra",
        "retry",
        "wrong_title",
        "wrong_project",
        "wrong_timeout",
        "workers",
        "repeat_count",
        "report_error",
        "result_error",
    ],
)
def test_incomplete_or_different_repeat_matrix_never_passes(fault):
    value = report()
    tests = value["suites"][0]["specs"][0]["tests"]
    if fault in {"skipped", "failed", "flaky"}:
        tests[0]["status"] = fault
    elif fault == "missing":
        tests.pop()
    elif fault == "extra":
        tests.append(copy.deepcopy(tests[0]))
    elif fault == "retry":
        tests[0]["results"][0]["retry"] = 1
    elif fault == "wrong_title":
        value["suites"][0]["specs"][0]["title"] = "unrelated passing test"
    elif fault == "wrong_project":
        tests[0]["projectName"] = "other"
    elif fault == "wrong_timeout":
        tests[0]["timeout"] = 45001
    elif fault == "workers":
        value["config"]["workers"] = 2
    elif fault == "repeat_count":
        value["config"]["projects"][0]["repeatEach"] = 4
    elif fault == "report_error":
        value["errors"].append({"message": "synthetic"})
    else:
        tests[0]["results"][0]["errors"].append({"message": "synthetic"})
    with pytest.raises((AssertionError, ValueError)):
        gate.validate_report(value)


def test_start_binding_rejects_stale_changed_or_skipped_run(tmp_path):
    for name in gate.SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source")
    directory = tmp_path / gate.OUTPUT
    gate.start(tmp_path, "a" * 40, datetime(2026, 10, 15, 8, tzinfo=UTC))
    path = directory / "results.json"
    path.write_text(json.dumps(report()))
    gate.check(tmp_path, "a" * 40, "success")
    assert json.loads((directory / "evidence.json").read_text())["status"] == "complete"
    for outcome in ["skipped", "failure", "cancelled"]:
        with pytest.raises(AssertionError):
            gate.check(tmp_path, "a" * 40, outcome)
        assert json.loads((directory / "evidence.json").read_text())["status"] == "incomplete"
    with pytest.raises(AssertionError):
        gate.check(tmp_path, "b" * 40, "success")
    value = report()
    value["stats"]["startTime"] = "2026-10-15T07:59:59Z"
    path.write_text(json.dumps(value))
    with pytest.raises(AssertionError):
        gate.check(tmp_path, "a" * 40, "success")
    path.write_text(json.dumps(report()))
    (tmp_path / gate.SOURCES[0]).write_text("changed source")
    with pytest.raises(AssertionError):
        gate.check(tmp_path, "a" * 40, "success")


def test_cli_source_mismatch_invalidates_previous_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setattr(gate.subprocess, "check_output", lambda *args, **kwargs: "a" * 40)
    monkeypatch.setattr(gate.sys, "argv", ["gate", "check", "success"])
    directory = tmp_path / gate.OUTPUT
    directory.mkdir(parents=True)
    (directory / "evidence.json").write_text('{"status":"complete"}')
    with pytest.raises(SystemExit, match="Inventory expiry repetition incomplete"):
        gate.main()
    assert json.loads((directory / "evidence.json").read_text())["status"] == "incomplete"


def test_workflow_requires_successful_fresh_repeat_even_when_other_steps_fail():
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/ci.yml").read_text()
    step = workflow.split("- name: Repeat inventory expiry without retries", 1)[1].split(
        "- name:", 1
    )[0]
    assert "id: inventory_expiry_repeat" in step
    assert "inventory_expiry_repeat.py start" in step
    assert "--grep 'inventory-only display clears on .* expiry'" in step
    assert "--repeat-each=5 --retries=0 --workers=1" in step
    assert "--reporter=line,html,json" in step
    assert (
        "PLAYWRIGHT_JSON_OUTPUT_NAME: test-results/inventory-expiry-repeat-proof/results.json"
        in step
    )
    check = workflow.split("- name: Require complete inventory expiry repetition", 1)[1].split(
        "- name:", 1
    )[0]
    assert "if: always()" in check
    assert (
        'inventory_expiry_repeat.py check "${{ steps.inventory_expiry_repeat.outcome }}"' in check
    )
    upload = workflow.split("- name: Upload inventory expiry repetition evidence", 1)[1].split(
        "- name:", 1
    )[0]
    assert "if: always()" in upload
    assert "browser-inventory-expiry-repeat-${{ github.sha }}" in upload
    assert "if-no-files-found: error" in upload
    assert "apps/web/test-results/inventory-expiry-repeat-proof/" in upload
    assert "continue-on-error" not in step + check + upload
    aggregate = workflow.split("- name: Run V0.1 qualification verifier", 1)[1].split("- name:", 1)[
        0
    ]
    assert "if: always()" in aggregate
    assert (
        'inventory_expiry_repeat.py check "${{ steps.inventory_expiry_repeat.outcome }}"'
        in aggregate
    )
