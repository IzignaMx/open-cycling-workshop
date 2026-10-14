"""Real synthetic PostgreSQL/filesystem/API drill. Explicitly skipped without PG18.

This test owns only UUID-named disposable databases through the established fixture.
It never changes the configured test database or an operator installation.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.app import create_app
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from test_backup_postgres_integration import disposable_databases as disposable_databases
from test_branding_bundle import synthetic_png

from scripts.database import backup_postgres as postgres
from scripts.database import branding_bundle as branding

ROOT = Path(__file__).resolve().parents[2]
SECRET = "synthetic-branding-restore-test-signing-key-no-real-account"
PASSWORD = "synthetic recovery password for test only"


def login(client: TestClient, organization: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"organization_id": organization, "username": "fixture", "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-OCWP-Write-Protocol": "1",
    }


def put(
    client: TestClient, headers: dict[str, str], location: str, data: bytes, *, version: int = 0
) -> dict[str, Any]:
    response = client.put(
        f"/api/v1/locations/{location}/branding",
        headers=headers,
        json={
            "expected_version": version,
            "display_name": f"Synthetic brand {location} {version}",
            "palette_id": "jade",
            "logo_png_base64": base64.b64encode(data).decode("ascii"),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_real_snapshot_assets_corrupt_latest_earlier_restore_and_authenticated_bytes(
    disposable_databases: tuple[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_url, target_url = disposable_databases
    config = Config(str(ROOT / "services/platform/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "services/platform/migrations"))
    config.set_main_option("prepend_sys_path", str(ROOT / "services/platform/src"))
    config.set_main_option("sqlalchemy.url", source_url.replace("%", "%%"))
    monkeypatch.setenv("OCWP_DATABASE_URL", source_url)
    command.upgrade(config, "head")
    source, target = create_engine(source_url), create_engine(target_url)
    source_assets, restored_assets = tmp_path / "source-assets", tmp_path / "restored-assets"
    source_factory = sessionmaker(source, expire_on_commit=False)
    source_settings = Settings(
        environment="test",
        database_url=source_url,
        auth_secret=SECRET,
        cutover_enabled=True,
        branding_asset_root=str(source_assets),
    )
    password_hash = PasswordService().hash(PASSWORD)
    try:
        with source_factory.begin() as session:
            for org in ("recovery-a", "recovery-b"):
                session.add(OrganizationRecord(id=org, name=org, minimum_write_protocol=1))
            session.flush()
            for org, locations in (("recovery-a", ("a1", "a2")), ("recovery-b", ("b1",))):
                for location in locations:
                    session.add(LocationRecord(id=location, organization_id=org, name=location))
                session.add(
                    UserRecord(
                        id=f"{org}-user",
                        organization_id=org,
                        location_id=None,
                        username="fixture",
                        display_name="Synthetic recovery actor",
                        password_hash=password_hash,
                        is_active=True,
                        capabilities=[
                            "branding.read",
                            "branding.write",
                            "customers.read",
                            "sync.pull",
                        ],
                    )
                )
        with TestClient(create_app(source_settings, session_factory=source_factory)) as client:
            old_headers = {org: login(client, org) for org in ("recovery-a", "recovery-b")}
            expected = {
                "a1": put(client, old_headers["recovery-a"], "a1", synthetic_png()),
                "a2": put(client, old_headers["recovery-a"], "a2", synthetic_png(b"\xff\0\0\xff")),
                "b1": put(client, old_headers["recovery-b"], "b1", synthetic_png(b"\0\xff\0\xff")),
            }
            context = client.get(
                "/api/v1/auth/context?selected_location_id=a1", headers=old_headers["recovery-a"]
            )
            assert context.status_code == 200
            baseline = client.post(
                "/api/v1/sync/baselines/start",
                headers=old_headers["recovery-a"],
                json={
                    "protocol": 1,
                    "selected_location_id": "a1",
                    "authorization_epoch": context.json()["authorization_epoch"],
                    "request_id": new_id(),
                },
            )
            assert baseline.status_code == 200, baseline.text
            continuation = baseline.json()["continuation"]
            advanced = False

            def concurrent_writer(command: list[str], *, env: dict[str, str]) -> None:
                nonlocal advanced
                if command[0] == "pg_dump":
                    # The observer has already captured v1 in the SAME exported snapshot.
                    # Commit a real new authenticated v2 while that snapshot remains open.
                    changed = put(
                        client,
                        old_headers["recovery-a"],
                        "a1",
                        synthetic_png(b"\0\0\xff\xff"),
                        version=1,
                    )
                    assert changed["version"] == 2
                    assert changed["logo"]["sha256"] != expected["a1"]["logo"]["sha256"]
                    advanced = True
                postgres._run(command, env=env)

            earlier = branding.create_branding_bundle(
                source_url, tmp_path / "earlier", asset_root=source_assets, runner=concurrent_writer
            )
            assert advanced
            earlier_manifest = branding.verify_branding_bundle(earlier)["manifest"]
            assert {p["location_id"]: p["logo_sha256"] for p in earlier_manifest["profiles"]} == {
                location: profile["logo"]["sha256"] for location, profile in expected.items()
            }
            latest = branding.create_branding_bundle(
                source_url, tmp_path / "latest", asset_root=source_assets
            )
            latest_manifest = branding.verify_branding_bundle(latest)["manifest"]
            damaged = next(row for row in latest_manifest["profiles"] if row["location_id"] == "a1")
            namespace = hashlib.sha256(damaged["organization_id"].encode()).hexdigest()
            damaged_path = latest / "assets" / namespace / damaged["logo_key"]
            damaged_path.write_bytes(b"synthetic corrupt latest image")
            with pytest.raises(postgres.BackupError, match="integrity"):
                branding.restore_branding_bundle(
                    latest, target_url, asset_root=restored_assets, confirm_empty_target=True
                )
            assert not restored_assets.exists()
            with target.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT to_regclass('public.organizations')")
                    ).scalar_one()
                    is None
                )
            # Close the probe pool before the fresh-target no-other-clients preflight.
            target.dispose()
            result = branding.restore_branding_bundle(
                earlier, target_url, asset_root=restored_assets, confirm_empty_target=True
            )
            assert result["status"] == "branding_restore_checked"
            assert result["profiles_checked"] == result["asset_references_checked"] == 3
            assert result["incarnations_rotated"] == 2
            assert result["application_smoke_tested"] is False
            assert result["elapsed_seconds"] > 0
            target_settings = Settings(
                environment="test",
                database_url=target_url,
                auth_secret=SECRET,
                cutover_enabled=True,
                branding_asset_root=str(restored_assets),
            )
            with TestClient(
                create_app(
                    target_settings, session_factory=sessionmaker(target, expire_on_commit=False)
                )
            ) as restored_client:
                for headers in old_headers.values():
                    refused = restored_client.get("/api/v1/auth/me", headers=headers)
                    assert refused.status_code == 401, refused.text
                fresh = {org: login(restored_client, org) for org in old_headers}
                proofs = []
                for location, original in expected.items():
                    org = "recovery-b" if location == "b1" else "recovery-a"
                    response = restored_client.get(
                        f"/api/v1/locations/{location}/branding", headers=fresh[org]
                    )
                    assert response.status_code == 200, response.text
                    actual = response.json()
                    assert actual["logo_state"] == "available"
                    assert actual["dataset_incarnation"] != original["dataset_incarnation"]
                    assert {k: v for k, v in actual.items() if k != "dataset_incarnation"} == {
                        k: v for k, v in original.items() if k != "dataset_incarnation"
                    }
                    actual_bytes = base64.b64decode(actual["logo"]["png_base64"], validate=True)
                    expected_bytes = base64.b64decode(original["logo"]["png_base64"], validate=True)
                    assert actual_bytes == expected_bytes
                    assert hashlib.sha256(actual_bytes).hexdigest() == original["logo"]["sha256"]
                    proofs.append(
                        {
                            "location_id": location,
                            "expected_sha256": original["logo"]["sha256"],
                            "actual_sha256": hashlib.sha256(actual_bytes).hexdigest(),
                        }
                    )
                assert (
                    restored_client.get(
                        "/api/v1/locations/b1/branding", headers=fresh["recovery-a"]
                    ).status_code
                    == 403
                )
                stale_checkpoint = restored_client.post(
                    "/api/v1/sync/baselines/page",
                    headers=fresh["recovery-a"],
                    json={"protocol": 1, "continuation": continuation},
                )
                assert stale_checkpoint.status_code == 409, stale_checkpoint.text
                assert stale_checkpoint.json()["error"]["code"] == "context_changed"
                # Artifact contains only synthetic IDs/hashes/timing, never tokens/passwords/PNGs.
                (tmp_path / "branding-recovery-evidence.json").write_text(
                    json.dumps(
                        {
                            **result,
                            "authenticated_profile_smoke_tested": True,
                            "stale_sessions_and_checkpoint_refused": True,
                            "profiles": proofs,
                        },
                        sort_keys=True,
                        indent=2,
                    )
                )
    finally:
        source.dispose()
        target.dispose()
