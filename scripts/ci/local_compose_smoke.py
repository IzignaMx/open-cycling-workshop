#!/usr/bin/env python3
"""Disposable Docker-only qualification; never connects to an operator's stack."""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
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
JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def disposable_environment(inherited: dict[str, str]) -> dict[str, str]:
    """Never inherit an operator's project, database, credentials or cutover setting."""
    return {
        key: value for key, value in inherited.items() if not key.startswith(("COMPOSE_", "OCWP_"))
    } | {"OCWP_CUTOVER_ENABLED": "true"}


def restored_api_override(restore_file: Path) -> dict[str, object]:
    """A generated API-only switch; workers/migrations retain the original target."""
    return {
        "services": {
            "api": {
                "environment": {"OCWP_DATABASE_URL_FILE": "/run/secrets/restore_url"},
                "secrets": [{"source": "restore_url", "target": "restore_url"}],
            }
        },
        "secrets": {"restore_url": {"file": str(restore_file)}},
    }


class BrowserSmoke:
    """One bounded pipe-only browser session survives the actual restore drill.

    Never forward raw child output: an assertion can contain a bearer token or
    session snapshot. Only the closed phase protocol enters durable evidence.
    """

    def __init__(self, command: list[str], *, env: dict[str, str], timeout: float = 180) -> None:
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.timeout = timeout
        self.buffer = b""

    def __enter__(self) -> BrowserSmoke:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send(self, payload: dict[str, object]) -> None:
        body = (json.dumps(payload) + "\n").encode()
        if len(body) > 16384:
            raise RuntimeError("Browser smoke input exceeds limit")
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(body)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            raise RuntimeError("Browser smoke input pipe closed") from None

    def expect(self, phase: str) -> None:
        deadline = time.monotonic() + self.timeout
        assert self.process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise RuntimeError("Browser smoke phase timed out")
                chunk = os.read(self.process.stdout.fileno(), 4097)
                if not chunk:
                    raise RuntimeError("Browser smoke exited before expected phase")
                self.buffer += chunk
                if len(self.buffer) > 4096:
                    raise RuntimeError("Browser smoke phase exceeds limit")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            message = json.loads(line)
        except (ValueError, UnicodeError):
            raise RuntimeError("Browser smoke emitted invalid phase") from None
        if (
            isinstance(message, dict)
            and set(message) == {"phase", "step"}
            and message["phase"] == "failed"
            and isinstance(message["step"], str)
            and re.fullmatch(r"[a-z_]{1,64}", message["step"])
        ):
            raise RuntimeError("Browser smoke failed during " + message["step"])
        if message != {"phase": phase}:
            raise RuntimeError("Browser smoke emitted unexpected phase")

    def finish(self) -> None:
        try:
            code = self.process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Browser smoke exit timed out") from None
        if code:
            raise RuntimeError("Browser smoke exited unsuccessfully")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout):
            if pipe is not None:
                pipe.close()


def redact(value: str, secrets: list[str]) -> str:
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted]")
    return JWT_PATTERN.sub("[redacted]", value)


def assert_logs_safe(logs: str, secrets: list[str]) -> None:
    # Browser-issued tokens never leave that process. Detect JWT-shaped output
    # too, so those tokens are covered without exporting their value or hash.
    if any(secret and secret in logs for secret in secrets) or JWT_PATTERN.search(logs):
        raise RuntimeError("Container logs contain generated credentials")


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
    env = disposable_environment(dict(os.environ))
    browser: BrowserSmoke | None = None
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
            # Historical REST data predates activation; do not fabricate a cache.
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            assert code == 200 and json.loads(body)["snapshot_protocol"] is None
            activated = json.loads(
                compose(
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "api",
                    "ocwpctl",
                    "cutover",
                    "activate",
                    "--organization-id",
                    bootstrap["organization_id"],
                ).stdout
            )
            original_incarnation = activated["dataset_incarnation"]
            assert activated["changed"] is True and activated["minimum_write_protocol"] == 1
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            advertised = json.loads(body)
            assert code == 200 and advertised["snapshot_protocol"] == "baseline-v1"
            assert advertised["dataset_incarnation"] == original_incarnation
            assert advertised["policy_revision"] == "ocwp-access-baseline-2"
            evidence["cutover_fixture"] = "generated project only, floor 1, baseline-v1"
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
                browser = BrowserSmoke(
                    ["node", "scripts/ci/local_runtime_browser_smoke.mjs"], env=env
                )
                browser.send(
                    {
                        "base": base,
                        "organizationId": bootstrap["organization_id"],
                        "locationId": bootstrap["location_id"],
                        "userId": bootstrap["user_id"],
                        "password": values["admin_password"],
                        "datasetIncarnation": original_incarnation,
                        "historicalCustomerId": customer_id,
                    }
                )
                browser.expect("ready_for_backup")
                checks.append("caddy_pwa_offline_reload_queue_reconnect_two_browser_convergence")
            else:
                evidence["browser"] = "not run (pass --browser to require it)"
                evidence["authenticated_recovery"] = "not run (requires --browser)"
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
            if browser is not None:
                browser.send({"phase": "backup_verified"})
                browser.expect("pending_preserved")
            # No fixture writer may access either DB during restored maintenance.
            compose("stop", "edge", "api", "worker")
            captured_logs = compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
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

            def restored_history() -> str:
                # Hash exact restored records, not merely counts. Only synthetic
                # digests are retained; no user/password/session row is printed.
                return compose(
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "ocwp_restore_test",
                    "-At",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "SELECT 'customers', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY id), '')) FROM customers t "
                    "UNION ALL SELECT 'receipts', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY mutation_id), '')) "
                    "FROM sync_mutation_receipts t "
                    "UNION ALL SELECT 'changes', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY cursor), '')) FROM sync_changes t "
                    "UNION ALL SELECT 'families', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY reference_hash), '')) "
                    "FROM sync_baseline_families t "
                    "UNION ALL SELECT 'original_audit', count(*), md5(coalesce(string_agg("
                    "row_to_json(t)::text, '' ORDER BY id), '')) FROM identity_audit_events t "
                    "WHERE action <> 'organization.dataset_recovered'",
                ).stdout

            history_before = restored_history()
            maintenance = (
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--volume",
                f"{restore_file}:/run/secrets/restore_url:ro",
                "--env",
                "OCWP_DATABASE_URL_FILE=/run/secrets/restore_url",
                "api",
                "ocwpctl",
            )
            recovered = json.loads(
                compose(
                    *maintenance,
                    "cutover",
                    "recover",
                    "--organization-id",
                    bootstrap["organization_id"],
                    "--expected-incarnation",
                    original_incarnation,
                ).stdout
            )
            assert recovered["changed"] is True and recovered["minimum_write_protocol"] == 1
            assert recovered["dataset_incarnation"] != original_incarnation
            status = json.loads(
                compose(
                    *maintenance,
                    "cutover",
                    "status",
                    "--organization-id",
                    bootstrap["organization_id"],
                ).stdout
            )
            audit = status["latest_maintenance_audit"]
            assert status["dataset_incarnation"] == recovered["dataset_incarnation"]
            assert audit["action"] == "organization.dataset_recovered"
            assert audit["before"]["dataset_incarnation"] == original_incarnation
            assert audit["after"]["dataset_incarnation"] == recovered["dataset_incarnation"]
            assert restored_history() == history_before
            # This file contains only a mounted secret-file path, never its URL.
            override = directory / "restored-api.json"
            override.write_text(json.dumps(restored_api_override(restore_file)))
            reopened_command = [*command, "-f", str(override)]
            run([*reopened_command, "up", "-d", "--no-deps", "--force-recreate", "api", "edge"])
            wait_ready(base)
            # Worker remains stopped and cannot write to the original or restored DB.
            worker_id = compose("ps", "-a", "-q", "worker").stdout.strip()
            assert (
                run(
                    ["docker", "inspect", "--format", "{{.State.Running}}", worker_id]
                ).stdout.strip()
                == "false"
            )
            if browser is not None:
                browser.send(
                    {
                        "phase": "restored_api_ready",
                        "datasetIncarnation": recovered["dataset_incarnation"],
                    }
                )
                browser.expect("recovery_verified")
                browser.finish()
                evidence["authenticated_recovery"] = (
                    "passed: old-token 401, backed-up checkpoint 409 with fresh token, "
                    "unchanged journal recovery hold, hidden overlay, fresh same-user work"
                )
            checks.append("pg18_backup_restore_schema_counts_and_nonempty_target_refusal")
            # The unmodified base command returns to the ORIGINAL database, proving
            # its persisted data/auth independently of the reopened restored target.
            captured_logs += compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
            compose("down")  # Deliberately no --volumes: preserve deployment state.
            compose("up", "-d")
            wait_ready(base)
            code, _, body = request(base, "/api/v1/auth/login", payload=login_payload)
            assert code == 200
            token = json.loads(body)["access_token"]
            secrets.append(token)
            code, _, body = request(base, f"/api/v1/customers/{customer_id}", token=token)
            assert code == 200 and json.loads(body)["display_name"] == "Disposable runtime customer"
            code, _, body = request(base, "/api/v1/auth/context", token=token)
            assert code == 200 and json.loads(body)["dataset_incarnation"] == original_incarnation
            checks.append("down_up_retains_database_and_authentication")
            captured_logs += compose("logs", "--no-color").stdout
            assert_logs_safe(captured_logs, secrets)
            checks.append("container_logs_do_not_contain_generated_credentials")
            evidence["image_ids"] = compose("images", "--format", "json").stdout.strip()
            evidence["status"] = "passed"
        except Exception as exc:
            evidence["error"] = redact(str(exc), secrets)
            print(evidence["error"], file=sys.stderr)
        finally:
            if browser is not None:
                browser.close()
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
