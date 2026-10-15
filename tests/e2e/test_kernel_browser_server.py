"""The kernel surrogate owns its SQLite target; PostgreSQL guards stay closed."""

from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy
import uvicorn
from cycling_workshop.db.base import Base
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.tenancy.models import OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import select

from scripts.e2e import prepare_e2e_database

ROOT = Path(__file__).resolve().parents[2]


def kernel_main():
    return runpy.run_path(str(ROOT / "apps/web/tools/kernel-browser/baseline-server.py"))["main"]


@pytest.fixture
def engines(monkeypatch):
    created = []
    original = sqlalchemy.create_engine

    def create(*args, **kwargs):
        engine = original(*args, **kwargs)
        monkeypatch.setattr(engine, "dispose", MagicMock(wraps=engine.dispose))
        created.append(engine)
        return engine

    monkeypatch.setattr(sqlalchemy, "create_engine", create)
    return created


def test_kernel_owned_surrogate_starts_both_protocol_floors_ignoring_ambient_urls(
    tmp_path, monkeypatch, engines
):
    unrelated = tmp_path / "ordinary.sqlite"
    unrelated.write_bytes(b"unrelated existing data")
    for key in ("OCWP_DATABASE_URL", "OCWP_E2E_DATABASE_URL", "OCWP_TEST_DATABASE_URL"):
        monkeypatch.setenv(key, "sqlite:///" + str(unrelated))
    monkeypatch.setenv("OCWP_DATABASE_URL_FILE", str(tmp_path / "never-read"))
    served = []

    def serve(app, **kwargs):
        served.append(app)
        assert kwargs == {
            "host": "127.0.0.1",
            "port": 8007,
            "log_level": "warning",
            "access_log": False,
        }
        assert app.state.settings.database_url != "sqlite:///" + str(unrelated)
        assert app.state.settings.environment == "test" and app.state.settings.cutover_enabled
        with app.state.session_factory() as session:
            assert sorted(session.scalars(select(OrganizationRecord.minimum_write_protocol))) == [
                0,
                1,
            ]
            users = session.scalars(select(UserRecord)).all()
            assert len(users) == 2 and all(user.capabilities == ["*"] for user in users)
        with TestClient(app) as client:
            assert client.get("/health/ready").status_code == 200
            for org in (
                "00000000-0000-7000-8000-000000000001",
                "00000000-0000-7000-8000-000000000101",
            ):
                result = client.post(
                    "/api/v1/auth/login",
                    json={
                        "organization_id": org,
                        "username": "e2e-admin",
                        "password": "ocwp-e2e-password",
                    },
                )
                assert result.status_code == 200

    monkeypatch.setattr(uvicorn, "run", serve)
    kernel_main()()
    assert len(served) == 1 and len(engines) == 1
    engines[0].dispose.assert_called_once()
    assert not Path(engines[0].url.database).parent.exists()
    assert unrelated.read_bytes() == b"unrelated existing data"


@pytest.mark.parametrize("stage", ["schema", "seed", "app", "serve"])
def test_owned_engine_and_directory_are_released_after_failure(monkeypatch, engines, stage):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic " + stage + " failure")

    if stage == "schema":
        monkeypatch.setattr(Base.metadata, "create_all", fail)
    elif stage == "seed":
        monkeypatch.setattr(PasswordService, "hash", fail)
    elif stage == "app":
        import cycling_workshop.app

        monkeypatch.setattr(cycling_workshop.app, "create_app", fail)
    else:
        monkeypatch.setattr(uvicorn, "run", fail)
    with pytest.raises(RuntimeError, match="synthetic " + stage):
        kernel_main()()
    assert len(engines) == 1
    engines[0].dispose.assert_called_once()
    assert not Path(engines[0].url.database).parent.exists()


def test_direct_shared_seed_rejects_existing_sqlite_before_connect(tmp_path, monkeypatch):
    path = tmp_path / "existing_test.sqlite"
    path.write_bytes(b"must not touch")
    connect = MagicMock(side_effect=AssertionError("must reject before connecting"))
    monkeypatch.setattr(prepare_e2e_database, "create_engine", connect)
    with pytest.raises(RuntimeError, match="dedicated local test database"):
        prepare_e2e_database.seed_browser_identity("sqlite:///" + str(path))
    connect.assert_not_called()
    assert path.read_bytes() == b"must not touch"
