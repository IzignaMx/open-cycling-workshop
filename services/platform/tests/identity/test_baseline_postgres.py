"""Adversarial baseline HTTP transactions against an explicitly opted-in PostgreSQL.

The shared administration fixture validates routing before connecting and owns its
random schema exclusively. SQLite and sleep-only concurrency evidence are never
substitutes for these tests; an absent safe test URL is an explicit skip.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.sync.baseline_models import BaselineFamily
from httpx import Response
from sqlalchemy import select, text
from test_administration_postgres import AdministrationPostgres, HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres
from test_context_postgres import _lock_barrier, _wait_at_barrier

BASE = "/api/v1/sync/baselines"
GRANTS = frozenset({"sync.pull", "customers.read"})


def _identity(db: AdministrationPostgres) -> tuple[str, dict[str, str]]:
    actor = db.seed(location_id=db.location_id, capabilities=GRANTS)
    token = db.app.state.session_tokens.issue(
        Principal(actor, db.organization_id, db.location_id, GRANTS)
    )
    return actor, {"Authorization": f"Bearer {token}"}


def _start_command(db: AdministrationPostgres, headers: dict[str, str]) -> HttpCommand:
    context = db.request(
        HttpCommand("GET", f"/api/v1/auth/context?selected_location_id={db.location_id}", headers)
    )
    assert context.status_code == 200, context.text
    return HttpCommand(
        "POST",
        f"{BASE}/start",
        headers,
        {
            "protocol": 1,
            "selected_location_id": db.location_id,
            "authorization_epoch": context.json()["authorization_epoch"],
            "request_id": str(uuid4()),
        },
    )


def _progress(headers: dict[str, str], path: str, token: str) -> HttpCommand:
    return HttpCommand("POST", path, headers, {"protocol": 1, "continuation": token})


def _ok(response: Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def _families(db: AdministrationPostgres) -> list[dict[str, Any]]:
    with db.engine.connect() as connection:
        return [
            dict(row)
            for row in connection.execute(
                select(BaselineFamily.__table__).order_by(BaselineFamily.reference_hash)
            ).mappings()
        ]


def _worker(db: AdministrationPostgres) -> AdministrationPostgres:
    """Fresh application composition shares only PostgreSQL and configured signing key."""
    return replace(db, app=create_app(db.app.state.settings, session_factory=db.factory))


def _race(db: AdministrationPostgres, commands: list[HttpCommand]) -> list[Response]:
    workers = [_worker(db) for _ in commands]
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=len(commands)) as executor:
        db.lock_organization(blocker)
        futures = [
            executor.submit(worker.request, command)
            for worker, command in zip(workers, commands, strict=True)
        ]
        try:
            waiting = db.wait_for_lock_waiters(futures)
        finally:
            blocker.rollback()
        responses = [future.result(timeout=25) for future in futures]
    assert len(waiting) == len(commands), (
        "Each independently composed application must visibly block in a distinct "
        f"PostgreSQL session; observed={len(waiting)}, statuses="
        f"{[response.status_code for response in responses]}"
    )
    return responses


@pytest.mark.parametrize("barrier", ["organization", "user"])
@pytest.mark.parametrize("operation", ["start", "page", "start_replay"])
@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ("revoke", 401, None),
        ("disable", 401, None),
        ("location", 401, None),
        ("pull_grant", 403, "capability_denied"),
        ("read_grant", 409, "context_changed"),
    ],
)
def test_authority_reloaded_after_observed_wait(
    administration_postgres: AdministrationPostgres,
    barrier: str,
    operation: str,
    change: str,
    status: int,
    code: str | None,
) -> None:
    db = administration_postgres
    actor, headers = _identity(db)
    command = _start_command(db, headers)
    if operation != "start":
        started = _ok(db.request(command))
        if operation == "page":
            command = _progress(headers, f"{BASE}/page", started["continuation"])
    before = _families(db)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(db.request, command)
        try:
            assert len(_wait_at_barrier(db, future, barrier)) == 1
            account = blocker.get(UserRecord, actor)
            assert account is not None
            # Isolate persisted authority reload from the admin API's session bump.
            if change == "revoke":
                account.session_version += 1
            elif change == "disable":
                account.is_active = False
            elif change == "location":
                account.location_id = db.other_location_id
            elif change == "pull_grant":
                account.capabilities = ["customers.read"]
            else:
                account.capabilities = ["sync.pull"]
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=25)
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    if code is not None:
        assert response.json()["error"]["code"] == code
    else:
        assert response.json()["detail"] == "invalid session"
    assert _families(db) == before


@pytest.mark.parametrize("barrier", ["organization", "user"])
@pytest.mark.parametrize("operation", ["start", "page", "start_replay"])
def test_jwt_expires_while_request_is_observably_waiting(
    administration_postgres: AdministrationPostgres,
    barrier: str,
    operation: str,
) -> None:
    db = administration_postgres
    now = [datetime(2026, 1, 2, tzinfo=UTC)]
    db.app.state.session_tokens = SessionTokenService(
        secret="synthetic-baseline-expiry-signing-secret-at-least-32",
        ttl=timedelta(seconds=60),
        clock=lambda: now[0],
    )
    actor, headers = _identity(db)
    command = _start_command(db, headers)
    if operation != "start":
        started = _ok(db.request(command))
        if operation == "page":
            command = _progress(headers, f"{BASE}/page", started["continuation"])
    before = _families(db)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(db.request, command)
        try:
            assert len(_wait_at_barrier(db, future, barrier)) == 1
            now[0] += timedelta(seconds=60)
        finally:
            blocker.rollback()
        response = future.result(timeout=25)
    assert response.status_code == 401, response.text
    assert response.headers["cache-control"] == "no-store"
    assert _families(db) == before


def test_duplicate_start_cross_worker_is_exact_and_durable(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    _, headers = _identity(db)
    command = _start_command(db, headers)
    first, second = _race(db, [command, command])
    start = _ok(first)
    _ok(second)
    assert first.content == second.content
    assert len(_families(db)) == 1
    _ok(db.request(_progress(headers, f"{BASE}/page", start["continuation"])))
    before = _families(db)
    replay = _worker(db).request(command)
    _ok(replay)
    assert replay.content == first.content
    assert _families(db) == before


def test_three_simultaneous_starts_have_two_slots_and_one_safe_refusal(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    _, headers = _identity(db)
    commands = [_start_command(db, headers) for _ in range(3)]
    responses = _race(db, commands)
    assert sorted(response.status_code for response in responses) == [200, 200, 409]
    refusal = next(response for response in responses if response.status_code == 409)
    assert refusal.json()["error"]["code"] == "baseline_in_progress"
    assert int(refusal.headers["retry-after"]) >= 1
    assert refusal.headers["cache-control"] == "no-store"
    families = _families(db)
    assert len(families) == 2
    for response in responses:
        if response.status_code == 200:
            body = response.json()
            assert body["baseline_id"] not in refusal.text
            assert body["continuation"] not in refusal.text
    retry = _worker(db).request(commands[responses.index(refusal)])
    assert retry.status_code == 409
    assert _families(db) == families


def test_page_finalize_and_completion_retries_serialize_without_double_advance(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    _, headers = _identity(db)
    start = _ok(db.request(_start_command(db, headers)))
    token = start["continuation"]
    for sequence, path in enumerate(
        [f"{BASE}/page", f"{BASE}/finalize", "/api/v1/sync/deltas/page"], start=1
    ):
        command = _progress(headers, path, token)
        first, second = _race(db, [command, command])
        body = _ok(first)
        _ok(second)
        assert first.content == second.content
        rows = _families(db)
        assert len(rows) == 1 and rows[0]["sequence"] == sequence
        assert body["predecessor"] == token
        token = body["continuation"]
    assert body["phase"] == "complete"
    assert body["completion"]["checkpoint"] == token


def test_cleanup_preserves_completed_checkpoint_past_original_baseline_expiry(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    now = [datetime(2026, 1, 2, tzinfo=UTC)]
    db.app.state.session_tokens = SessionTokenService(
        secret="synthetic-baseline-cleanup-signing-secret-at-least-32",
        ttl=timedelta(hours=8),
        clock=lambda: now[0],
    )
    _, headers = _identity(db)
    start_command = _start_command(db, headers)
    completed = _ok(db.request(start_command))
    for path in (f"{BASE}/page", f"{BASE}/finalize", "/api/v1/sync/deltas/page"):
        completed = _ok(db.request(_progress(headers, path, completed["continuation"])))
    checkpoint = completed["continuation"]
    abandoned = _ok(db.request(_start_command(db, headers)))
    completed_row = next(row for row in _families(db) if row["phase"] == "complete")
    now[0] += timedelta(minutes=31)
    _ok(db.request(_start_command(db, headers)))  # Admission triggers scoped cleanup.
    rows = _families(db)
    assert len(rows) == 2
    assert abandoned["baseline_id"] not in {row["baseline_id"] for row in rows}
    assert next(row for row in rows if row["phase"] == "complete") == completed_row
    activation = HttpCommand(
        "POST", f"{BASE}/validate-activation", headers, {"protocol": 1, "checkpoint": checkpoint}
    )
    for _ in range(2):
        assert _ok(db.request(activation))["checkpoint"] == checkpoint
    assert _families(db) == rows
    expired_start = db.request(start_command)
    assert expired_start.status_code == 410
    assert expired_start.json()["error"]["code"] == "baseline_expired"
    incremental = _ok(db.request(_progress(headers, "/api/v1/sync/deltas/page", checkpoint)))
    assert incremental["phase"] == "complete" and incremental["baseline_id"] is None
    retained = next(
        row for row in _families(db) if row["baseline_id"] == completed_row["baseline_id"]
    )
    assert retained["family_expires_at"] == completed_row["family_expires_at"]
    assert retained["retention_until"] == completed_row["retention_until"]
    stale_activation = db.request(activation)
    assert stale_activation.status_code == 409
    assert stale_activation.json()["error"]["code"] == "continuation_stale"


@pytest.mark.parametrize("barrier", ["organization", "user"])
def test_lock_timeout_rolls_back_and_retry_can_progress(
    administration_postgres: AdministrationPostgres,
    barrier: str,
) -> None:
    db = administration_postgres
    actor, headers = _identity(db)
    start = _ok(db.request(_start_command(db, headers)))
    command = _progress(headers, f"{BASE}/page", start["continuation"])
    before = _families(db)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        _lock_barrier(db, blocker, actor, barrier)
        future = executor.submit(db.request, command)
        try:
            assert len(_wait_at_barrier(db, future, barrier)) == 1
            # Keep the actual blocker until PostgreSQL's LOCAL lock_timeout fires.
            response = future.result(timeout=15)
        finally:
            blocker.rollback()
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "temporary_unavailable"
    assert int(response.headers["retry-after"]) >= 1
    assert response.headers["cache-control"] == "no-store"
    assert _families(db) == before
    _ok(db.request(command))
    assert _families(db)[0]["sequence"] == before[0]["sequence"] + 1


def test_statement_timeout_during_flush_rolls_back_progress_and_cached_response(
    administration_postgres: AdministrationPostgres,
) -> None:
    db = administration_postgres
    _, headers = _identity(db)
    start = _ok(db.request(_start_command(db, headers)))
    command = _progress(headers, f"{BASE}/page", start["continuation"])
    before = _families(db)
    with db.engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION delay_baseline_update() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN PERFORM pg_sleep(6); RETURN NEW; END; $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER delay_baseline_update BEFORE UPDATE ON sync_baseline_families "
                "FOR EACH ROW EXECUTE FUNCTION delay_baseline_update()"
            )
        )
    try:
        response = db.request(command)
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "temporary_unavailable"
        assert int(response.headers["retry-after"]) >= 1
        assert response.headers["cache-control"] == "no-store"
        assert _families(db) == before
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("DROP TRIGGER delay_baseline_update ON sync_baseline_families"))
            connection.execute(text("DROP FUNCTION delay_baseline_update()"))
    _ok(db.request(command))
    assert _families(db)[0]["sequence"] == before[0]["sequence"] + 1
