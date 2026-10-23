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


def test_full_python_serial_workflow_binds_fixed_pair_and_full_job_budget() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    job = workflow.split("  python-tests:\n", 1)[1].split("\n  verify:", 1)[0]
    assert "timeout-minutes: 55" in job
    assert "timeout-minutes: 35" not in job
    assert "nonce_a: ${{ steps.identity.outputs.nonce_a }}" in job
    assert "nonce_b: ${{ steps.identity.outputs.nonce_b }}" in job
    assert job.count("timeout-minutes: 12") == 1
    assert job.count("timeout-minutes: 18") == 2
    assert job.count("timeout-minutes: 1\n") == 2
    assert job.count("--signal=TERM --kill-after=30s 1020s") == 2
    assert job.count("--signal=TERM --kill-after=5s 55s") == 2
    assert (
        job.index("id: run_a")
        < job.index("id: finalize_a")
        < job.index("id: run_b")
        < job.index("id: finalize_b")
    )
    for shard in ("a", "b"):
        assert job.count(f"--full-python-shard {shard}") == 2
        assert job.count(f'--owned "$RUNNER_TEMP/full-python-{shard}-owned.json"') == 2
        assert job.count(f"--evidence artifacts/full-python/{shard}/receipt.json") == 2
        assert f"artifacts/full-python/{shard}/independent-cleanup.json" in job
    run_b = job.split("id: run_b", 1)[1].split("\n      - name:", 1)[0]
    assert "if: ${{ !cancelled() && steps.finalize_a.outputs.cleanup_verified == 'true' }}" in run_b
    assert "continue-on-error" not in job
    assert "strategy:" not in job
    assert "matrix:" not in job
    assert "--full-python-receipt artifacts/full-python\n" in workflow
    for shard in ("A", "B"):
        assert (
            f"OCWP_FULL_PYTHON_NONCE_{shard}: "
            f"${{{{ needs.python-tests.outputs.nonce_{shard.lower()} }}}}" in workflow
        )
