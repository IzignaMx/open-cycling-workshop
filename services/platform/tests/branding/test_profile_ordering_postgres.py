"""Additional real-lock ordering evidence; never substituted with SQLite."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from cycling_workshop.branding.service import BrandingService
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.security import SessionTokenService
from test_administration_postgres import AdministrationPostgres, HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres
from test_context_postgres import _lock_barrier, _wait_at_barrier
from test_profile_postgres import PAYLOAD, prepare


@pytest.mark.parametrize("method", ["GET", "PUT"])
@pytest.mark.parametrize("barrier", ["organization", "user"])
def test_branding_expiry_during_observed_real_lock_wait(administration_postgres, method, barrier):
    db = administration_postgres
    actor, _, path = prepare(db)
    issued = datetime(2026, 10, 14, 1, 2, 3, tzinfo=UTC)
    now = [issued]
    tokens = SessionTokenService(
        secret="synthetic-branding-lock-expiry-secret-at-least-32",
        ttl=timedelta(seconds=60),
        clock=lambda: now[0],
    )
    db.app.state.session_tokens = tokens
    token = tokens.issue(
        Principal(actor, db.organization_id, None, frozenset({"branding.read", "branding.write"}))
    )
    headers = {"Authorization": f"Bearer {token}", "X-OCWP-Write-Protocol": "1"}
    before = db.snapshot()
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(
            db.request, HttpCommand(method, path, headers, PAYLOAD if method == "PUT" else None)
        )
        try:
            assert len(_wait_at_barrier(db, future, barrier)) == 1
            now[0] = issued + timedelta(seconds=60)
        finally:
            blocker.rollback()
        response = future.result(timeout=25)
    assert response.status_code == 401, response.text
    assert response.headers["cache-control"] == "no-store"
    assert db.snapshot() == before
    assert db.audits() == []


def test_branding_read_first_holds_authority_until_its_snapshot_completes(
    administration_postgres, monkeypatch
):
    db = administration_postgres
    actor, headers, path = prepare(db)
    administrator = db.seed(owner=True)
    admin_headers = {**db.headers(administrator), "X-OCWP-Write-Protocol": "1"}
    entered, release = Event(), Event()
    original = BrandingService._response

    def paused(service, principal, location, profile):
        result = original(service, principal, location, profile)
        if principal.user_id == actor:
            entered.set()
            assert release.wait(timeout=15), "Test must release read snapshot"
        return result

    monkeypatch.setattr(BrandingService, "_response", paused)
    with ThreadPoolExecutor(max_workers=2) as executor:
        read = executor.submit(db.request, HttpCommand("GET", path, headers))
        assert entered.wait(timeout=10), "Read must acquire its real authority locks"
        revoke = executor.submit(
            db.request,
            HttpCommand(
                "POST",
                f"/api/v1/admin/users/{actor}/revoke-sessions",
                admin_headers,
                {"expected_version": 1},
            ),
        )
        try:
            assert len(db.wait_for_lock_waiters([revoke])) == 1
            assert not read.done()
        finally:
            release.set()
        assert read.result(timeout=25).status_code == 200
        assert revoke.result(timeout=25).status_code == 200
    assert db.request(HttpCommand("GET", path, headers)).status_code == 401


def test_branding_tenant_lock_does_not_block_independent_organization(administration_postgres):
    db: AdministrationPostgres = administration_postgres
    actor, headers, path = prepare(db)
    db.app.state.settings = replace(db.app.state.settings, cutover_enabled=True)
    foreign = db.seed(
        organization_id=db.foreign_organization_id,
        location_id=db.foreign_location_id,
        capabilities=frozenset({"branding.read"}),
    )
    foreign_headers = {
        **db.headers(foreign, organization_id=db.foreign_organization_id),
        "X-OCWP-Write-Protocol": "1",
    }
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        _lock_barrier(db, blocker, actor, "organization")
        waiting = executor.submit(db.request, HttpCommand("GET", path, headers))
        try:
            assert len(_wait_at_barrier(db, waiting, "organization")) == 1
            independent = executor.submit(
                db.request,
                HttpCommand(
                    "GET", f"/api/v1/locations/{db.foreign_location_id}/branding", foreign_headers
                ),
            )
            response = independent.result(timeout=5)
            assert response.status_code == 200, response.text
            assert response.json()["organization_id"] == db.foreign_organization_id
            assert not waiting.done()
        finally:
            blocker.rollback()
        assert waiting.result(timeout=25).status_code == 200
