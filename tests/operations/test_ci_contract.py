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


def test_full_python_cleanup_diagnostics_are_retained_after_failure() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    job = workflow.split("  python-tests:\n", 1)[1].split("\n  verify:", 1)[0]
    uploads = [step for step in job.split("\n      - ") if "actions/upload-artifact@" in step]
    assert len(uploads) == 1
    assert "if: always()" in uploads[0]
    for shard in ("a", "b"):
        for phase in ("primary", "independent"):
            assert f"artifacts/full-python/{shard}/{phase}-cleanup-diagnostic.json" in uploads[0]


# Phase isolation applies only to the declared GitHub-managed verify service.
# A localhost name/suffix alone is not disposable-database ownership evidence.
_REPEAT_PHASES = (
    ("Repeat sync and order baseline journeys without retries", 5),
    ("Repeat authenticated handoff and lost-ACK fences without retries", 3),
    ("Repeat administration probe clock without retries", 5),
    ("Repeat inventory expiry without retries", 5),
)
_FIXTURE_DSN = "postgresql+psycopg://ocwp:ocwp-test@127.0.0.1:5432/ocwp_e2e"
_PREPARE = "uv run python scripts/ci/prepare_browser_phase.py"


def _verify_steps():
    workflow = Path(".github/workflows/ci.yml").read_text()
    verify = workflow.split("\n  verify:\n", 1)[1]
    steps = verify.split("\n      - ")[1:]
    return verify, {step.splitlines()[0].removeprefix("name: "): step for step in steps}


def test_browser_repeat_phases_bind_the_existing_job_owned_service_and_fresh_fixture():
    verify, steps = _verify_steps()
    service = verify.split("    services:\n", 1)[1].split("    steps:\n", 1)[0]
    for exact in (
        "      postgres:\n",
        "        image: postgres:18.4-trixie\n",
        "          POSTGRES_USER: ocwp\n",
        "          POSTGRES_DB: ocwp_e2e\n",
        "          - 5432:5432\n",
    ):
        assert exact in service
    names = list(steps)
    previous = "Upload direct browser screenshots and traces"
    for name, repeats in _REPEAT_PHASES:
        step = steps[name]
        assert names.index(previous) < names.index(name)
        assert "\n        if:" not in step
        assert "continue-on-error" not in step
        assert "\n        shell: bash\n" in step
        for key in ("OCWP_E2E_DATABASE_URL", "OCWP_DATABASE_URL", "OCWP_TEST_DATABASE_URL"):
            assert f"          {key}: {_FIXTURE_DSN}\n" in step
        assert step.count(_PREPARE) == 1
        assert step.index(_PREPARE) < step.index("pnpm --filter @ocwp/web exec playwright test")
        assert f"--repeat-each={repeats} --retries=0 --workers=1" in step
        assert "          OCWP_E2E_SERVICE_ID: ${{ job.services.postgres.id }}\n" in step
        assert "${{" not in step.replace("${{ job.services.postgres.id }}", "")
        previous = name


def test_repeat_phase_reset_failure_stops_browser_without_real_database(tmp_path):
    import subprocess
    import sys
    import textwrap

    _, steps = _verify_steps()
    # Execute each actual workflow block with closed fake commands, never uv,
    # Playwright, Docker, PostgreSQL or a listener. Bash failure semantics are real.
    command = tmp_path / "command"
    command.write_text(
        f"#!{sys.executable}\n"
        "import os,sys\n"
        "from pathlib import Path\n"
        "args=sys.argv[1:]\n"
        "prepare='scripts/ci/prepare_browser_phase.py' in args\n"
        "label='prepare' if prepare else "
        "('browser' if Path(sys.argv[0]).name=='pnpm' else 'receipt')\n"
        "with open(os.environ['TRACE'],'a') as out: out.write(label+'\\n')\n"
        "if prepare: sys.exit(int(os.environ['PREPARE_EXIT']))\n"
        "if label=='browser': sys.exit(int(os.environ['BROWSER_EXIT']))\n"
    )
    command.chmod(0o700)
    for executable in ("uv", "pnpm"):
        (tmp_path / executable).symlink_to(command)
    for name, _ in (("Prepare browser E2E database", 0), *_REPEAT_PHASES):
        step = steps[name]
        assert "\n        run: |\n" in step
        script = textwrap.dedent(step.split("\n        run: |\n", 1)[1])
        for prepare_exit, browser_exit, bad_output in (
            (0, 0, False),
            (9, 0, False),
            (124, 0, False),
            (137, 0, False),
            (0, 7, False),
            (0, 0, True),
        ):
            if name == "Prepare browser E2E database" and browser_exit:
                continue
            trace = tmp_path / "trace"
            trace.write_text("")
            receipt = tmp_path / "github-output"
            receipt.write_text("")
            result = subprocess.run(
                ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                env={
                    "PATH": str(tmp_path),
                    "TRACE": str(trace),
                    "PREPARE_EXIT": str(prepare_exit),
                    "BROWSER_EXIT": str(browser_exit),
                    "GITHUB_OUTPUT": str(tmp_path if bad_output else receipt),
                    "OCWP_E2E_DATABASE_URL": _FIXTURE_DSN,
                    "OCWP_DATABASE_URL": _FIXTURE_DSN,
                },
                capture_output=True,
                timeout=5,
                check=False,
            )
            assert result.returncode == (prepare_exit or (1 if bad_output else browser_exit))
            calls = trace.read_text().splitlines()
            assert calls[0] == "prepare"
            if prepare_exit or bad_output:
                assert calls == ["prepare"]
                assert receipt.read_text() == ""
            else:
                assert calls.count("prepare") == 1
                assert calls.count("browser") == (
                    0 if name == "Prepare browser E2E database" else 1
                )
                assert receipt.read_text() == "fixture_prepared=true\n"


def test_hosted_aggregate_receives_complete_trusted_phase_acceptance_history():
    _, steps = _verify_steps()
    initial = steps["Prepare browser E2E database"]
    assert "        id: browser_fixture_initial\n" in initial
    assert _PREPARE in initial and "scripts/e2e/prepare_e2e_database.py" not in initial
    identities = [
        ("INITIAL", "browser_fixture_initial", "Prepare browser E2E database"),
        ("SYNC_ORDER", "browser_repeat_sync_order", _REPEAT_PHASES[0][0]),
        ("CUTOVER", "browser_repeat_cutover", _REPEAT_PHASES[1][0]),
        ("ADMINISTRATION", "browser_repeat_administration", _REPEAT_PHASES[2][0]),
        ("INVENTORY", "inventory_expiry_repeat", _REPEAT_PHASES[3][0]),
    ]
    aggregate = steps["Run V0.1 qualification verifier"]
    assert "OCWP_E2E_SERVICE_ID: ${{ job.services.postgres.id }}" in aggregate
    receipt = '''printf 'fixture_prepared=true\\n' >> "$GITHUB_OUTPUT"'''
    for prefix, step_id, name in identities:
        step = steps[name]
        assert f"        id: {step_id}\n" in step
        assert step.count(receipt) == 1
        assert step.index(_PREPARE) < step.index(receipt)
        if prefix != "INITIAL":
            assert step.index(receipt) < step.index("pnpm --filter")
        assert (
            f"OCWP_BROWSER_PREP_{prefix}_OUTCOME: ${{{{ steps.{step_id}.outcome }}}}" in aggregate
        )
        assert (
            f"OCWP_BROWSER_PREP_{prefix}_ACCEPTED: "
            f"${{{{ steps.{step_id}.outputs.fixture_prepared }}}}" in aggregate
        )
