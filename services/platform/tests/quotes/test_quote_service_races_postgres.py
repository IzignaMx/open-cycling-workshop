"""Five tiny actual-service races with observed PostgreSQL organization waits.

Two participant sessions and a read-only observer establish correctness only;
these cases do not qualify throughput, maximum capacity or network cancellation.
"""

import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import replace
from threading import Event

import pytest
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.quotes import service
from cycling_workshop.quotes.service import QuoteServiceError
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session
from test_identity_migration import identity_migration_database as identity_migration_database
from test_quote_application_service import GRANTS
from test_quote_application_service import actors as actors
from test_quote_application_service import execute, totals
from test_quote_application_service_postgres import postgres_identity as postgres_identity
from test_quote_repository import creation, decision
from test_quote_repository import database as database
from test_quote_service_atomicity_postgres import _assert_one_decision, _retained_rows
from test_quote_storage import uid

pytestmark = pytest.mark.parametrize("identity_migration_database", ["postgres"], indirect=True)


def _observe_organization_wait(database, waiter, blocker, future):
    """Require this exact contender's real lock wait, never elapsed-time success."""
    assert waiter != blocker
    deadline = time.monotonic() + 1.0
    with Session(database) as observer:
        observer.execute(text("SET LOCAL statement_timeout = '500ms'"))
        while time.monotonic() < deadline:
            observer.execute(text("SELECT pg_stat_clear_snapshot()"))
            rows = observer.execute(
                text(
                    "SELECT pid, wait_event_type, pg_blocking_pids(pid) AS blockers "
                    "FROM pg_stat_activity WHERE pid = :waiter AND state = 'active' "
                    "AND wait_event_type = 'Lock' AND query ILIKE '%organizations%' "
                    "AND query ILIKE '%FOR UPDATE%' "
                    "AND :blocker = ANY(pg_blocking_pids(pid))"
                ),
                {"waiter": waiter, "blocker": blocker},
            ).mappings()
            waiting = rows.one_or_none()
            if waiting is not None:
                assert waiting["pid"] == waiter
                assert waiting["wait_event_type"] == "Lock"
                assert blocker in waiting["blockers"]
                return
            if future.done():
                break
            # Poll pacing only; the SQL observation above is the sole success condition.
            time.sleep(0.005)
    pytest.fail("contender did not reach its required PostgreSQL organization lock wait")


@pytest.mark.parametrize("contender", ["same_proof", "changed_proof", "distinct_decision"])
def test_two_service_decisions_serialize_one_complete_effect_set(
    database, actors, monkeypatch, contender
):
    first_command = decision()
    second_command = first_command
    if contender == "changed_proof":
        second_command = decision(
            evidence=replace(first_command.command.evidence, note="Changed synthetic proof")
        )
    elif contender == "distinct_decision":
        second_command = decision(decision_id=uid(101))
    with Session(database) as session:
        execute(session, actors, creation())

    first_locked, second_connected, release_first = Event(), Event(), Event()
    pids = {}
    original_lock_writer = service.lock_writer

    def hold_first_after_real_admission(session, *args, **kwargs):
        fresh = original_lock_writer(session, *args, **kwargs)
        if session.info.get("quote_race_role") == "first":
            pids["first"] = session.connection().connection.driver_connection.info.backend_pid
            first_locked.set()
            assert release_first.wait(timeout=2.0), "first service was not released in time"
        return fresh

    def call_service(role, command):
        with Session(database) as session:
            session.info["quote_race_role"] = role

            def connected(_session, transaction, connection):
                if role == "second" and not transaction.nested:
                    pids["second"] = connection.connection.driver_connection.info.backend_pid
                    second_connected.set()

            event.listen(session, "after_begin", connected)
            try:
                return execute(session, actors, command)
            except QuoteServiceError as error:
                return error
            finally:
                event.remove(session, "after_begin", connected)

    with monkeypatch.context() as patch:
        patch.setattr(service, "lock_writer", hold_first_after_real_admission)
        executor = ThreadPoolExecutor(max_workers=2)
        futures = []
        try:
            first = executor.submit(call_service, "first", first_command)
            futures.append(first)
            assert first_locked.wait(timeout=2.0), "first service never acquired authority locks"
            second = executor.submit(call_service, "second", second_command)
            futures.append(second)
            assert second_connected.wait(timeout=1.0), "second service never opened its session"
            _observe_organization_wait(database, pids["second"], pids["first"], second)
        finally:
            release_first.set()
            # Completion follows each worker's Session exit. On timeout, fail;
            # only the existing whole-worker containment can stop a stuck thread.
            _, unfinished = wait(futures, timeout=8.0)
            executor.shutdown(wait=False, cancel_futures=True)
            assert not unfinished, "service participants did not finish within the cleanup wait"
        first_result = first.result(timeout=0)
        second_result = second.result(timeout=0)

    assert not isinstance(first_result, Exception)
    assert first_result["delivery"] == "applied"
    if contender == "same_proof":
        assert not isinstance(second_result, Exception)
        assert second_result["delivery"] == "replayed"
        assert second_result["receipt"] == first_result["receipt"]
    else:
        assert isinstance(second_result, QuoteServiceError)
        assert second_result.code == "quote_conflict"
        assert second_result.outcome_unknown is False
    _assert_one_decision(database, actors, first_result, first_command)


@pytest.mark.parametrize("replay", [False, True])
def test_waiting_service_rechecks_revoked_quote_grant_for_new_and_exact_replay(
    database, actors, replay
):
    command = decision()
    with Session(database) as session:
        execute(session, actors, creation())
        if replay:
            execute(session, actors, command)
        before_totals = totals(session)
    baseline = _retained_rows(database)
    assert "quotes.authorize" in actors.capabilities
    waiter_connected = Event()
    waiter_pid = []

    def call_service():
        with Session(database) as session:

            def connected(_session, transaction, connection):
                if not transaction.nested:
                    waiter_pid.append(connection.connection.driver_connection.info.backend_pid)
                    waiter_connected.set()

            event.listen(session, "after_begin", connected)
            try:
                return execute(session, actors, command, enabled=not replay)
            except QuoteServiceError as error:
                return error
            finally:
                event.remove(session, "after_begin", connected)

    with Session(database) as blocker:
        locked = blocker.scalar(
            select(OrganizationRecord.id).where(OrganizationRecord.id == "a").with_for_update()
        )
        assert locked == "a"
        blocker_pid = blocker.connection().connection.driver_connection.info.backend_pid
        executor = ThreadPoolExecutor(max_workers=1)
        futures = []
        try:
            future = executor.submit(call_service)
            futures.append(future)
            assert waiter_connected.wait(timeout=2.0), "service never opened its waiting session"
            assert len(waiter_pid) == 1
            _observe_organization_wait(database, waiter_pid[0], blocker_pid, future)
            actor = blocker.get(UserRecord, "actor-a")
            assert actor is not None
            actor.capabilities = sorted(GRANTS - {"quotes.authorize"})
            blocker.commit()
        finally:
            blocker.rollback()
            # Do not report cleanup success while a service Session may remain open.
            _, unfinished = wait(futures, timeout=8.0)
            executor.shutdown(wait=False, cancel_futures=True)
            assert not unfinished, "service participant did not finish within the cleanup wait"
        result = future.result(timeout=0)

    assert isinstance(result, QuoteServiceError)
    assert result.code == "quote_access_denied"
    assert result.outcome_unknown is False
    with Session(database) as session:
        actor = session.get(UserRecord, "actor-a")
        assert actor is not None
        assert "quotes.authorize" not in actor.capabilities
        assert totals(session) == before_totals
    assert _retained_rows(database) == baseline
