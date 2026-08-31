#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class Check:
    name: str
    status: str
    detail: str


def run_check(name: str, command: list[str], *, env: dict[str, str] | None = None) -> Check:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    detail = (result.stdout + result.stderr).strip()
    return Check(
        name=name, status="pass" if result.returncode == 0 else "fail", detail=detail[-4000:]
    )


def probe_tool(name: str, executable: str, version_args: list[str], blocked_reason: str) -> Check:
    path = shutil.which(executable)
    if not path:
        return Check(f"tool_{name}", "blocked", blocked_reason)
    try:
        result = subprocess.run(
            [path, *version_args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Check(f"tool_{name}", "blocked", f"{blocked_reason}; probe failed: {error}")
    detail = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        suffix = detail[-1000:] if detail else f"exit {result.returncode}"
        return Check(f"tool_{name}", "blocked", f"{blocked_reason}; probe failed: {suffix}")
    version = detail.splitlines()[0] if detail else "version probe passed"
    return Check(f"tool_{name}", "pass", f"{path} · {version}")


def qualification_metadata() -> dict[str, str | bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    git_sha = commit.stdout.strip() if commit.returncode == 0 else "unknown"
    node = subprocess.run(
        ["node", "--version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    node_version = node.stdout.strip() if node.returncode == 0 else "unavailable"
    return {
        "git_sha": git_sha,
        "python": platform.python_version(),
        "node": node_version,
        "platform": platform.platform(),
        "ci": bool(os.environ.get("CI")),
    }


def static_analysis_checks(
    *,
    pnpm_probe: Check,
    ruff_probe: Check,
    mypy_probe: Check,
    env: dict[str, str],
) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []

    if ruff_probe.status == "pass" and mypy_probe.status == "pass":
        checks.extend(
            [
                run_check(
                    "python_ruff",
                    [
                        "ruff",
                        "check",
                        "services/platform/src",
                        "services/platform/tests",
                        "tests",
                        "scripts",
                    ],
                    env=env,
                ),
                run_check(
                    "python_format",
                    [
                        "ruff",
                        "format",
                        "--check",
                        "services/platform/src",
                        "services/platform/tests",
                        "tests",
                        "scripts",
                    ],
                    env=env,
                ),
                run_check("python_mypy", ["mypy", "services/platform/src"], env=env),
            ]
        )
    else:
        blockers.append(
            Check("python_static_analysis", "blocked", "Ruff and mypy must both execute")
        )

    if pnpm_probe.status == "pass":
        checks.extend(
            [
                run_check("frontend_eslint", ["pnpm", "exec", "eslint", "."], env=env),
                run_check(
                    "frontend_prettier",
                    [
                        "pnpm",
                        "exec",
                        "prettier",
                        "--check",
                        "**/*.{js,mjs,ts,tsx,json,css,md,yml,yaml}",
                    ],
                    env=env,
                ),
            ]
        )
    else:
        blockers.append(
            Check(
                "frontend_static_analysis",
                "blocked",
                "pnpm must execute with workspace dependencies",
            )
        )

    return checks, blockers


def postgresql_runtime_checks(env: dict[str, str]) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []
    if importlib.util.find_spec("psycopg") is None:
        blockers.append(
            Check(
                "python_psycopg",
                "blocked",
                "psycopg v3 is not installed in the execution environment",
            )
        )
    else:
        checks.append(Check("python_psycopg", "pass", "psycopg v3 import available"))

    database_url = env.get("OCWP_TEST_DATABASE_URL")
    if not database_url:
        blockers.append(
            Check("postgresql_integration", "blocked", "OCWP_TEST_DATABASE_URL is required")
        )
    elif any(item.name == "python_psycopg" for item in blockers):
        blockers.append(
            Check(
                "postgresql_integration",
                "blocked",
                "psycopg v3 is required for PostgreSQL integration",
            )
        )
    else:
        checks.append(
            run_check(
                "postgresql_integration",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "services/platform/tests/db/test_postgres_integration.py",
                ],
                env=env,
            )
        )
    return checks, blockers


def indexeddb_runtime_check() -> Check:
    result = subprocess.run(
        [sys.executable, "scripts/benchmarks/run_indexeddb_native_benchmark.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    detail = (result.stdout + result.stderr).strip()[-4000:]
    if result.returncode == 0:
        return Check("indexeddb_100k", "pass", detail)
    if result.returncode == 2:
        return Check("indexeddb_100k", "blocked", detail)
    return Check("indexeddb_100k", "fail", detail)


def browser_runtime_checks(
    pnpm_probe: Check, env: dict[str, str]
) -> tuple[list[Check], list[Check]]:
    checks: list[Check] = []
    blockers: list[Check] = []
    if pnpm_probe.status != "pass":
        blockers.extend(
            [
                Check(
                    "pwa_build",
                    "blocked",
                    "pnpm must execute with installed workspace dependencies",
                ),
                Check(
                    "browser_e2e",
                    "blocked",
                    "pnpm/Playwright must execute before browser E2E can run",
                ),
            ]
        )
        return checks, blockers

    checks.append(run_check("pwa_build", ["pnpm", "--filter", "@ocwp/web", "build"], env=env))
    database_url = env.get("OCWP_E2E_DATABASE_URL")
    if not database_url:
        blockers.append(
            Check(
                "browser_e2e",
                "blocked",
                "OCWP_E2E_DATABASE_URL is required for destructive browser E2E setup",
            )
        )
        return checks, blockers

    prepare = run_check(
        "browser_e2e_prepare", [sys.executable, "scripts/e2e/prepare_e2e_database.py"], env=env
    )
    checks.append(prepare)
    if prepare.status != "pass":
        checks.append(Check("browser_e2e", "fail", "browser E2E database preparation failed"))
        return checks, blockers
    checks.append(run_check("browser_e2e", ["pnpm", "--filter", "@ocwp/web", "test:e2e"], env=env))
    return checks, blockers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()

    python_env = dict(__import__("os").environ)
    python_env["PYTHONPATH"] = str(ROOT / "services/platform/src")
    checks = [
        run_check("repository_contract", [sys.executable, "scripts/ci/verify_repository.py"]),
        run_check("python_tests", [sys.executable, "-m", "pytest", "-q"], env=python_env),
        run_check(
            "runtime_http_smoke",
            [sys.executable, "scripts/ci/runtime_http_smoke.py"],
            env=python_env,
        ),
        run_check("frontend_core_tests", ["node", "apps/web/tools/run-core-tests.mjs"]),
        run_check(
            "api_client_core_tests", ["node", "packages/api-client/tools/run-core-tests.mjs"]
        ),
        run_check(
            "frontend_offline_typecheck",
            ["tsc", "-p", "apps/web/tsconfig.offline-check.json", "--pretty", "false"],
        ),
        run_check(
            "openapi_contract",
            [sys.executable, "scripts/contracts/export_openapi.py", "--check"],
            env=python_env,
        ),
        run_check(
            "typescript_api_contract",
            [sys.executable, "scripts/contracts/generate_ts_client.py", "--check"],
        ),
        run_check(
            "typescript_api_typecheck",
            ["tsc", "-p", "packages/api-client/tsconfig.json", "--pretty", "false"],
        ),
    ]

    blockers: list[Check] = []
    postgresql_checks, postgresql_blockers = postgresql_runtime_checks(python_env)
    checks.extend(postgresql_checks)
    blockers.extend(postgresql_blockers)
    for filename, name, reason in (
        (
            "pnpm-lock.yaml",
            "pnpm_lock",
            "registry access is required to produce and verify the lockfile",
        ),
        (
            "uv.lock",
            "uv_lock",
            "registry/cache access is required to produce and verify the lockfile",
        ),
    ):
        if (ROOT / filename).is_file():
            checks.append(Check(name, "pass", filename))
        else:
            blockers.append(Check(name, "blocked", reason))

    tool_probes: dict[str, Check] = {}
    for name, executable, version_args, reason in (
        ("docker", "docker", ["--version"], "Docker CLI is unavailable in the execution container"),
        (
            "pnpm",
            "pnpm",
            ["--version"],
            "pnpm cannot execute because the npm registry is unreachable "
            "or Corepack is not provisioned",
        ),
        (
            "psql",
            "psql",
            ["--version"],
            "PostgreSQL client/server tools are unavailable in the execution container",
        ),
        ("ruff", "ruff", ["--version"], "Ruff is not installed in the execution container"),
        ("mypy", "mypy", ["--version"], "mypy is not installed in the execution container"),
    ):
        probe = probe_tool(name, executable, version_args, reason)
        tool_probes[name] = probe
        (checks if probe.status == "pass" else blockers).append(probe)

    pnpm_probe = tool_probes["pnpm"]
    static_checks, static_blockers = static_analysis_checks(
        pnpm_probe=pnpm_probe,
        ruff_probe=tool_probes["ruff"],
        mypy_probe=tool_probes["mypy"],
        env=python_env,
    )
    checks.extend(static_checks)
    blockers.extend(static_blockers)
    indexeddb_check = indexeddb_runtime_check()
    (checks if indexeddb_check.status != "blocked" else blockers).append(indexeddb_check)
    browser_checks, browser_blockers = browser_runtime_checks(pnpm_probe, python_env)
    checks.extend(browser_checks)
    blockers.extend(browser_blockers)

    failed = [check for check in checks if check.status == "fail"]
    status = "failed" if failed else ("partial" if blockers else "passed")
    report = {
        "schema": 2,
        "release": "V0.1",
        "status": status,
        "metadata": qualification_metadata(),
        "checks": [asdict(check) for check in checks],
        "blockers": [asdict(check) for check in blockers],
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")

    if failed:
        return 1
    if blockers and not args.allow_blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
