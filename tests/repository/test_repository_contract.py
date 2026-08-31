from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_contract_has_required_workspace_and_governance_files() -> None:
    required = [
        "LICENSE",
        "README.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "GOVERNANCE.md",
        "MAINTAINERS.md",
        "ARCHITECTURE.md",
        "package.json",
        "pnpm-workspace.yaml",
        "pyproject.toml",
        "tsconfig.base.json",
        ".python-version",
        ".nvmrc",
        "scripts/ci/verify_repository.py",
    ]

    missing = [path for path in required if not (ROOT / path).exists()]
    assert missing == [], f"missing repository contract files: {missing}"


def test_workspace_directories_match_engineering_spec() -> None:
    required_dirs = [
        "apps/web",
        "services/platform",
        "packages/ui",
        "packages/api-client",
        "packages/plugin-sdk",
        "packages/branding",
        "infra/compose",
        "fixtures/minimal",
        "fixtures/demo-workshop",
        "fixtures/load",
    ]

    missing = [path for path in required_dirs if not (ROOT / path).is_dir()]
    assert missing == [], f"missing workspace directories: {missing}"


def test_plugin_sdk_workspace_has_a_versioned_manifest() -> None:
    required = [
        "packages/plugin-sdk/package.json",
        "packages/plugin-sdk/src/index.ts",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert missing == [], f"missing plugin SDK workspace files: {missing}"


def test_static_analysis_configuration_is_versioned() -> None:
    required = [
        "ruff.toml",
        "mypy.ini",
        "eslint.config.mjs",
        ".prettierrc.json",
        ".prettierignore",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert missing == [], f"missing static-analysis configuration: {missing}"


def test_web_workspace_wires_generated_api_client_and_same_origin_dev_proxy() -> None:
    import json

    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    assert package["dependencies"]["@ocwp/api-client"] == "workspace:*"

    tsconfig = json.loads((ROOT / "apps/web/tsconfig.json").read_text(encoding="utf-8"))
    assert tsconfig["compilerOptions"]["paths"]["@ocwp/api-client"] == [
        "../../packages/api-client/src/index.ts"
    ]

    vite_config = (ROOT / "apps/web/vite.config.ts").read_text(encoding="utf-8")
    assert "'/api'" in vite_config
    assert "http://127.0.0.1:8000" in vite_config


def test_api_client_exposes_a_core_test_runner_for_ci() -> None:
    import json

    package = json.loads((ROOT / "packages/api-client/package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test:core"] == "node tools/run-core-tests.mjs"
    assert (ROOT / "packages/api-client/tools/run-core-tests.mjs").is_file()


def test_ci_and_v01_verifier_execute_api_client_behavior_tests() -> None:
    verifier = (ROOT / "scripts/ci/verify_v01.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "api_client_core_tests" in verifier
    assert "packages/api-client/tools/run-core-tests.mjs" in verifier
    assert "Run API client core tests" in workflow
    assert "pnpm --filter @ocwp/api-client test:core" in workflow


def test_root_scripts_and_ci_use_normative_uv_and_static_quality_gates() -> None:
    import json

    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert "uv run ruff check" in package["scripts"]["lint"]
    assert "uv run mypy" in package["scripts"]["typecheck"]
    assert "uv run pytest" in package["scripts"]["test"]

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "astral-sh/setup-uv@" in workflow
    assert "uv sync --all-packages --group dev" in workflow
    assert "uv run ruff check" in workflow
    assert "uv run mypy" in workflow
    assert "pnpm exec eslint ." in workflow
    assert "pnpm exec prettier --check" in workflow


def test_security_workflow_uses_uv_for_python_auditing() -> None:
    workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
    assert "astral-sh/setup-uv@" in workflow
    assert "uvx pip-audit" in workflow
    assert "python -m pip install" not in workflow


def test_reuse_configuration_and_hosted_license_gate_are_versioned() -> None:
    reuse = (
        (ROOT / "REUSE.toml").read_text(encoding="utf-8") if (ROOT / "REUSE.toml").exists() else ""
    )
    security = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
    assert 'SPDX-License-Identifier = "AGPL-3.0-only"' in reuse
    assert "Open Cycling Workshop Platform contributors" in reuse
    assert "uvx reuse lint" in security


def test_compose_routes_healthchecks_through_database_readiness() -> None:
    compose = (ROOT / "infra/compose/docker-compose.dev.yml").read_text(encoding="utf-8")
    assert "/health/ready" in compose
    assert "/health/live" not in compose


def test_platform_container_uses_uv_instead_of_pip() -> None:
    dockerfile = (ROOT / "infra/docker/platform.Dockerfile").read_text(encoding="utf-8")
    assert "ghcr.io/astral-sh/uv:" in dockerfile
    assert "uv pip install --system" in dockerfile
    assert "pip install" not in dockerfile.replace("uv pip install", "")


def test_hosted_browser_e2e_contract_is_versioned() -> None:
    import json

    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["@playwright/test"] == "1.62.0"
    assert package["devDependencies"]["@axe-core/playwright"] == "4.12.1"
    assert package["scripts"]["test:e2e"] == "playwright test"
    assert (ROOT / "apps/web/playwright.config.ts").is_file()
    assert (ROOT / "apps/web/e2e/customer-offline-sync.spec.ts").is_file()
    assert (ROOT / "scripts/e2e/prepare_e2e_database.py").is_file()

    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Install Playwright Chromium" in workflow
    assert "Prepare browser E2E database" in workflow
    assert "Run browser E2E" in workflow
    assert "pnpm --filter @ocwp/web exec playwright install --with-deps chromium" in workflow
    assert "pnpm --filter @ocwp/web test:e2e" in workflow


def test_web_build_declares_real_react_type_dependencies() -> None:
    import json

    web = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    ui = json.loads((ROOT / "packages/ui/package.json").read_text(encoding="utf-8"))
    assert web["devDependencies"]["@types/react"] == "19.2.17"
    assert web["devDependencies"]["@types/react-dom"] == "19.2.3"
    assert ui["devDependencies"]["@types/react"] == "19.2.17"
    assert (ROOT / "apps/web/src/vite-env.d.ts").is_file()


def test_ci_postgres_service_healthcheck_matches_the_e2e_database_name() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "POSTGRES_DB: ocwp_e2e" in workflow
    assert "pg_isready -U ocwp -d ocwp_e2e" in workflow
    assert "pg_isready -U ocwp -d ocwp_test" not in workflow


def test_hosted_browser_e2e_uses_the_production_pwa_build() -> None:
    config = (ROOT / "apps/web/playwright.config.ts").read_text(encoding="utf-8")
    # Assert the behavior tokens (production preview under CI, dev server
    # locally) instead of a formatting-sensitive single-line ternary.
    assert "process.env.CI" in config
    assert "'pnpm exec vite preview --host 127.0.0.1 --port 5173'" in config
    assert "'pnpm dev -- --host 127.0.0.1'" in config


def test_ci_publishes_a_v01_qualification_artifact() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Run V0.1 qualification verifier" in workflow
    assert "scripts/ci/verify_v01.py --json-out artifacts/v0.1-qualification.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "name: v0.1-qualification" in workflow
    assert "path: artifacts/v0.1-qualification.json" in workflow


def test_golden_slice_requires_service_worker_offline_reload_evidence() -> None:
    spec = (ROOT / "apps/web/e2e/customer-offline-sync.spec.ts").read_text(encoding="utf-8")
    assert "navigator.serviceWorker.ready" in spec
    assert "firstPage.reload" in spec
    assert "getByText('Operación de taller que no se detiene cuando falla Internet.')" in spec


def test_repository_has_manual_actions_and_master_agent_loop_v02() -> None:
    required = [
        "MANUAL-ACTIONS-CHECKLIST.md",
        "scripts/repository/publish-authoritative-bundle.sh",
        "AGENTS.md",
        "docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md",
    ]
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert missing == [], f"missing repository handoff artifacts: {missing}"

    checklist = (ROOT / "MANUAL-ACTIONS-CHECKLIST.md").read_text(encoding="utf-8")
    loop = (
        ROOT / "docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md"
    ).read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    for blocker in [
        "uv.lock",
        "pnpm-lock.yaml",
        "PostgreSQL 18.4",
        "IndexedDB",
        "Windows",
        "Android",
        "backup",
        "restore",
    ]:
        assert blocker in checklist

    assert "MANUAL-ACTIONS-CHECKLIST.md" in loop
    assert "execution-state.yaml" in loop
    assert "do not wait for a new human prompt" in loop
    assert "Master Agent Loop v0.2" in agents


def test_readme_python_verification_includes_repository_root() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "PYTHONPATH=.:services/platform/src pytest -q" in readme
