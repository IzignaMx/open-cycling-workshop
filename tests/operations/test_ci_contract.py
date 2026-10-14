from pathlib import Path


def test_ci_workflow_runs_repository_backend_frontend_and_contract_checks() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()

    for required in (
        "verify_repository.py",
        "pytest",
        "pnpm --filter @ocwp/web test:core",
        "runtime_http_smoke.py",
        "pnpm --filter @ocwp/web build",
        "typecheck:offline",
        "export_openapi.py --check",
        "postgres:18.4-trixie",
    ):
        assert required in workflow


def test_security_workflow_has_secret_dependency_and_code_scans() -> None:
    workflow = Path(".github/workflows/security.yml").read_text()
    for required in ("gitleaks", "pip-audit", "trivy"):
        assert required in workflow.lower()


def test_ci_supports_manual_dispatch_and_exports_generated_lockfiles() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "workflow_dispatch:" in workflow
    assert "Generate missing lockfiles" in workflow
    assert "uv lock" in workflow
    assert "pnpm install --lockfile-only --no-frozen-lockfile" in workflow
    assert "name: v0.1-lockfiles" in workflow
    assert "uv.lock" in workflow
    assert "pnpm-lock.yaml" in workflow


def test_security_supports_manual_dispatch() -> None:
    workflow = Path(".github/workflows/security.yml").read_text()
    assert "workflow_dispatch:" in workflow


def test_direct_browser_evidence_upload_immediately_follows_e2e() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    steps = workflow.split("\n      - ")[1:]
    names = [step.splitlines()[0].removeprefix("name: ") for step in steps]
    upload_name = "Upload direct browser screenshots and traces"
    assert names.count(upload_name) == 1
    upload_index = names.index(upload_name)
    assert upload_index == names.index("Run browser E2E") + 1
    for later_step in (
        "Repeat sync and order baseline journeys without retries",
        "Repeat authenticated handoff and lost-ACK fences without retries",
        "Run V0.1 qualification verifier",
    ):
        assert upload_index < names.index(later_step)
    assert "\n        if: always()\n" in steps[upload_index]
