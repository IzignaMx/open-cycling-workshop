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
