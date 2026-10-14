"""Real PostgreSQL cutover waits; absent safe fixture URL is an explicit skip."""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.identity.cutover import lock_compatibility
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from test_administration_postgres import HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres


def _customer(db, headers, *, organization=None, location=None):
    return HttpCommand(
        "POST",
        "/api/v1/customers",
        headers,
        {
            "customer_id": new_id(),
            "display_name": "Disposable cutover fixture",
            "location_id": location or db.location_id,
        },
    )


def _floor(db, floor):
    with db.factory.begin() as session:
        lock_compatibility(session, db.organization_id).minimum_write_protocol = floor


def _child_request(url: str, settings: Settings, command: HttpCommand, output: Any) -> None:
    """Fresh Python process, engine and app; no inherited request/session state."""
    engine = create_engine(url, hide_parameters=True)
    try:
        app = create_app(settings, session_factory=sessionmaker(engine, expire_on_commit=False))
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.request(
                command.method, command.path, headers=command.headers, json=command.payload
            )
            output.put((response.status_code, response.json()))
    finally:
        engine.dispose()


def _observe(db, blocker_pid, count):
    deadline = time.monotonic() + 15
    with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        while time.monotonic() < deadline:
            rows = observer.execute(
                text(
                    "WITH RECURSIVE waiting AS ("
                    " SELECT pid, query, pg_blocking_pids(pid) AS blockers FROM pg_stat_activity"
                    " WHERE application_name=:app AND state='active' AND wait_event_type='Lock'"
                    "), graph AS ("
                    " SELECT pid, query, ARRAY[pid] AS path FROM waiting"
                    " WHERE :blocker=ANY(blockers) UNION ALL"
                    " SELECT w.pid, w.query, g.path || w.pid FROM waiting w JOIN graph g"
                    " ON g.pid=ANY(w.blockers) WHERE NOT w.pid=ANY(g.path)"
                    ") SELECT DISTINCT pid, query FROM graph"
                ),
                {"app": db.application_name, "blocker": blocker_pid},
            ).all()
            if len(rows) >= count:
                return rows
            time.sleep(0.02)
    raise AssertionError(f"Expected {count} genuinely blocked independent transactions")


@pytest.mark.parametrize("commit_floor", [True, False])
def test_two_process_writers_refresh_floor_after_observed_wait(
    administration_postgres, commit_floor
):
    db = administration_postgres
    actor = db.seed(location_id=db.location_id)
    headers = db.headers(actor)
    before = db.snapshot()
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    commands = [_customer(db, headers), _customer(db, headers)]
    processes = [
        context.Process(
            target=_child_request,
            args=(
                db.engine.url.render_as_string(hide_password=False),
                db.app.state.settings,
                command,
                output,
            ),
        )
        for command in commands
    ]
    with db.factory() as blocker:
        org = lock_compatibility(blocker, db.organization_id)
        pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        org.minimum_write_protocol = 1
        blocker.flush()
        try:
            for process in processes:
                process.start()
            waits = _observe(db, pid, 2)
            assert all("organizations" in row.query and "FOR UPDATE" in row.query for row in waits)
            if commit_floor:
                blocker.commit()
            else:
                blocker.rollback()
            responses = [output.get(timeout=30) for _ in processes]
        finally:
            blocker.rollback()
            for process in processes:
                process.join(timeout=30)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
    assert all(process.exitcode == 0 for process in processes)
    assert [status for status, _ in responses] == ([409, 409] if commit_floor else [201, 201])
    if commit_floor:
        assert all(body["error"]["code"] == "client_upgrade_required" for _, body in responses)
        assert db.snapshot() == before
    with db.factory() as session:
        for command in commands:
            assert (session.get(CustomerRecord, command.payload["customer_id"]) is not None) == (
                not commit_floor
            )


def test_writer_first_commits_before_waiting_floor_change(administration_postgres):
    db = administration_postgres
    actor = db.seed(location_id=db.location_id)
    headers = db.headers(actor)
    command = _customer(db, headers)
    with db.factory() as actor_blocker, ThreadPoolExecutor(max_workers=2) as executor:
        actor_blocker.scalar(select(UserRecord).where(UserRecord.id == actor).with_for_update())
        actor_pid = actor_blocker.scalar(text("SELECT pg_backend_pid()"))
        writer = executor.submit(db.request, command)
        try:
            writer_waits = _observe(db, actor_pid, 1)
            assert "users" in writer_waits[0].query
            writer_pid = writer_waits[0].pid
            activate = executor.submit(_floor, db, 1)
            waits = _observe(db, writer_pid, 1)
            assert "organizations" in waits[0].query
        finally:
            actor_blocker.rollback()
        assert writer.result(timeout=25).status_code == 201
        activate.result(timeout=25)
    with db.factory() as session:
        assert session.get(CustomerRecord, command.payload["customer_id"]) is not None
        assert session.get(OrganizationRecord, db.organization_id).minimum_write_protocol == 1


def test_cutover_barrier_does_not_block_independent_organization(administration_postgres):
    db = administration_postgres
    actor = db.seed(location_id=db.foreign_location_id, organization_id=db.foreign_organization_id)
    headers = db.headers(actor, organization_id=db.foreign_organization_id)
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        lock_compatibility(blocker, db.organization_id).minimum_write_protocol = 1
        blocker.flush()
        future = executor.submit(
            db.request, _customer(db, headers, location=db.foreign_location_id)
        )
        try:
            assert future.result(timeout=5).status_code == 201
        finally:
            blocker.rollback()


def test_signed_expiry_rechecked_after_actor_wait(administration_postgres):
    from datetime import UTC, datetime, timedelta

    from cycling_workshop.identity.security import SessionTokenService

    db = administration_postgres
    actor = db.seed(location_id=db.location_id)
    now = [datetime.now(UTC)]
    tokens = SessionTokenService(
        secret=db.app.state.settings.auth_secret, clock=lambda: now[0], ttl=timedelta(minutes=1)
    )
    db.app.state.session_tokens = tokens
    with db.factory() as session:
        incarnation = session.get(OrganizationRecord, db.organization_id).dataset_incarnation
    token = tokens.issue(
        Principal(
            actor,
            db.organization_id,
            db.location_id,
            frozenset({"customers.write"}),
            dataset_incarnation=incarnation,
        )
    )
    command = _customer(db, {"Authorization": f"Bearer {token}"})
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        blocker.scalar(select(UserRecord).where(UserRecord.id == actor).with_for_update())
        pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        future = executor.submit(db.request, command)
        try:
            _observe(db, pid, 1)
            now[0] += timedelta(minutes=2)
        finally:
            blocker.rollback()
        assert future.result(timeout=25).status_code == 401
    with db.factory() as session:
        assert session.get(CustomerRecord, command.payload["customer_id"]) is None


def test_cross_organization_global_id_race_is_per_item_and_preserves_sibling(
    administration_postgres,
):
    from datetime import UTC, datetime

    from cycling_workshop.identity.cutover import WriteAdmission
    from cycling_workshop.sync.domain import MutationEnvelope, SyncApplicationContext
    from cycling_workshop.sync.proof import envelope_digest
    from cycling_workshop.sync.service import SyncService
    from cycling_workshop.sync.writes import lock_writer

    db = administration_postgres
    db.app.state.settings = replace(db.app.state.settings, cutover_enabled=True)
    actor = db.seed(location_id=db.location_id)
    other_actor = db.seed(
        location_id=db.foreign_location_id, organization_id=db.foreign_organization_id
    )
    headers = db.headers(other_actor, organization_id=db.foreign_organization_id)
    headers["X-OCWP-Write-Protocol"] = "1"
    context = db.request(
        HttpCommand(
            "GET", f"/api/v1/auth/context?selected_location_id={db.foreign_location_id}", headers
        )
    )
    headers["X-OCWP-Authorization-Epoch"] = context.json()["authorization_epoch"]
    mutation = MutationEnvelope(
        new_id(),
        "customer",
        new_id(),
        "create",
        db.organization_id,
        db.location_id,
        None,
        datetime.now(UTC),
        {"display_name": "Winning fixture"},
    )

    def wire(mid, eid):
        return dict(
            mutation_id=mid,
            entity_type="customer",
            entity_id=eid,
            operation="create",
            organization_id=db.foreign_organization_id,
            location_id=db.foreign_location_id,
            base_version=None,
            occurred_at="2026-10-14T00:00:00Z",
            payload={"display_name": "Other fixture"},
        )

    sibling = wire(new_id(), new_id())
    collision = wire(mutation.mutation_id, new_id())
    with db.factory() as winner, ThreadPoolExecutor(max_workers=1) as executor:
        principal = Principal(
            actor, db.organization_id, db.location_id, frozenset({"customers.write", "sync.push"})
        )
        lock_writer(winner, principal, WriteAdmission.for_fixtures(1, enabled=True))
        SyncService(winner).apply(
            mutation,
            context=SyncApplicationContext(actor, 1, envelope_digest(mutation), id(winner)),
        )
        winner.flush()
        winner_pid = winner.scalar(text("SELECT pg_backend_pid()"))
        future = executor.submit(
            db.request,
            HttpCommand(
                "POST", "/api/v1/sync/mutations", headers, {"mutations": [sibling, collision]}
            ),
        )
        try:
            waits = _observe(db, winner_pid, 1)
            assert "sync_mutation_receipts" in waits[0].query
            winner.commit()
        finally:
            winner.rollback()
        response = future.result(timeout=25)
    assert response.status_code == 200, response.text
    assert [result["status"] for result in response.json()["results"]] == ["applied", "conflict"]
    assert response.json()["results"][1]["error_code"] == "sync_conflict"
    assert actor not in response.text and db.organization_id not in response.text
    with db.factory() as session:
        assert session.get(CustomerRecord, sibling["entity_id"]) is not None
        assert session.get(CustomerRecord, collision["entity_id"]) is None
        assert session.get(CustomerRecord, mutation.entity_id) is not None
