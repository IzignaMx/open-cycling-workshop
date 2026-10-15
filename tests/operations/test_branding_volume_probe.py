"""Contracts for a Docker-only probe; these tests do not execute Docker."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.ci.branding_volume_probe import (
    BrandingVolumeProbe,
    assert_profile_equal,
    synthetic_png,
)

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "ocwp-smoke-123456abcdef"
ORGANIZATION = "00000000-0000-4000-8000-000000000001"
LOCATION = "00000000-0000-4000-8000-000000000002"
INCARNATION = "00000000-0000-4000-8000-000000000003"
RESTORED_INCARNATION = "00000000-0000-4000-8000-000000000004"


def profile() -> dict[str, object]:
    data = synthetic_png()
    return {
        "schema_version": 1,
        "organization_id": ORGANIZATION,
        "location_id": LOCATION,
        "dataset_incarnation": INCARNATION,
        "version": 1,
        "display_name": "Synthetic volume proof",
        "palette_id": "jade",
        "logo_state": "available",
        "logo_diagnostic": None,
        "updated_at": "2026-10-14T00:00:00Z",
        "updated_by": "synthetic-owner",
        "logo": {
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_count": len(data),
            "width": 2,
            "height": 2,
            "mime_type": "image/png",
            "png_base64": base64.b64encode(data).decode("ascii"),
        },
    }


def test_exact_profile_proof_rejects_changed_bytes_metadata_or_incarnation() -> None:
    original = profile()
    restored = original | {"dataset_incarnation": RESTORED_INCARNATION}
    assert (
        assert_profile_equal(original, restored, restored=True)
        == hashlib.sha256(synthetic_png()).hexdigest()
    )
    for field, value in (
        ("display_name", "wrong"),
        ("palette_id", "bosque"),
        ("version", 2),
        ("dataset_incarnation", INCARNATION),
        ("organization_id", "wrong"),
    ):
        with pytest.raises(RuntimeError):
            assert_profile_equal(original, restored | {field: value}, restored=True)
    corrupted = copy.deepcopy(restored)
    corrupted["logo"]["png_base64"] = base64.b64encode(b"wrong").decode()
    with pytest.raises(RuntimeError):
        assert_profile_equal(original, corrupted, restored=True)


def test_probe_refuses_operator_projects_before_any_command(tmp_path: Path) -> None:
    calls: list[object] = []
    with pytest.raises(ValueError, match="disposable"):
        BrandingVolumeProbe(
            project="operator-project",
            command=["docker", "compose", "-p", "operator-project"],
            directory=tmp_path,
            run=lambda *args, **kwargs: calls.append(args),
            secrets=[],
        )
    assert not calls


def test_probe_secret_is_generated_target_only_and_not_in_argv(tmp_path: Path) -> None:
    directory = tmp_path / (PROJECT + "-temporary")
    (directory / "secrets").mkdir(parents=True)
    calls: list[object] = []
    probe = BrandingVolumeProbe(
        project=PROJECT,
        command=[
            "docker",
            "compose",
            "-p",
            PROJECT,
            "-f",
            str(ROOT / "infra/compose/docker-compose.local.yml"),
        ],
        directory=directory,
        run=lambda *args, **kwargs: calls.append(args),
        secrets=[],
    )
    secret = probe.prepare_restore_secret("postgresql+psycopg://ocwp:synthetic@postgres:5432/ocwp")
    assert secret.read_text().strip().endswith("/ocwp_branding_restore_test")
    assert secret.stat().st_mode & 0o777 == 0o600
    assert not calls
    with pytest.raises(FileExistsError):
        probe.prepare_restore_secret("postgresql+psycopg://ocwp:synthetic@postgres:5432/ocwp")


class DockerFixture:
    """In-memory command boundary only; passing is NOT Docker/runtime evidence."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls: list[tuple[list[str], str | None]] = []
        self.created = False
        self.removed = False
        self.running = True
        self.started = "source-start-1"
        self.restored_started = "restore-start-1"
        self.bad_root = False
        self.bad_mount = False
        self.foreign_volume = False
        self.foreign_container = False
        self.stale_accepted = False
        self.restored_profile = profile() | {"dataset_incarnation": RESTORED_INCARNATION}
        self.authority = {
            "user_id": "bootstrap-user",
            "organization_id": ORGANIZATION,
            "location_id": LOCATION,
            "display_name": "Admin",
            "capabilities": ["*"],
        }
        self.changed_authority = False
        self.source_volume = PROJECT + "_branding_assets"

    def host(self, base: str, path: str, **kwargs: object) -> tuple[int, dict[str, object]]:
        assert base == "http://127.0.0.1:12345"
        token = kwargs.get("token", "")
        if path.endswith("/login"):
            return 200, {"access_token": "private-source-token"}
        if path.endswith("/me"):
            if token == "private-bootstrap-token":
                return 200, self.authority | (
                    {"capabilities": ["*", "branding.read"]} if self.changed_authority else {}
                )
            return 200, {
                "user_id": "synthetic-owner",
                "location_id": None,
                "capabilities": ["branding.read", "branding.write"],
            }
        assert path.endswith("/branding")
        if token == "private-bootstrap-token":
            return 403, {}
        if kwargs.get("method") == "PUT":
            assert kwargs["payload"]["expected_version"] == 0
        return 200, profile()

    def container(self, service: str) -> dict[str, object]:
        restored = service == "branding-proof-api"
        from scripts.ci.branding_volume_probe import ASSET_ROOT, LABEL

        labels = {"com.docker.compose.project": PROJECT, "com.docker.compose.service": service}
        if restored:
            labels[LABEL] = "foreign" if self.foreign_container else PROJECT
        mounts = [
            {
                "Destination": ASSET_ROOT,
                "Type": "volume",
                "RW": True,
                "Name": PROJECT + "_branding_probe_assets"
                if restored and not self.bad_mount
                else self.source_volume,
            }
        ]
        if restored:
            mounts += [
                {
                    "Destination": "/run/secrets/branding_restore_url",
                    "Type": "bind",
                    "RW": False,
                    "Source": str(self.directory / "secrets/branding_restore_url.txt"),
                },
                {"Destination": "/run/secrets/auth_secret", "Type": "bind", "RW": False},
                {"Destination": "/tmp", "Type": "tmpfs", "RW": True},
            ]
        return {
            "Id": "id-" + service,
            "Config": {
                "Labels": labels,
                "User": "10001:10001" if restored else "ocwp",
                "Env": ["OCWP_DATABASE_URL_FILE=/run/secrets/branding_restore_url"]
                if restored
                else [],
            },
            "State": {
                "Running": True if restored else self.running,
                "StartedAt": self.restored_started if restored else self.started,
            },
            "Mounts": mounts,
        }

    def __call__(
        self, parts: list[str], *, check: bool = True, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        from scripts.ci.branding_volume_probe import HTTP_PROBE, LABEL, ROOT_PROBE

        self.calls.append((parts, stdin))
        code = 0
        output: object = ""
        if parts[:3] == ["docker", "volume", "inspect"]:
            if parts[-1] == self.source_volume:
                output = [
                    {
                        "Name": self.source_volume,
                        "Labels": {
                            "com.docker.compose.project": PROJECT,
                            "com.docker.compose.volume": "branding_assets",
                        },
                    }
                ]
            elif self.created:
                output = [
                    {
                        "Name": PROJECT + "_branding_probe_assets",
                        "Labels": {LABEL: "foreign" if self.foreign_volume else PROJECT},
                    }
                ]
            else:
                code = 1
        elif parts[:3] == ["docker", "volume", "create"]:
            self.created = True
        elif parts[:3] == ["docker", "volume", "rm"]:
            self.removed = True
        elif parts[:2] == ["docker", "inspect"]:
            service = (
                "branding-proof-api"
                if parts[-1] == PROJECT + "-branding-proof-api"
                else parts[-1].removeprefix("id-")
            )
            output = [self.container(service)]
        elif parts[:2] == ["docker", "restart"]:
            self.restored_started = "restore-start-2"
        elif parts[-1] == ROOT_PROBE:
            output = {
                "uid": 0 if self.bad_root else 10001,
                "gid": 10001,
                "owner": 10001,
                "group": 10001,
                "mode": 0o700,
                "directory": True,
            }
        elif parts[-1] == HTTP_PROBE:
            message = json.loads(stdin)
            if message["path"] == "/health/ready":
                output = {"code": 200, "body": {"status": "ready"}}
            elif message["path"].endswith("/login"):
                output = {"code": 200, "body": {"access_token": "private-restored-token"}}
            elif message["token"] == "private-source-token" and not self.stale_accepted:
                output = {"code": 401, "body": {}}
            else:
                output = {"code": 200, "body": self.restored_profile}
        elif parts[:2] == ["docker", "compose"]:
            if "ps" in parts:
                output = "id-" + parts[-1]
            elif "branding-proof-restore" in parts:
                output = {
                    "status": "branding_restore_checked",
                    "profiles_checked": 1,
                    "asset_references_checked": 1,
                    "incarnations_rotated": 1,
                    "legacy_organizations_activated": 0,
                }
        result = subprocess.CompletedProcess(
            parts, code, json.dumps(output) if not isinstance(output, str) else output, ""
        )
        if check and code:
            raise RuntimeError("mock command failed")
        return result


@pytest.fixture
def fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[BrandingVolumeProbe, DockerFixture]:
    directory = tmp_path / (PROJECT + "-temporary")
    (directory / "secrets").mkdir(parents=True)
    docker = DockerFixture(directory)
    probe = BrandingVolumeProbe(
        project=PROJECT,
        command=[
            "docker",
            "compose",
            "-p",
            PROJECT,
            "-f",
            str(ROOT / "infra/compose/docker-compose.local.yml"),
        ],
        directory=directory,
        run=docker,
        secrets=["private-password", "private-bootstrap-token"],
    )
    probe.prepare_restore_secret("postgresql+psycopg://ocwp:private-password@postgres:5432/ocwp")
    monkeypatch.setattr("scripts.ci.branding_volume_probe.host_request", docker.host)
    return probe, docker


def seed(probe: BrandingVolumeProbe) -> None:
    probe.seed(
        base="http://127.0.0.1:12345",
        bootstrap={
            "organization_id": ORGANIZATION,
            "location_id": LOCATION,
            "user_id": "bootstrap-user",
        },
        token="private-bootstrap-token",
        password="private-password",
    )


def backup(probe: BrandingVolumeProbe, docker: DockerFixture) -> None:
    seed(probe)
    docker.started = "source-start-2"
    probe.verify_restart()
    probe.backup()
    docker.running = False


def test_mocked_lifecycle_requires_api_bytes_restarts_fresh_targets_and_closed_evidence(
    fixture,
) -> None:
    probe, docker = fixture
    backup(probe, docker)
    probe.restore_and_probe()
    evidence = probe.verify_source_return("private-bootstrap-token")
    assert evidence["status"] == "passed"
    assert evidence["canonical_sha256"] == hashlib.sha256(synthetic_png()).hexdigest()
    assert evidence["source_volume"] != evidence["restored_volume"]
    assert evidence["asset_root_mode"] == "0700" and evidence["runtime_uid"] == 10001
    assert not probe.container_requested
    assert not docker.removed
    probe.cleanup()
    assert docker.removed
    commands = [parts for parts, _ in docker.calls]
    assert sum("create-first-owner" in parts for parts in commands) == 1
    assert not any(
        "adopt-branding" in parts or "recover" in parts or "activate" in parts for parts in commands
    )
    assert (
        sum("CREATE DATABASE ocwp_branding_restore_test OWNER ocwp" in parts for parts in commands)
        == 1
    )
    assert sum("branding-proof-restore" in parts for parts in commands) == 1
    assert any(parts[:2] == ["docker", "restart"] for parts in commands)
    for private in (
        "private-password",
        "private-source-token",
        "private-restored-token",
        "private-bootstrap-token",
        "png_base64",
    ):
        assert private not in json.dumps(commands)
        assert private not in json.dumps(evidence)
    assert any(stdin and "private-restored-token" in stdin for _, stdin in docker.calls)


def test_generated_override_has_only_new_least_access_services(fixture) -> None:
    probe, _ = fixture
    config = probe.override_config()
    assert set(config["services"]) == {"branding-proof-restore", "branding-proof-api"}
    for service in config["services"].values():
        assert service["profiles"] == ["branding-volume-proof"]
        assert service["user"] == "10001:10001"
        assert service["read_only"] is True
        assert not service.get("ports") and not service.get("depends_on")
        assert "database_url" not in service["secrets"]
        assert "branding_assets" not in json.dumps(service)
        assert all(
            m["source"] == "branding_probe_assets"
            for m in service["volumes"]
            if m["type"] == "volume"
        )
    assert config["services"]["branding-proof-restore"]["secrets"] == ["branding_restore_url"]
    assert config["services"]["branding-proof-api"]["secrets"] == [
        "branding_restore_url",
        "auth_secret",
    ]
    assert config["volumes"] == {
        "branding_probe_assets": {"external": True, "name": PROJECT + "_branding_probe_assets"}
    }


def test_source_restart_and_original_authority_are_required(fixture) -> None:
    probe, docker = fixture
    seed(probe)
    with pytest.raises(RuntimeError, match="not restarted"):
        probe.verify_restart()
    docker.started = "source-start-2"
    probe.verify_restart()
    probe.backup()
    docker.running = False
    probe.restore_and_probe()
    docker.changed_authority = True
    with pytest.raises(RuntimeError, match="bootstrap authority"):
        probe.verify_source_return("private-bootstrap-token")
    probe.cleanup()


@pytest.mark.parametrize("failure", ["bad_mount", "bad_root", "stale_accepted", "profile"])
def test_restored_mount_identity_old_token_and_exact_profile_are_mandatory(
    fixture, failure: str
) -> None:
    probe, docker = fixture
    backup(probe, docker)
    if failure == "profile":
        docker.restored_profile["display_name"] = "Wrong profile"
    else:
        setattr(docker, failure, True)
    with pytest.raises(RuntimeError):
        probe.restore_and_probe()
    assert "restore" not in probe.proven
    assert not probe.container_requested  # Removed through label-checked finally.
    with pytest.raises(RuntimeError, match="incomplete"):
        probe.verify_source_return("private-bootstrap-token")
    probe.cleanup()


def test_running_writer_refuses_restore_before_target_creation(fixture) -> None:
    probe, docker = fixture
    backup(probe, docker)
    docker.running = True
    with pytest.raises(RuntimeError, match="still running"):
        probe.restore_and_probe()
    assert not any(
        "CREATE DATABASE ocwp_branding_restore_test OWNER ocwp" in parts
        for parts, _ in docker.calls
    )
    assert not docker.created


def test_existing_volume_is_not_reused_or_deleted(fixture) -> None:
    probe, docker = fixture
    backup(probe, docker)
    docker.created = True
    with pytest.raises(RuntimeError, match="already exists"):
        probe.restore_and_probe()
    probe.cleanup()
    assert not docker.removed


@pytest.mark.parametrize("foreign", ["volume", "container"])
def test_cleanup_never_deletes_foreign_resources(fixture, foreign: str) -> None:
    probe, docker = fixture
    if foreign == "volume":
        probe.volume_requested = True
        docker.created = True
        docker.foreign_volume = True
    else:
        probe.container_requested = True
        docker.foreign_container = True
    with pytest.raises(RuntimeError, match=r"ownership|label"):
        probe.cleanup()
    assert not any(
        parts[:2] == ["docker", "rm"] or parts[:3] == ["docker", "volume", "rm"]
        for parts, _ in docker.calls
    )


def test_source_volume_runtime_must_really_be_nonroot(fixture) -> None:
    probe, docker = fixture
    docker.bad_root = True
    with pytest.raises(RuntimeError, match="non-root"):
        seed(probe)
    assert "save" not in probe.proven


def test_container_http_program_compiles_and_rejects_malformed_input_without_leaking() -> None:
    import sys

    from scripts.ci.branding_volume_probe import HTTP_PROBE

    compile(HTTP_PROBE, "<probe>", "exec")
    # This malformed-input path exits before networking; no Docker is involved.
    result = subprocess.run(
        [sys.executable, "-c", HTTP_PROBE],
        input="private-invalid-input",
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert not result.stdout
    assert result.stderr == "branding HTTP probe failed\n"


def test_local_smoke_hooks_keep_browser_handshake_and_original_checks() -> None:
    source = (ROOT / "scripts/ci/local_compose_smoke.py").read_text()
    ordered = [
        "branding_probe.prepare_restore_secret",
        "branding_probe.seed(",
        'browser.expect("ready_for_backup")',
        "branding_probe.verify_restart()",
        "branding_probe.backup()",
        'browser.expect("pending_preserved")',
        'compose("stop", "edge", "api", "worker")',
        "branding_probe.restore_and_probe()",
        '"phase": "restored_api_ready"',
        'browser.expect("recovery_verified")',
        'compose("down")',
        "branding_probe.verify_source_return(token)",
        'evidence["status"] = "passed"',
        "branding_probe.cleanup()",
    ]
    assert [source.index(part) for part in ordered] == sorted(
        source.index(part) for part in ordered
    )
    assert '"/state/secrets/branding_restore_url.txt "' in source
    assert (
        'evidence["branding_named_volume"] = branding_probe.verify_source_return(token)' in source
    )
