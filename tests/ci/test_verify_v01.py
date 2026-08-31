from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
