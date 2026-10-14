#!/usr/bin/env python3
"""Disposable Docker-only qualification; never connects to an operator's stack."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/compose/docker-compose.local.yml"
PG_IMAGE = "postgres:18.4-trixie"


def redact(value: str, secrets: list[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


def validate_config(config: dict[str, object]) -> None:
    services = config["services"]
    assert isinstance(services, dict)
    for name, service in services.items():
        for port in service.get("ports", []):
            assert name == "edge" and port["host_ip"] == "127.0.0.1"
        assert not service.get("privileged", False)
    for name in ("api", "worker", "bootstrap"):
        assert (
            services[name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
        )
    assert "data_net" not in services["edge"]["networks"]
    assert "app_net" not in services["postgres"]["networks"]
    assert config["networks"]["data_net"]["internal"] is True  # type: ignore[index]
    assert config["networks"]["app_net"]["internal"] is True  # type: ignore[index]


def request(
    base: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    token: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(base + path, data=data, headers=headers)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return (
            response.status,
            {key.lower(): val for key, val in response.headers.items()},
            response.read(),
        )


def wait_ready(base: str) -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            code, _, body = request(base, "/health/ready")
            if code == 200 and json.loads(body)["status"] == "ready":
                return
        except (URLError, TimeoutError, OSError, ValueError, KeyError):
            pass
        time.sleep(2)
    raise RuntimeError("edge/API did not become ready within 180 seconds")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=Path("artifacts/local-runtime.json"))
    parser.add_argument(
        "--browser", action="store_true", help="Require installed Playwright Chromium"
    )
    args = parser.parse_args()
    evidence: dict[str, object] = {
        "status": "failed",
        "checks": [],
        "physical_hardware": "not tested",
    }
    checks: list[str] = []
    secrets: list[str] = []
    project = "ocwp-smoke-" + uuid.uuid4().hex[:12]
    env = dict(os.environ)
    # Prevent an ambient operator's project/config/context variables selecting it.
    for name in tuple(env):
        if name.startswith(("COMPOSE_", "OCWP_")):
            del env[name]
    command = ["docker", "compose", "-p", project, "-f", str(COMPOSE)]

    def run(
        parts: list[str], *, check: bool = True, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            parts, cwd=ROOT, env=env, input=stdin, capture_output=True, text=True, timeout=1200
        )
        if check and result.returncode:
            output = redact(result.stdout + result.stderr, secrets)
            raise RuntimeError(f"Command failed ({parts[0]}):\n{output[-12000:]}")
        return result

    def compose(*parts: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run([*command, *parts], check=check)

    with tempfile.TemporaryDirectory(prefix=project + "-", ignore_cleanup_errors=True) as temporary:
        directory = Path(temporary)
        try:
            sys.path.insert(0, str(ROOT))
            from scripts.operations.init_local_secrets import initialize_secrets

            secret_dir = directory / "secrets"
            initialize_secrets(secret_dir, include_admin=True)
            values = {p.stem: p.read_text().strip() for p in secret_dir.iterdir()}
            secrets.extend(values.values())
            restore_file = secret_dir / "restore_url.txt"
            restore_file.write_text(
                values["database_url"].rsplit("/", 1)[0] + "/ocwp_restore_test\n"
            )
            restore_file.chmod(0o600)
            secrets.append(restore_file.read_text().strip())
            backup_dir = directory / "backups"
            backup_dir.mkdir(mode=0o700)
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            env.update(
                OCWP_SECRETS_DIR=str(secret_dir),
                OCWP_BACKUP_DIR=str(backup_dir),
                OCWP_HTTP_PORT=str(port),
                OCWP_IMAGE_TAG=project,
            )
            base = f"http://127.0.0.1:{port}"
            evidence["git_sha"] = run(["git", "rev-parse", "HEAD"]).stdout.strip()
            evidence["docker_version"] = run(
                ["docker", "version", "--format", "{{.Server.Version}}"]
            ).stdout.strip()
            evidence["compose_version"] = compose("version", "--short").stdout.strip()
            evidence["architecture"] = run(
                ["docker", "info", "--format", "{{.Architecture}}"]
            ).stdout.strip()
            config = json.loads(
                compose(
                    "--profile",
                    "bootstrap",
                    "--profile",
                    "operations",
                    "config",
                    "--format",
                    "json",
                ).stdout
            )
            validate_config(config)
            checks.append("resolved_compose_private_ports_migration_dependency_and_networks")
            compose("build", "api", "edge", "operations")
            run(["docker", "pull", PG_IMAGE])
            # Discover image uid/gid, never assume a host account or chmod secrets
            # world-readable. Only this disposable directory is mounted/changed.
            pg_uid = run(
                ["docker", "run", "--rm", "--entrypoint", "id", PG_IMAGE, "-u", "postgres"]
            ).stdout.strip()
            pg_gid = run(
                ["docker", "run", "--rm", "--entrypoint", "id", PG_IMAGE, "-g", "postgres"]
            ).stdout.strip()
            assert pg_uid.isdecimal() and pg_gid.isdecimal()
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--user",
                    "0",
                    "--mount",
                    f"type=bind,source={directory},target=/state",
                    "--entrypoint",
                    "sh",
                    PG_IMAGE,
                    "-ec",
                    "chown 10001:10001 /state/secrets/database_url.txt "
                    "/state/secrets/auth_secret.txt "
                    "/state/secrets/admin_password.txt /state/secrets/restore_url.txt "
                    "/state/backups; "
                    f"chown {pg_uid}:{pg_gid} /state/secrets/postgres_password.txt "
                    "/state/secrets/postgres_admin_password.txt",
                ]
            )
            lan = json.loads(
                compose(
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "--env",
                    "OCWP_LAN_HOST=workshop.example.test",
                    "edge",
                    "caddy",
                    "adapt",
                    "--config",
                    "/etc/caddy/Caddyfile.lan",
                    "--adapter",
                    "caddyfile",
                ).stdout
            )
            listeners = [
                listener
                for server in lan["apps"]["http"]["servers"].values()
                for listener in server["listen"]
            ]
            assert ":8443" in listeners
            assert ":8080" not in listeners
            checks.append("lan_caddy_configuration_parses_without_installing_trust")
            compose("up", "-d")
            wait_ready(base)
            assert compose("ps", "-a", "--format", "json").returncode == 0
            migration_id = compose("ps", "-a", "-q", "migrate").stdout.strip()
            assert (
                run(
                    ["docker", "inspect", "--format", "{{.State.ExitCode}}", migration_id]
                ).stdout.strip()
                == "0"
            )
            checks.append("fresh_volume_secret_backed_migration_and_readiness")
            for name in ("api", "worker"):
                assert compose("exec", "-T", name, "id", "-u").stdout.strip() == "10001"
            assert compose("exec", "-T", "edge", "id", "-u").stdout.strip() == "10001"
            # Prove NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION on the live role.
            flags = compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-Atc",
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication "
                "FROM pg_roles WHERE rolname='ocwp'",
            ).stdout.strip()
            assert flags == "f|f|f|f"
            checks.append("nonroot_processes_and_restricted_database_role")
            bootstrap = json.loads(compose("run", "--rm", "-T", "bootstrap").stdout)
            assert bootstrap["created"] is True
            assert compose("run", "--rm", "-T", "bootstrap", check=False).returncode != 0
            login_payload = {
                "organization_id": bootstrap["organization_id"],
                "username": "admin",
                "password": values["admin_password"],
            }
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(
                base,
                "/api/v1/customers",
                token=token,
                payload={
                    "location_id": bootstrap["location_id"],
                    "display_name": "Disposable runtime customer",
                },
            )
            assert code == 201
            customer_id = json.loads(body)["customer_id"]
            checks.append("first_admin_bootstrap_guard_login_and_customer_creation")
            code, headers, html = request(base, "/")
            assert code == 200 and b'<div id="root">' in html
            assert headers["cache-control"] == "no-cache"
            assert request(base, "/workshop/deep/link")[2] == html
            asset = re.search(rb'src="(/assets/[^\"]+\.js)"', html)
            assert asset
            assert "immutable" in request(base, asset[1].decode())[1]["cache-control"]
            assert request(base, "/assets/missing.js")[0] == 404
            for path in ("/api", "/api/not-a-route", "/health/not-a-route"):
                code, headers, body = request(base, path)
                assert code == 404 and "application/json" in headers["content-type"]
                assert b'<div id="root">' not in body
            for path in ("/sw.js", "/manifest.webmanifest"):
                code, headers, body = request(base, path)
                assert code == 200 and body and headers["cache-control"] == "no-cache"
            checks.append("pwa_static_delivery_cache_policy_and_backend_404_isolation")
            if args.browser:
                browser_input = json.dumps(
                    {
                        "base": base,
                        "organizationId": bootstrap["organization_id"],
                        "password": values["admin_password"],
                    }
                )
                run(["node", "scripts/ci/local_runtime_browser_smoke.mjs"], stdin=browser_input)
                checks.append("caddy_pwa_offline_reload_queue_reconnect_two_browser_convergence")
            else:
                evidence["browser"] = "not run (pass --browser to require it)"
            compose("stop", "api")
            code, _, body = request(base, "/api/v1/auth/me")
            assert code == 502 and b'<div id="root">' not in body
            assert request(base, "/")[0] == 200
            compose("start", "api")
            wait_ready(base)
            checks.append("backend_outage_returns_502_without_spa_fallback")
            # The backup/restore drill uses only a fresh, dedicated DB in this
            # generated Compose project; it cannot target an existing installation.
            compose("run", "--rm", "-T", "operations", "backup", "/backups/generation-1")
            compose("run", "--rm", "-T", "operations", "verify", "/backups/generation-1")
            compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "CREATE DATABASE ocwp_restore_test OWNER ocwp",
            )
            restore_args = (
                "run",
                "--rm",
                "-T",
                "--volume",
                f"{restore_file}:/run/secrets/restore_url:ro",
                "--env",
                "OCWP_RESTORE_DATABASE_URL_FILE=/run/secrets/restore_url",
                "operations",
                "restore",
                "/backups/generation-1",
                "--confirm-empty-target",
            )
            compose(*restore_args)
            assert compose(*restore_args, check=False).returncode != 0
            checks.append("pg18_backup_restore_schema_counts_and_nonempty_target_refusal")
            compose("down")  # Deliberately no --volumes: preserve deployment state.
            compose("up", "-d")
            wait_ready(base)
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(base, f"/api/v1/customers/{customer_id}", token=token)
            assert code == 200 and json.loads(body)["display_name"] == "Disposable runtime customer"
            checks.append("down_up_retains_database_and_authentication")
            logs = compose("logs", "--no-color").stdout
            assert all(secret not in logs for secret in secrets)
            checks.append("container_logs_do_not_contain_generated_credentials")
            evidence["image_ids"] = compose("images", "--format", "json").stdout.strip()
            evidence["status"] = "passed"
        except Exception as exc:
            evidence["error"] = redact(str(exc), secrets)
            print(evidence["error"], file=sys.stderr)
        finally:
            evidence["checks"] = checks
            try:
                # The random project is created by this test, never an operator's
                # project. Its synthetic data/volumes are intentionally disposable.
                compose(
                    "--profile",
                    "bootstrap",
                    "--profile",
                    "operations",
                    "down",
                    "--volumes",
                    "--remove-orphans",
                    check=False,
                )
            except Exception:
                evidence["cleanup"] = f"Inspect and remove disposable project {project} manually"
            if hasattr(os, "getuid"):
                try:
                    run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "--network",
                            "none",
                            "--user",
                            "0",
                            "--mount",
                            f"type=bind,source={directory},target=/state",
                            "--entrypoint",
                            "chown",
                            PG_IMAGE,
                            "-R",
                            f"{os.getuid()}:{os.getgid()}",
                            "/state",
                        ]
                    )
                except Exception:
                    evidence["temporary_files_cleanup"] = "Inspect disposable directory " + str(
                        directory
                    )
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
