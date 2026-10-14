"""Real row-lock qualification, skipped explicitly without safe PostgreSQL 18 URL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.branding.models import WorkshopBrandProfileRecord
from cycling_workshop.identity.branding_cli import adopt_branding
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import LEGACY_WILDCARD_CAPABILITIES
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import select
from test_administration_postgres import AdministrationPostgres, HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres
from test_context_postgres import _lock_barrier, _wait_at_barrier

PAYLOAD = {
    "expected_version": 0,
    "display_name": "Synthetic shared brand",
    "palette_id": "jade",
    "logo_png_base64": None,
}


def prepare(db: AdministrationPostgres):
    db.app.state.settings = replace(db.app.state.settings, cutover_enabled=True)
    actor = db.seed(capabilities=frozenset({"branding.read", "branding.write"}))
    headers = {**db.headers(actor), "X-OCWP-Write-Protocol": "1"}
    return actor, headers, f"/api/v1/locations/{db.location_id}/branding"


@pytest.mark.parametrize("existing", [False, True])
def test_two_real_writers_have_one_cas_success_even_for_first_create(
    administration_postgres, existing
):
    db = administration_postgres
    _, headers, path = prepare(db)
    version = 0
    if existing:
        assert db.request(HttpCommand("PUT", path, headers, PAYLOAD)).status_code == 200
        version = 1
    responses = db.race(
        *[
            HttpCommand(
                "PUT",
                path,
                headers,
                {**PAYLOAD, "expected_version": version, "display_name": f"Writer {number}"},
            )
            for number in (1, 2)
        ]
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    success = next(response.json() for response in responses if response.status_code == 200)
    assert success["version"] == version + 1
    assert db.request(HttpCommand("GET", path, headers)).json() == success
    with db.factory() as session:
        assert len(list(session.scalars(select(WorkshopBrandProfileRecord)))) == 1
    assert len(db.audits()) == version + 1


@pytest.mark.parametrize("method", ["GET", "PUT"])
@pytest.mark.parametrize(
    "barrier,change",
    [
        (barrier, change)
        for barrier in ("organization", "user")
        for change in ("revoke", "disable", "grants", "scope", "incarnation")
        if not (barrier == "user" and change == "incarnation")
    ],
)
def test_profile_reauthorizes_after_observed_lock_wait(
    administration_postgres, method, barrier, change
):
    db = administration_postgres
    actor, headers, path = prepare(db)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(
            db.request, HttpCommand(method, path, headers, PAYLOAD if method == "PUT" else None)
        )
        try:
            assert len(_wait_at_barrier(db, future, barrier)) == 1
            account = blocker.get(UserRecord, actor)
            if change == "revoke":
                account.session_version += 1
            if change == "disable":
                account.is_active = False
            if change == "grants":
                account.capabilities = []
            if change == "scope":
                account.location_id = db.other_location_id
            if change == "incarnation":
                blocker.get(OrganizationRecord, db.organization_id).dataset_incarnation = str(
                    uuid4()
                )
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=25)
    assert response.status_code == (403 if change in {"grants", "scope"} else 401), response.text
    assert response.headers["cache-control"] == "no-store"
    assert db.audits() == []
    with db.factory() as session:
        assert list(session.scalars(select(WorkshopBrandProfileRecord))) == []


def test_explicit_adoption_serializes_and_only_one_expected_version_commits(
    administration_postgres,
):
    db = administration_postgres
    actor = db.seed(owner=True, capabilities=LEGACY_WILDCARD_CAPABILITIES)

    def adopt():
        try:
            return adopt_branding(
                db.app.state.settings,
                organization_id=db.organization_id,
                owner_id=actor,
                expected_version=1,
            )
        except ApiError as exc:
            return exc.code

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        db.lock_organization(blocker)
        futures = [executor.submit(adopt) for _ in range(2)]
        try:
            assert len(db.wait_for_lock_waiters(futures)) == 2
        finally:
            blocker.rollback()
        results = [future.result(timeout=25) for future in futures]
    assert sum(isinstance(result, dict) and result["changed"] for result in results) == 1
    assert results.count("stale_user_version") == 1
    assert db.user(actor).version == db.user(actor).session_version == 2
    assert len(db.audits()) == 1 and db.audits()[0].action == "user.branding_adopted"
