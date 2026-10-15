from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def service(name: str) -> str:
    compose = source("infra/compose/docker-compose.local.yml")
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_]+:|^[a-z]|\Z)", compose, re.M | re.S)
    assert match, f"Missing service {name}"
    return match[1]


def test_local_stack_exposes_only_loopback_edge_and_persists_postgres() -> None:
    compose = source("infra/compose/docker-compose.local.yml")
    assert "127.0.0.1:${OCWP_HTTP_PORT:-8080}:8080" in service("edge")
    for name in ("postgres", "api", "worker", "migrate", "bootstrap", "operations"):
        assert "ports:" not in service(name)
    assert "postgres_data:/var/lib/postgresql" in service("postgres")
    assert "internal: true" in compose
    assert "data_net" not in service("edge")
    assert "app_net" not in service("postgres")


def test_migrations_complete_before_api_worker_and_bootstrap_start() -> None:
    assert "['alembic', 'upgrade', 'head']" in service("migrate")
    for name in ("api", "worker", "bootstrap"):
        assert "migrate:" in service(name)
        assert "condition: service_completed_successfully" in service(name)
    assert "condition: service_healthy" in service("migrate")
    assert "alembic" not in service("api")


def test_production_secrets_are_file_backed_and_have_no_development_values() -> None:
    compose = source("infra/compose/docker-compose.local.yml")
    assert "OCWP_ENVIRONMENT: production" in compose
    assert "OCWP_DATABASE_URL_FILE: /run/secrets/database_url" in compose
    assert "OCWP_AUTH_SECRET_FILE: /run/secrets/auth_secret" in compose
    assert "POSTGRES_PASSWORD_FILE: /run/secrets/postgres_admin_password" in compose
    for name in ("database_url", "auth_secret", "postgres_password", "postgres_admin_password"):
        assert f"/{name}.txt" in compose
    for unsafe in ("ocwp-dev-only", "development-only-secret", "OCWP_DATABASE_URL:", "privileged:"):
        assert unsafe not in compose
    assert "admin_password" not in service("api")
    assert "admin_password" not in service("worker")
    assert "profiles: ['bootstrap']" in service("bootstrap")


def test_application_database_role_is_not_cluster_superuser() -> None:
    script = source("infra/compose/postgres-init/10-application-role.sql")
    assert "CREATE ROLE ocwp LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION" in script
    assert "PASSWORD :'app_password'" in script
    assert "CREATE DATABASE ocwp OWNER ocwp" in script
    assert "log_min_error_statement = 'panic'" in script
    assert "POSTGRES_USER: postgres" in service("postgres")


def test_edge_api_and_assets_never_use_spa_fallback() -> None:
    routes = source("infra/edge/routes.caddy")
    assert "path /api /api/* /health /health/*" in routes
    api = routes.split("handle @backend {", 1)[1].split("\n\t}", 1)[0]
    assert "reverse_proxy api:8000" in api
    assert "try_files" not in api
    assets = routes.split("handle /assets/* {", 1)[1].split("\n\t}", 1)[0]
    assert "immutable" in assets
    assert "try_files" not in assets
    assert 'Cache-Control "no-cache"' in routes
    assert "try_files {path} /index.html" in routes


def test_lan_mode_is_explicit_tls_and_retains_private_services() -> None:
    override = source("infra/compose/docker-compose.lan.yml")
    caddy = source("infra/edge/Caddyfile.lan")
    assert "OCWP_LAN_HOST:?" in override
    assert "OCWP_LAN_BIND_IP:?" in override
    assert "ports: !override" in override
    assert ":8443'" in override
    assert "tls internal" in caddy
    assert "skip_install_trust" in caddy
    assert "auto_https disable_redirects" in caddy
    assert "tls_insecure_skip_verify" not in caddy
    assert "bind 127.0.0.1" in caddy


def test_images_use_locks_build_stages_and_nonroot_runtime() -> None:
    backend = source("infra/docker/platform.local.Dockerfile")
    web = source("infra/docker/web.Dockerfile")
    assert "uv.lock" in backend
    assert "--locked" in backend
    assert "--no-dev" in backend
    assert "--no-editable" in backend
    assert "USER ocwp" in backend
    assert "pnpm install --frozen-lockfile" in web
    assert "pnpm --filter @ocwp/web build" in web
    assert "COPY --from=build /app/apps/web/dist /srv" in web
    assert "USER ocwp" in web
    assert "setcap -r /usr/bin/caddy" in web
    for dockerfile in ("web.Dockerfile", "platform.local.Dockerfile", "operations.Dockerfile"):
        excludes = source(f"infra/docker/{dockerfile}.dockerignore")
        assert "**/node_modules" in excludes
        assert "**/.env*" in excludes
        assert "infra/compose/secrets" in excludes


def test_operations_image_uses_matching_pg18_tools_and_no_socket() -> None:
    dockerfile = source("infra/docker/operations.Dockerfile")
    assert "FROM postgres:18.4-trixie" in dockerfile
    assert "scripts/database" in dockerfile
    assert "--locked" in dockerfile
    assert "USER ocwp" in dockerfile
    assert "docker.sock" not in service("operations")
    assert "profiles: ['operations']" in service("operations")


def test_hosted_workflow_exercises_amd64_runtime_and_arm64_builds() -> None:
    workflow = source(".github/workflows/local-runtime.yml")
    assert "workflow_dispatch:" in workflow
    assert "local_compose_smoke.py" in workflow
    assert "linux/arm64" in workflow
    assert "push: false" in workflow
    assert "local-runtime-evidence" in workflow
    smoke = source("scripts/ci/local_compose_smoke.py")
    for required in ("service_completed_successfully", "NOSUPERUSER", "bootstrap", "stop", "start"):
        assert required in smoke


def test_postgres_health_ignores_temporary_socket_only_initialization_server() -> None:
    assert "pg_isready -h 127.0.0.1" in service("postgres")


def test_migration_job_does_not_receive_authentication_secret() -> None:
    assert "secrets: [database_url]" in service("migrate")
    assert "OCWP_AUTH_SECRET_FILE" not in service("migrate")


def test_smoke_redaction_removes_longer_secrets_first() -> None:
    from scripts.ci.local_compose_smoke import redact

    assert redact("secret-url secret", ["secret", "secret-url"]) == "[redacted] [redacted]"


def test_smoke_rejects_accidentally_exposed_database_port() -> None:
    import pytest

    from scripts.ci.local_compose_smoke import validate_config

    with pytest.raises(AssertionError):
        validate_config({"services": {"postgres": {"ports": [{"host_ip": "0.0.0.0"}]}}})


def test_cutover_opt_in_is_scoped_to_generated_disposable_environment(tmp_path) -> None:
    from scripts.ci.local_compose_smoke import disposable_environment

    inherited = {
        "PATH": "/bin",
        "COMPOSE_PROJECT_NAME": "operator-project",
        "OCWP_DATABASE_URL": "postgresql://operator/private",
        "OCWP_AUTH_SECRET": "operator-secret",
        "OCWP_CUTOVER_ENABLED": "false",
    }
    env = disposable_environment(inherited)
    assert env == {"PATH": "/bin", "OCWP_CUTOVER_ENABLED": "true"}
    assert inherited["OCWP_CUTOVER_ENABLED"] == "false"
    assert "OCWP_CUTOVER_ENABLED: ${OCWP_CUTOVER_ENABLED:-false}" in source(
        "infra/compose/docker-compose.local.yml"
    )


def test_restore_override_changes_only_disposable_api_secret(tmp_path) -> None:
    from scripts.ci.local_compose_smoke import restored_api_override

    restore_file = tmp_path / "secrets" / "restore_url.txt"
    config = restored_api_override(restore_file)
    assert config == {
        "services": {
            "api": {
                "environment": {"OCWP_DATABASE_URL_FILE": "/run/secrets/restore_url"},
                "secrets": [{"source": "restore_url", "target": "restore_url"}],
            }
        },
        "secrets": {"restore_url": {"file": str(restore_file)}},
    }
    assert "postgresql" not in str(config)


def test_browser_handshake_is_bounded_and_does_not_echo_child_output() -> None:
    import os
    import sys

    import pytest

    from scripts.ci.local_compose_smoke import BrowserSmoke

    secret = "test-secret-never-in-error"
    for output in (secret, "x" * 5000, '{"phase":"wrong"}', '{"phase":"ready","token":"x"}'):
        with BrowserSmoke(
            [sys.executable, "-c", f"print({output!r}, flush=True)"],
            env=dict(os.environ),
            timeout=1,
        ) as browser:
            with pytest.raises(RuntimeError) as error:
                browser.expect("ready")
            assert secret not in str(error.value)
            assert output not in str(error.value)


def test_browser_handshake_retains_process_across_phases() -> None:
    import os
    import sys

    from scripts.ci.local_compose_smoke import BrowserSmoke

    script = (
        "import json,sys; "
        "first=json.loads(sys.stdin.readline()); "
        "assert first['password']=='synthetic'; "
        "print(json.dumps({'phase':'ready_for_backup'}),flush=True); "
        "assert json.loads(sys.stdin.readline())=={'phase':'backup_verified'}; "
        "print(json.dumps({'phase':'pending_preserved'}),flush=True)"
    )
    with BrowserSmoke([sys.executable, "-c", script], env=dict(os.environ), timeout=1) as browser:
        browser.send({"password": "synthetic"})
        browser.expect("ready_for_backup")
        browser.send({"phase": "backup_verified"})
        browser.expect("pending_preserved")
        browser.finish()


def test_browser_handshake_times_out_without_hanging() -> None:
    import os
    import sys
    import time

    import pytest

    from scripts.ci.local_compose_smoke import BrowserSmoke

    start = time.monotonic()
    with (
        BrowserSmoke(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ),
            timeout=0.05,
        ) as browser,
        pytest.raises(RuntimeError, match="timed out"),
    ):
        browser.expect("ready_for_backup")
    assert time.monotonic() - start < 3


def test_floor_one_restore_retains_all_eleven_substantive_checks() -> None:
    import ast

    smoke = source("scripts/ci/local_compose_smoke.py")
    tree = ast.parse(smoke)
    checks = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "checks"
        and node.func.attr == "append"
    }
    assert checks == {
        "resolved_compose_private_ports_migration_dependency_and_networks",
        "lan_caddy_configuration_parses_without_installing_trust",
        "fresh_volume_secret_backed_migration_and_readiness",
        "nonroot_processes_and_restricted_database_role",
        "first_admin_bootstrap_guard_login_and_customer_creation",
        "pwa_static_delivery_cache_policy_and_backend_404_isolation",
        "caddy_pwa_offline_reload_queue_reconnect_two_browser_convergence",
        "backend_outage_returns_502_without_spa_fallback",
        "pg18_backup_restore_schema_counts_and_nonempty_target_refusal",
        "down_up_retains_database_and_authentication",
        "container_logs_do_not_contain_generated_credentials",
    }
    assert '"--expected-incarnation"' in smoke
    assert '"--no-deps", "--force-recreate", "api", "edge"' in smoke
    assert smoke.index('"backup_verified"') < smoke.index(
        'compose("stop", "edge", "api", "worker")'
    )
    assert smoke.index('"pending_preserved"') < smoke.index("compose(*restore_args)")
    compact = re.sub(r"\s+", "", smoke)
    assert compact.index('"cutover","recover"') < compact.index('"restored_api_ready"')


def test_log_check_catches_browser_tokens_without_transmitting_them() -> None:
    import pytest

    from scripts.ci.local_compose_smoke import assert_logs_safe

    assert_logs_safe("GET /api/v1/auth/me HTTP/1.1 200 OK", ["generated-password"])
    for log in ("generated-password", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature"):
        with pytest.raises(RuntimeError) as error:
            assert_logs_safe(log, ["generated-password"])
        assert log not in str(error.value)


def test_browser_protocol_unit_cases() -> None:
    import subprocess

    result = subprocess.run(
        ["node", "--test", "tests/operations/local_runtime_browser_protocol.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_reads_current_partition_and_preserves_immutable_work() -> None:
    browser = source("scripts/ci/local_runtime_browser_smoke.mjs")
    for required in (
        "ocwp-authenticated-v1",
        "operationJournal",
        "operationDelivery",
        "cacheRecords",
        "[principalKey+locationId]",
        "[partitionId+entityType]",
        "data-runtime-state",
        "baselineComplete",
        "historicalCustomerId",
        "datasetIncarnation",
        "held_recovery",
        "assert.deepEqual(held.journal, pendingState.journal)",
        "assert.equal(refused.status, 409)",
        "'context_changed'",
        "oldSession.token",
        "pendingSession",
        "backup_verified",
        "restored_api_ready",
        "recovery_verified",
    ):
        assert required in browser
    for unsafe in ("page.route(", "context.route(", "recordVideo", "tracing.start", ".screenshot("):
        assert unsafe not in browser
    assert "indexedDB.open('ocwp')" not in browser


def test_smoke_redacts_unexported_browser_jwt_from_failure_output() -> None:
    from scripts.ci.local_compose_smoke import redact

    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature"
    assert redact(f"failure with {token}", []) == "failure with [redacted]"


def test_failure_diagnostic_capture_redacts_complete_output() -> None:
    import os
    import sys

    from scripts.ci.local_compose_smoke import diagnostic_capture

    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhIn0.signature"
    result = diagnostic_capture(
        [sys.executable, "-c", f"import sys; print('generated-password {token}', file=sys.stderr)"],
        env=dict(os.environ),
        secrets=["generated-password"],
    )
    assert result == {"status": "captured", "returncode": 0, "output": "[redacted] [redacted]\n"}


def test_failure_diagnostic_overflow_discards_partial_secret_and_reaps_child() -> None:
    import os
    import sys
    import time

    from scripts.ci.local_compose_smoke import diagnostic_capture

    started = time.monotonic()
    result = diagnostic_capture(
        [
            sys.executable,
            "-c",
            "import sys,time; print('prefix-'+'secret'*1000, flush=True); time.sleep(30)",
        ],
        env=dict(os.environ),
        secrets=["secret" * 1000],
        max_bytes=100,
    )
    assert result == {"status": "output_limit"}
    assert time.monotonic() - started < 3


def test_failure_diagnostic_timeout_and_missing_command_never_echo_raw_output() -> None:
    import os
    import sys
    import time

    from scripts.ci.local_compose_smoke import diagnostic_capture

    started = time.monotonic()
    result = diagnostic_capture(
        [
            sys.executable,
            "-c",
            "import time; print('unlisted-sensitive-output',flush=True); time.sleep(30)",
        ],
        env=dict(os.environ),
        secrets=[],
        timeout=0.05,
    )
    assert result == {"status": "timeout"}
    assert time.monotonic() - started < 3
    assert diagnostic_capture(
        ["/definitely-missing-diagnostic-command"], env=dict(os.environ), secrets=[]
    ) == {"status": "unavailable"}


def test_failure_diagnostics_use_project_bound_read_only_commands_and_allowlisted_states(
    monkeypatch,
) -> None:
    import json

    from scripts.ci import local_compose_smoke as module

    command = ["docker", "compose", "-p", "ocwp-smoke-fixture", "-f", "/fixture/compose.yml"]
    calls = []

    def capture(parts, **kwargs):
        calls.append((parts, kwargs))
        if "ps" in parts:
            output = json.dumps(
                [
                    {
                        "Service": "api",
                        "State": "running",
                        "Health": "healthy",
                        "ExitCode": 0,
                        "Command": "never-emit-command",
                        "Publishers": "never-emit-network-details",
                    },
                    {"Service": "operator-service", "State": "running", "ExitCode": 0},
                    {"Service": "edge", "State": "unexpected-sensitive-state", "ExitCode": True},
                ]
            )
        else:
            output = "safe diagnostic log\n"
        return {"status": "captured", "returncode": 0, "output": output}

    monkeypatch.setattr(module, "diagnostic_capture", capture)
    result = module.failure_diagnostics(command, env={"PATH": "/bin"}, secrets=["synthetic"])
    assert result["containers"] == [
        {"service": "api", "state": "running", "health": "healthy", "exit_code": 0},
        {"service": "edge", "state": "unknown", "health": "unknown", "exit_code": None},
    ]
    assert set(result["logs"]) == {"api", "edge", "migrate", "postgres", "worker"}
    serialized = json.dumps(result)
    for forbidden in ("never-emit", "operator-service", "unexpected-sensitive-state"):
        assert forbidden not in serialized
    assert len(calls) == 6
    assert calls[0][0] == [*command, "ps", "--all", "--format", "json"]
    for parts, kwargs in calls:
        assert parts[: len(command)] == command
        assert kwargs == {"env": {"PATH": "/bin"}, "secrets": ["synthetic"]}
        if "logs" in parts:
            assert parts[len(command) : -1] == ["logs", "--no-color", "--tail", "40"]


def test_failure_diagnostics_are_recorded_before_cleanup_without_changing_readiness() -> None:
    smoke = source("scripts/ci/local_compose_smoke.py")
    handler = smoke.split("except Exception as exc:", 1)[1]
    assert handler.index('evidence["error"]') < handler.index("failure_diagnostics(")
    assert handler.index("failure_diagnostics(") < handler.index("browser.close()")
    assert handler.index("failure_diagnostics(") < handler.index("branding_probe.cleanup()")
    assert handler.index("failure_diagnostics(") < handler.index('"--volumes"')
    assert "time.monotonic() + 180" in smoke
    assert "time.sleep(2)" in smoke


def test_completed_diagnostic_terminates_same_group_descendant_with_detached_stdio() -> None:
    import os
    import signal
    import sys
    import time
    from contextlib import suppress

    import pytest

    from scripts.ci.local_compose_smoke import diagnostic_capture

    if sys.platform != "linux":
        pytest.skip("Linux hosted process-group regression uses /proc state")
    script = (
        "import subprocess,sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "print(child.pid,flush=True)"
    )
    result = diagnostic_capture([sys.executable, "-c", script], env=dict(os.environ), secrets=[])
    assert result["status"] == "captured" and result["returncode"] == 0
    pid = int(str(result["output"]).strip())
    state_file = Path(f"/proc/{pid}/stat")
    deadline = time.monotonic() + 1
    try:
        while state_file.exists() and time.monotonic() < deadline:
            try:
                state = state_file.read_text().split()[2]
            except (FileNotFoundError, ProcessLookupError):
                return  # init reaped the terminated orphan after exists().
            if state == "Z":
                return  # Orphan is terminated; only its adopting init can reap it.
            time.sleep(0.01)
        assert not state_file.exists(), "completed diagnostic left its descendant running"
    finally:
        with suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
