"""Authenticated context revalidation behind real PostgreSQL row-lock waits.

Reuse the dedicated-target and exclusively owned-schema fixture. These tests
never substitute SQLite or infer lock contention from sleeps alone.
"""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.roles import CAPABILITIES
from cycling_workshop.identity.security import SessionTokenService
from httpx import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from test_administration_postgres import AdministrationPostgres, HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres

CONTEXT = "/api/v1/auth/context"


def _lock_barrier(db: AdministrationPostgres, blocker: Session, actor: str, barrier: str) -> None:
    if barrier == "organization":
        db.lock_organization(blocker)
    else:
        assert (
            blocker.scalar(select(UserRecord).where(UserRecord.id == actor).with_for_update())
            is not None
        )


def _wait_at_barrier(
    db: AdministrationPostgres, future: Future[Response], barrier: str
) -> set[int]:
    if barrier == "organization":
        return db.wait_for_lock_waiters([future])
    deadline = time.monotonic() + 10
    waiting: set[int] = set()
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        while time.monotonic() < deadline:
            waiting = set(
                observer.scalars(
                    text(
                        "SELECT pid FROM pg_stat_activity "
                        "WHERE application_name = :application_name "
                        "AND state = 'active' AND wait_event_type = 'Lock' "
                        "AND query ILIKE '%users%' AND query ILIKE '%FOR UPDATE%' "
                        "AND cardinality(pg_blocking_pids(pid)) > 0"
                    ),
                    {"application_name": db.application_name},
                )
            )
            if len(waiting) == 1 or future.done():
                break
            time.sleep(0.02)
    return waiting


@pytest.mark.parametrize("barrier", ["organization", "user"])
@pytest.mark.parametrize(
    "change", ["revoke", "disable", "location", "remove_grants", "widen_grants", "narrow_location"]
)
def test_context_revalidates_account_after_observed_lock_wait(
    administration_postgres: AdministrationPostgres, change: str, barrier: str
) -> None:
    db = administration_postgres
    actor = db.seed(capabilities=frozenset({"customers.read", "sync.pull"}))
    token = db.app.state.session_tokens.issue(
        Principal(
            actor,
            db.organization_id,
            None if change == "narrow_location" else db.location_id,
            frozenset({"customers.read"}),
        )
    )
    request = HttpCommand(
        "GET",
        f"{CONTEXT}?selected_location_id={db.location_id}",
        {"Authorization": f"Bearer {token}"},
    )

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(db.request, request)
        try:
            waiting = _wait_at_barrier(db, future, barrier)
            assert len(waiting) == 1, f"Context must wait on the real {barrier} row lock"
            account = blocker.get(UserRecord, actor)
            assert account is not None
            # Deliberately isolate fresh persisted-authority checks from the
            # normal administration session bump: stale token grants and scope
            # must still not leak into a successful context response.
            if change == "revoke":
                account.session_version += 1
            elif change == "disable":
                account.is_active = False
            elif change == "location":
                account.location_id = db.other_location_id
            elif change == "remove_grants":
                account.capabilities = []
            elif change == "widen_grants":
                account.capabilities = sorted(CAPABILITIES)
            else:
                account.location_id = db.location_id
            account.version += 1
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=25)

    assert response.headers["cache-control"] == "no-store"
    if change in {"revoke", "disable", "location"}:
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid session"
    else:
        assert response.status_code == 200
        body = response.json()
        assert body["capabilities"] == ([] if change == "remove_grants" else ["customers.read"])
        assert body["account_location_id"] == db.location_id
        assert body["selected_location_id"] == db.location_id
        assert body["principal"] == {
            "api_realm": None,
            "organization_id": db.organization_id,
            "user_id": actor,
        }
        assert body["snapshot_protocol"] is None
    assert db.audits() == []


@pytest.mark.parametrize("barrier", ["organization", "user"])
@pytest.mark.parametrize("seconds_after_issue", [60, 61])
def test_context_rechecks_expiry_after_observed_lock_wait(
    administration_postgres: AdministrationPostgres, seconds_after_issue: int, barrier: str
) -> None:
    db = administration_postgres
    actor = db.seed(location_id=db.location_id, capabilities=frozenset({"customers.read"}))
    issued_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    now = [issued_at]
    tokens = SessionTokenService(
        secret="synthetic-context-postgres-expiry-secret-at-least-32",
        ttl=timedelta(seconds=60),
        clock=lambda: now[0],
    )
    db.app.state.session_tokens = tokens
    token = tokens.issue(
        Principal(actor, db.organization_id, db.location_id, frozenset({"customers.read"}))
    )
    # Assert issuance and validation share the injected clock. No real-time
    # sleeps or fabricated dependency principals can establish this behavior.
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iat"] == int(issued_at.timestamp())
    assert claims["exp"] == int((issued_at + timedelta(seconds=60)).timestamp())
    request = HttpCommand("GET", CONTEXT, {"Authorization": f"Bearer {token}"})
    before = db.snapshot()

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(db.request, request)
        try:
            waiting = _wait_at_barrier(db, future, barrier)
            assert len(waiting) == 1, "Initially valid context must reach the PostgreSQL barrier"
            now[0] = issued_at + timedelta(seconds=seconds_after_issue)
        finally:
            blocker.rollback()
        response = future.result(timeout=25)

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid session"
    assert response.headers["cache-control"] == "no-store"
    assert db.snapshot() == before
