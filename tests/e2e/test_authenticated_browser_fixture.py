from __future__ import annotations

from pathlib import Path

from cycling_workshop.app import create_app
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.tenancy.models import OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from scripts.e2e.prepare_e2e_database import (
    E2E_ORGANIZATION_ID,
    E2E_PASSWORD,
    run_migrations,
    seed_browser_identity,
)


def test_browser_fixture_has_genuine_enabled_multiuser_workshop_contexts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'browser.sqlite3'}"
    monkeypatch.setenv("OCWP_DATABASE_URL", url)
    monkeypatch.delenv("OCWP_DATABASE_URL_FILE", raising=False)
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
    run_migrations(url)
    seed_browser_identity(url)
    engine = create_engine(url)
    with Session(engine) as session:
        org = session.get(OrganizationRecord, E2E_ORGANIZATION_ID)
        assert org is not None and org.minimum_write_protocol == 0
        assert len(list(session.scalars(select(UserRecord)))) == 1
    engine.dispose()
