"""Strict disposable Compose branding proof. Importing this module runs nothing.

Standard library only: the host need not install application dependencies. Docker
execution is exclusively via the generated smoke project's redacting runner.
Captured HTTP bodies stay in memory; durable evidence contains only closed facts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import time
import zlib
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = "/var/lib/ocwp/branding-assets"
TARGET_DATABASE = "ocwp_branding_restore_test"
GENERATION = "/backups/branding-volume-generation"
LABEL = "org.ocwp.disposable-branding-project"
LIMIT = 393216
JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
ROOT_PROBE = (
    "import json,os,stat; p='/var/lib/ocwp/branding-assets'; s=os.lstat(p); "
    "print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'owner':s.st_uid,"
    "'group':s.st_gid,'mode':stat.S_IMODE(s.st_mode),'directory':stat.S_ISDIR(s.st_mode)}))"
)
# Fixed loopback destination, bounded stdin and output. Never include request or
# error response bodies in exceptions, argv, logs, or durable evidence.
HTTP_PROBE = """
import json,sys,urllib.request,urllib.error
try:
    raw=sys.stdin.buffer.read(393217)
    if len(raw)>393216: raise ValueError()
    p=json.loads(raw)
    if not p['path'].startswith(('/api/v1/','/health/')): raise ValueError()
    headers={'Accept':'application/json','X-OCWP-Write-Protocol':'1'}
    if p.get('token'): headers['Authorization']='Bearer '+p['token']
    data=None
    if p.get('payload') is not None:
        data=json.dumps(p['payload']).encode()
        headers['Content-Type']='application/json'
    req=urllib.request.Request('http://127.0.0.1:8000'+p['path'],data=data,headers=headers,method=p['method'])
    try: response=urllib.request.urlopen(req,timeout=5)
    except urllib.error.HTTPError as error: response=error
    with response:
        body=response.read(393217)
        if len(body)>393216: raise ValueError()
        print(json.dumps({'code':response.status,'body':json.loads(body)}))
except Exception:
    print('branding HTTP probe failed',file=sys.stderr)
    sys.exit(1)
"""


class Runner(Protocol):
    def __call__(
        self, parts: list[str], *, check: bool = True, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]: ...


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError("Branding volume proof: " + message)


def synthetic_png() -> bytes:
    """Tiny deterministic valid fixture; the API still performs canonicalization."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + b"\x10\x90\x60\xff" * 2) * 2))
        + chunk(b"IEND", b"")
    )


def _bytes(profile: dict[str, Any]) -> bytes:
    try:
        logo = profile["logo"]
        require(
            profile["logo_state"] == "available" and profile["logo_diagnostic"] is None,
            "logo is not available",
        )
        require(
            isinstance(logo, dict)
            and set(logo) == {"sha256", "byte_count", "width", "height", "mime_type", "png_base64"},
            "unexpected logo metadata",
        )
        encoded = logo["png_base64"]
        require(isinstance(encoded, str) and 0 < len(encoded) <= 349528, "logo exceeds bounds")
        data = base64.b64decode(encoded, validate=True)
        require(
            base64.b64encode(data).decode("ascii") == encoded
            and data.startswith(b"\x89PNG\r\n\x1a\n")
            and len(data) == logo["byte_count"] <= 262144
            and hashlib.sha256(data).hexdigest() == logo["sha256"]
            and logo["mime_type"] == "image/png"
            and logo["width"] == logo["height"] == 2,
            "canonical logo bytes or metadata differ",
        )
        return data
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Branding volume proof: invalid logo response") from None


def assert_profile_equal(
    expected: dict[str, Any], actual: dict[str, Any], *, restored: bool = False
) -> str:
    require(
        set(expected)
        == set(actual)
        == {
            "schema_version",
            "organization_id",
            "location_id",
            "dataset_incarnation",
            "version",
            "display_name",
            "palette_id",
            "logo_state",
            "logo_diagnostic",
            "logo",
            "updated_at",
            "updated_by",
        },
        "unexpected profile fields",
    )
    try:
        for profile in (expected, actual):
            require(
                str(UUID(profile["dataset_incarnation"])) == profile["dataset_incarnation"],
                "invalid incarnation",
            )
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Branding volume proof: invalid incarnation") from None
    require(
        (expected["dataset_incarnation"] != actual["dataset_incarnation"]) == restored,
        "incarnation transition differs",
    )
    require(
        {k: v for k, v in expected.items() if k != "dataset_incarnation"}
        == {k: v for k, v in actual.items() if k != "dataset_incarnation"},
        "profile metadata differ",
    )
    require(_bytes(expected) == _bytes(actual), "decoded canonical bytes differ")
    return hashlib.sha256(_bytes(actual)).hexdigest()


def host_request(
    base: str,
    path: str,
    *,
    method: str = "GET",
    token: str = "",
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    parsed = urlsplit(base)
    require(
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port is not None
        and not parsed.username
        and not parsed.path
        and not parsed.query
        and not parsed.fragment,
        "HTTP target is not generated loopback",
    )
    headers = {"Accept": "application/json", "X-OCWP-Write-Protocol": "1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
        require(len(data) <= LIMIT, "request exceeds bounds")
    try:
        try:
            response = urlopen(
                Request(base + path, data=data, headers=headers, method=method), timeout=5
            )
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(LIMIT + 1)
            require(len(raw) <= LIMIT, "response exceeds bounds")
            return response.status, json.loads(raw)
    except Exception:
        raise RuntimeError("Branding volume proof: HTTP request failed") from None


class BrandingVolumeProbe:
    def __init__(
        self, *, project: str, command: list[str], directory: Path, run: Runner, secrets: list[str]
    ) -> None:
        if (
            not re.fullmatch(r"ocwp-smoke-[0-9a-f]{12}", project)
            or command
            != [
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(ROOT / "infra/compose/docker-compose.local.yml"),
            ]
            or not directory.name.startswith(project + "-")
            or directory.is_symlink()
        ):
            raise ValueError("Branding probe requires its generated disposable project")
        self.project, self.command, self.directory = project, command, directory
        self.run, self.secrets = run, secrets
        self.volume = project + "_branding_probe_assets"
        self.container = project + "-branding-proof-api"
        self.volume_requested = False
        self.container_requested = False
        self.proven: set[str] = set()
        self.expected: dict[str, Any] = {}
        self.override = directory / "branding-proof.json"
        self.target_secret = directory / "secrets/branding_restore_url.txt"

    def compose(self, *parts: str) -> subprocess.CompletedProcess[str]:
        return self.run([*self.command, *parts])

    def prepare_restore_secret(self, source_url: str) -> Path:
        parsed = urlsplit(source_url)
        require(
            parsed.scheme == "postgresql+psycopg"
            and parsed.hostname == "postgres"
            and parsed.port == 5432
            and parsed.username == "ocwp"
            and parsed.path == "/ocwp"
            and not parsed.query
            and not parsed.fragment,
            "unexpected generated database URL",
        )
        target = urlunsplit(parsed._replace(path="/" + TARGET_DATABASE))
        fd = os.open(self.target_secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(target + "\n")
        self.secrets.append(target)
        return self.target_secret

    def override_config(self) -> dict[str, Any]:
        common: dict[str, Any] = {
            "profiles": ["branding-volume-proof"],
            "user": "10001:10001",
            "read_only": True,
            "tmpfs": ["/tmp:rw,noexec,nosuid,size=64m"],
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "init": True,
            "labels": {LABEL: self.project},
        }
        return {
            "services": {
                "branding-proof-restore": common
                | {
                    "image": "ocwp-operations:" + self.project,
                    "networks": ["data_net"],
                    "entrypoint": ["python", "-m", "scripts.database.branding_bundle"],
                    "environment": {
                        "OCWP_RESTORE_DATABASE_URL_FILE": "/run/secrets/branding_restore_url"
                    },
                    "secrets": ["branding_restore_url"],
                    "volumes": [
                        {
                            "type": "volume",
                            "source": "branding_probe_assets",
                            "target": "/restore-branding-assets",
                        },
                        {
                            "type": "bind",
                            "source": str(self.directory / "backups"),
                            "target": "/backups",
                            "read_only": True,
                            "bind": {"create_host_path": False},
                        },
                    ],
                },
                "branding-proof-api": common
                | {
                    "image": "ocwp-platform:" + self.project,
                    "networks": ["app_net", "data_net"],
                    "environment": {
                        "OCWP_ENVIRONMENT": "production",
                        "OCWP_CUTOVER_ENABLED": "true",
                        "OCWP_DATABASE_URL_FILE": "/run/secrets/branding_restore_url",
                        "OCWP_AUTH_SECRET_FILE": "/run/secrets/auth_secret",
                        "OCWP_BRANDING_ASSET_ROOT": ASSET_ROOT,
                    },
                    "secrets": ["branding_restore_url", "auth_secret"],
                    "volumes": [
                        {"type": "volume", "source": "branding_probe_assets", "target": ASSET_ROOT}
                    ],
                    "command": [
                        "uvicorn",
                        "cycling_workshop.runtime:app",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                        "--no-proxy-headers",
                    ],
                },
            },
            "volumes": {"branding_probe_assets": {"external": True, "name": self.volume}},
            "secrets": {"branding_restore_url": {"file": str(self.target_secret)}},
        }

    def _inspect(self, name: str, *, volume: bool = False) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            json.loads(
                self.run(["docker", *(["volume"] if volume else []), "inspect", name]).stdout
            )[0],
        )

    def _owned_container(self, name: str, service: str) -> dict[str, Any]:
        info = self._inspect(name)
        labels = info["Config"].get("Labels", {})
        require(
            labels.get("com.docker.compose.project") == self.project
            and labels.get("com.docker.compose.service") == service,
            "container project ownership differs",
        )
        if service == "branding-proof-api":
            require(labels.get(LABEL) == self.project, "probe container label differs")
        return info

    def _owned_volume(self) -> None:
        info = self._inspect(self.volume, volume=True)
        require(
            info["Name"] == self.volume and info.get("Labels", {}).get(LABEL) == self.project,
            "restore volume ownership differs",
        )

    def _source(self) -> dict[str, Any]:
        name = self.compose("ps", "-a", "-q", "api").stdout.strip()
        require(bool(name) and "\n" not in name, "expected one source API")
        return self._owned_container(name, "api")

    def _mount(self, info: dict[str, Any], *, restored: bool) -> str:
        mounts = [m for m in info["Mounts"] if m["Destination"] == ASSET_ROOT]
        require(
            len(mounts) == 1 and mounts[0]["Type"] == "volume" and mounts[0]["RW"] is True,
            "API does not use a writable named asset volume",
        )
        volume = mounts[0]["Name"]
        if restored:
            require(
                volume == self.volume and volume != self.source_volume,
                "restored API is not isolated from source assets",
            )
            require(
                {m["Destination"] for m in info["Mounts"] if m["Type"] != "tmpfs"}
                == {ASSET_ROOT, "/run/secrets/branding_restore_url", "/run/secrets/auth_secret"},
                "restored API has unexpected mounts",
            )
            secret_mount = next(
                m for m in info["Mounts"] if m["Destination"] == "/run/secrets/branding_restore_url"
            )
            require(
                secret_mount["Source"] == str(self.target_secret) and not secret_mount["RW"],
                "restored API database secret differs",
            )
            env = info["Config"]["Env"]
            require(
                "OCWP_DATABASE_URL_FILE=/run/secrets/branding_restore_url" in env
                and not any(v.startswith("OCWP_DATABASE_URL=") for v in env),
                "restored API database target differs",
            )
        else:
            metadata = self._inspect(volume, volume=True)
            require(
                metadata.get("Labels", {}).get("com.docker.compose.project") == self.project
                and metadata.get("Labels", {}).get("com.docker.compose.volume")
                == "branding_assets",
                "source volume project ownership differs",
            )
        require(info["Config"]["User"] in {"ocwp", "10001", "10001:10001"}, "unexpected API user")
        root = json.loads(
            self.run(["docker", "exec", info["Id"], "python", "-c", ROOT_PROBE]).stdout
        )
        require(
            root
            == {
                "uid": 10001,
                "gid": 10001,
                "owner": 10001,
                "group": 10001,
                "mode": 0o700,
                "directory": True,
            },
            "asset root is not private and non-root",
        )
        return str(volume)

    def _host(self, path: str, **kwargs: Any) -> tuple[int, dict[str, Any]]:
        return host_request(self.base, path, **kwargs)

    def _login(self, *, restored: bool = False) -> str:
        request = self._inside if restored else self._host
        code, body = request("/api/v1/auth/login", method="POST", payload=self.login)
        require(code == 200 and isinstance(body.get("access_token"), str), "owner login failed")
        token = str(body["access_token"])
        self.secrets.append(token)
        return token

    def _read(self, token: str, *, restored: bool = False) -> dict[str, Any]:
        request = self._inside if restored else self._host
        code, body = request(self.path, token=token)
        require(code == 200, "authenticated profile read failed")
        return body

    def seed(self, *, base: str, bootstrap: dict[str, Any], token: str, password: str) -> None:
        self.base = base
        self.path = f"/api/v1/locations/{bootstrap['location_id']}/branding"
        code, self.bootstrap_authority = self._host("/api/v1/auth/me", token=token)
        require(
            code == 200
            and self.bootstrap_authority["capabilities"] == ["*"]
            and self.bootstrap_authority["location_id"] == bootstrap["location_id"],
            "bootstrap authority baseline differs",
        )
        self.compose(
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--volume",
            f"{self.directory / 'secrets/admin_password.txt'}:/run/secrets/branding_password:ro",
            "api",
            "ocwpctl",
            "access",
            "create-first-owner",
            "--organization-id",
            bootstrap["organization_id"],
            "--username",
            "branding-proof-owner",
            "--display-name",
            "Disposable branding proof owner",
            "--password-file",
            "/run/secrets/branding_password",
        )
        self.login = {
            "organization_id": bootstrap["organization_id"],
            "username": "branding-proof-owner",
            "password": password,
        }
        self.owner_token = self._login()
        code, owner = self._host("/api/v1/auth/me", token=self.owner_token)
        require(
            code == 200
            and owner["user_id"] != bootstrap["user_id"]
            and owner["location_id"] is None
            and "*" not in owner["capabilities"]
            and {"branding.read", "branding.write"} <= set(owner["capabilities"]),
            "separate explicit branding authority missing",
        )
        require(
            self._host("/api/v1/auth/me", token=token) == (200, self.bootstrap_authority),
            "bootstrap authority changed",
        )
        require(
            self._host(self.path, token=token)[0] == 403, "bootstrap unexpectedly gained branding"
        )
        code, self.expected = self._host(
            self.path,
            method="PUT",
            token=self.owner_token,
            payload={
                "expected_version": 0,
                "display_name": "Synthetic volume proof",
                "palette_id": "jade",
                "logo_png_base64": base64.b64encode(synthetic_png()).decode("ascii"),
            },
        )
        require(
            code == 200
            and self.expected["version"] == 1
            and self.expected["schema_version"] == 1
            and self.expected["display_name"] == "Synthetic volume proof"
            and self.expected["palette_id"] == "jade"
            and self.expected["organization_id"] == bootstrap["organization_id"]
            and self.expected["location_id"] == bootstrap["location_id"],
            "API save did not commit expected profile",
        )
        self.digest = assert_profile_equal(self.expected, self._read(self.owner_token))
        source = self._source()
        self.source_volume = self._mount(source, restored=False)
        self.source_started = source["State"]["StartedAt"]
        self.proven.add("save")

    def verify_restart(self) -> None:
        require("save" in self.proven, "source save missing")
        source = self._source()
        require(source["State"]["StartedAt"] != self.source_started, "source API was not restarted")
        require(self._mount(source, restored=False) == self.source_volume, "source volume changed")
        assert_profile_equal(self.expected, self._read(self.owner_token))
        self.proven.add("restart")

    def backup(self) -> None:
        require("restart" in self.proven, "source restart proof missing")
        for args in (("backup", GENERATION, "--asset-root", ASSET_ROOT), ("verify", GENERATION)):
            self.compose(
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "--entrypoint",
                "python",
                "operations",
                "-m",
                "scripts.database.branding_bundle",
                *args,
            )
        self.proven.add("backup")

    def _inside(
        self,
        path: str,
        *,
        method: str = "GET",
        token: str = "",
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        raw = json.dumps({"path": path, "method": method, "token": token, "payload": payload})
        require(len(raw.encode()) <= LIMIT, "container HTTP input exceeds bounds")
        result = self.run(
            ["docker", "exec", "-i", self.container, "python", "-c", HTTP_PROBE],
            stdin=raw,
            check=False,
        )
        require(
            result.returncode == 0 and len(result.stdout.encode()) <= LIMIT + 1024,
            "container HTTP probe failed",
        )
        try:
            response = json.loads(result.stdout)
            return response["code"], response["body"]
        except (ValueError, KeyError, TypeError):
            raise RuntimeError("Branding volume proof: invalid container HTTP response") from None

    def _ready(self) -> None:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if self._inside("/health/ready")[0] == 200:
                    return
            except RuntimeError:
                pass
            time.sleep(2)
        raise RuntimeError("Branding volume proof: restored API readiness timed out")

    def restore_and_probe(self) -> None:
        require("backup" in self.proven, "asset-inclusive backup missing")
        for service in ("api", "edge", "worker"):
            name = self.compose("ps", "-a", "-q", service).stdout.strip()
            require(
                self._owned_container(name, service)["State"]["Running"] is False,
                "fixture writers or edge are still running",
            )
        # No IF EXISTS: a previous target is never silently reused or dropped.
        self.compose(
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
            f"CREATE DATABASE {TARGET_DATABASE} OWNER ocwp",
        )
        existing = self.run(["docker", "volume", "inspect", self.volume], check=False)
        require(existing.returncode != 0, "restore volume already exists")
        self.volume_requested = True
        self.run(["docker", "volume", "create", "--label", f"{LABEL}={self.project}", self.volume])
        self._owned_volume()
        self.override.write_text(json.dumps(self.override_config()))
        command = [*self.command, "-f", str(self.override)]
        result = json.loads(
            self.run(
                [
                    *command,
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "branding-proof-restore",
                    "restore",
                    GENERATION,
                    "--asset-root",
                    "/restore-branding-assets",
                    "--confirm-empty-target",
                ]
            ).stdout
        )
        require(
            all(
                result.get(k) == v
                for k, v in {
                    "status": "branding_restore_checked",
                    "profiles_checked": 1,
                    "asset_references_checked": 1,
                    "incarnations_rotated": 1,
                    "legacy_organizations_activated": 0,
                }.items()
            ),
            "bundle restore did not verify and rotate expected snapshot",
        )
        self.container_requested = True
        self.run(
            [*command, "run", "-d", "--no-deps", "--name", self.container, "branding-proof-api"]
        )
        try:
            info = self._owned_container(self.container, "branding-proof-api")
            self._mount(info, restored=True)
            self._ready()
            require(
                self._inside(self.path, token=self.owner_token)[0] == 401,
                "source token accepted after recovery",
            )
            token = self._login(restored=True)
            restored = self._read(token, restored=True)
            assert_profile_equal(self.expected, restored, restored=True)
            started = info["State"]["StartedAt"]
            self.run(["docker", "restart", self.container])
            self._ready()
            info = self._owned_container(self.container, "branding-proof-api")
            require(info["State"]["StartedAt"] != started, "restored API was not restarted")
            self._mount(info, restored=True)
            assert_profile_equal(restored, self._read(self._login(restored=True), restored=True))
            log_result = self.run(["docker", "logs", self.container])
            logs = log_result.stdout + log_result.stderr
            require(
                not JWT.search(logs) and not any(s and s in logs for s in self.secrets),
                "probe logs contain credentials",
            )
            self.proven.add("restore")
        finally:
            self._remove_container()

    def verify_source_return(self, token: str) -> dict[str, Any]:
        require(
            self.proven == {"save", "restart", "backup", "restore"}, "incomplete named-volume proof"
        )
        require(
            self._mount(self._source(), restored=False) == self.source_volume,
            "original source volume was not reopened",
        )
        assert_profile_equal(self.expected, self._read(self._login()))
        require(
            self._host("/api/v1/auth/me", token=token) == (200, self.bootstrap_authority),
            "original bootstrap authority differs",
        )
        require(self._host(self.path, token=token)[0] == 403, "original bootstrap gained branding")
        return {
            "status": "passed",
            "canonical_sha256": self.digest,
            "canonical_byte_count": len(_bytes(self.expected)),
            "profile_version": 1,
            "source_volume": self.source_volume,
            "restored_volume": self.volume,
            "runtime_uid": 10001,
            "runtime_gid": 10001,
            "asset_root_mode": "0700",
            "source_restart_bytes_equal": True,
            "restored_restart_bytes_equal": True,
            "authenticated_restored_bytes_equal": True,
            "profile_metadata_equal": True,
            "incarnation_rotated_once": True,
            "old_token_refused": True,
            "bootstrap_authority_unchanged": True,
            "original_source_return_verified": True,
        }

    def _remove_container(self) -> None:
        if self.container_requested:
            info = self._owned_container(self.container, "branding-proof-api")
            self.run(["docker", "rm", "-f", info["Id"]])
            self.container_requested = False

    def cleanup(self) -> None:
        """Delete only this probe's label-checked resources, never source assets."""
        self._remove_container()
        if self.volume_requested:
            self._owned_volume()
            self.run(["docker", "volume", "rm", self.volume])
            self.volume_requested = False
