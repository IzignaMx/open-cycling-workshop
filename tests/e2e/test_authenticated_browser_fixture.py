from __future__ import annotations

from pathlib import Path

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from scripts.e2e import legacy_upgrade_fixture as legacy_fixture
from scripts.e2e import prepare_e2e_database as preparation
from scripts.e2e.prepare_e2e_database import (
    E2E_ORGANIZATION_ID,
    E2E_PASSWORD,
    run_migrations,
    seed_browser_identity,
)


def test_pinned_legacy_source_loads_exact_bytes_without_repository_history(
    tmp_path: Path, monkeypatch
) -> None:
    source = legacy_fixture.PIN_SOURCE_FIXTURE.read_bytes()
    fixture = tmp_path / "security.py.source"
    fixture.write_bytes(source)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(legacy_fixture, "PIN_SOURCE_FIXTURE", fixture)
    assert not (tmp_path / ".git").exists()
    assert len(source) == 4549
    assert legacy_fixture.legacy_security_source().encode("utf-8") == source


@pytest.mark.parametrize("damage", ["missing", "truncated", "tampered", "oversized"])
def test_pinned_legacy_source_refuses_missing_or_changed_bytes(
    tmp_path: Path, monkeypatch, damage: str
) -> None:
    source = legacy_fixture.PIN_SOURCE_FIXTURE.read_bytes()
    fixture = tmp_path / "security.py.source"
    if damage == "truncated":
        fixture.write_bytes(source[:-1])
    elif damage == "tampered":
        fixture.write_bytes(bytes([source[0] ^ 1]) + source[1:])
    elif damage == "oversized":
        fixture.write_bytes(source + b"\n")
    monkeypatch.setattr(legacy_fixture, "PIN_SOURCE_FIXTURE", fixture)
    reason = "unavailable" if damage == "missing" else "identity mismatch"
    with pytest.raises(RuntimeError, match=f"^Pinned legacy security source {reason}$"):
        legacy_fixture.legacy_security_source()


def test_browser_fixture_has_genuine_enabled_multiuser_workshop_contexts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'browser.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    # SQLite is an explicit isolated functional surrogate, never a CLI target.
    monkeypatch.setattr(preparation, "validate_e2e_database_url", lambda value: None)
    run_migrations(url)
    seed_browser_identity(url, authenticated=True)
    engine = create_engine(url)
    with Session(engine) as session:
        org = session.get(OrganizationRecord, E2E_ORGANIZATION_ID)
        assert org is not None and org.minimum_write_protocol == 1
        users = list(session.scalars(select(UserRecord)))
        assert {"e2e-admin", "e2e-other", "e2e-owner"} <= {user.username for user in users}
        owner = next(user for user in users if user.username == "e2e-owner")
        assert owner.location_id is None and owner.is_owner
    with TestClient(
        create_app(
            Settings(database_url=url, cutover_enabled=True), session_factory=sessionmaker(engine)
        )
    ) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "organization_id": E2E_ORGANIZATION_ID,
                "username": "e2e-owner",
                "password": E2E_PASSWORD,
            },
        )
        assert response.status_code == 200
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        locations = client.get("/api/v1/locations?limit=1", headers=headers).json()
        assert len(locations["items"]) == 1 and locations["next_cursor"] is not None
        context = client.get(
            "/api/v1/auth/context",
            params={
                "selected_location_id": locations["items"][0]["location_id"],
            },
            headers=headers,
        )
        assert context.status_code == 200
        assert context.json()["snapshot_protocol"] == "baseline-v1"
        assert context.json()["account_location_id"] is None
    engine.dispose()


def test_original_isolated_seed_remains_floor_zero_without_historical_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'legacy.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    # SQLite is an explicit isolated functional surrogate, never a CLI target.
    monkeypatch.setattr(preparation, "validate_e2e_database_url", lambda value: None)
    run_migrations(url)
    seed_browser_identity(url)
    engine = create_engine(url)
    with Session(engine) as session:
        org = session.get(OrganizationRecord, E2E_ORGANIZATION_ID)
        assert org is not None and org.minimum_write_protocol == 0
        assert len(list(session.scalars(select(UserRecord)))) == 1
    engine.dispose()


def test_real_old_bundle_fixture_is_floor_zero_until_explicit_disposable_cutover(
    tmp_path: Path, monkeypatch
) -> None:
    from cycling_workshop.identity.cutover_cli import activate_cutover

    from scripts.e2e.prepare_e2e_database import (
        E2E_LEGACY_ORGANIZATION_ID,
        seed_legacy_upgrade_identity,
    )

    url = f"sqlite+pysqlite:///{tmp_path / 'old-browser.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
    # SQLite is an explicit isolated functional surrogate, never a CLI target.
    monkeypatch.setattr(preparation, "validate_e2e_database_url", lambda value: None)
    run_migrations(url)
    seed_legacy_upgrade_identity(url)
    engine = create_engine(url)
    settings = Settings(database_url=url, cutover_enabled=True)
    with TestClient(create_app(settings, session_factory=sessionmaker(engine))) as client:
        payload = {
            "organization_id": E2E_LEGACY_ORGANIZATION_ID,
            "username": "e2e-legacy",
            "password": E2E_PASSWORD,
        }
        old = client.post("/api/v1/auth/login", json=payload)
        assert old.status_code == 200
        from scripts.e2e.legacy_upgrade_fixture import legacy_fixture_session

        old_headers = {"Authorization": f"Bearer {legacy_fixture_session(settings)}"}
        assert (
            client.get("/api/v1/auth/context", headers=old_headers).json()["snapshot_protocol"]
            is None
        )
        assert (
            activate_cutover(settings, organization_id=E2E_LEGACY_ORGANIZATION_ID)["changed"]
            is True
        )
        assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
        fresh = client.post("/api/v1/auth/login", json=payload)
        assert fresh.status_code == 200
        fresh_headers = {"Authorization": f"Bearer {fresh.json()['access_token']}"}
        blocked = client.post(
            "/api/v1/customers",
            headers=fresh_headers,
            json={
                "location_id": "00000000-0000-7000-8000-000000000102",
                "display_name": "Blocked old transport",
            },
        )
        assert (
            blocked.status_code == 409
            and blocked.json()["error"]["code"] == "client_upgrade_required"
        )

        from scripts.e2e.legacy_upgrade_fixture import recover_legacy_fixture

        incarnation = client.get("/api/v1/auth/context", headers=fresh_headers).json()[
            "dataset_incarnation"
        ]
        recovered = recover_legacy_fixture(settings, incarnation)
        assert recovered["minimum_write_protocol"] == 1
        assert recovered["dataset_incarnation"] != incarnation
        assert client.get("/api/v1/auth/me", headers=fresh_headers).status_code == 401
    engine.dispose()
