"""Real quote contention/restore qualification on exclusively owned test targets.

No SQLite substitute is used for locking, races or restore. The shared fixtures
validate explicit loopback *_test/*_e2e routing and own unpredictable schemas or
databases; unavailable PostgreSQL or matching clients produces explicit skips.
These tests qualify caller-owned storage/admission, not a live quote-grant boundary.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.cutover import WriteAdmission
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.quotes.models import QuoteDecisionRecord, QuoteOperationRecord
from cycling_workshop.quotes.repository import QuoteConflictError, QuoteRepository
from cycling_workshop.sync.writes import lock_writer
from cycling_workshop.tenancy.models import OrganizationRecord
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_administration_postgres import administration_postgres as administration_postgres
from test_backup_postgres_integration import disposable_databases as disposable_databases
from test_quote_repository import admitted, counts, creation, decision, revision
from test_quote_schema import seed_base
from test_quote_storage import NOW, uid


@pytest.fixture
def quote_postgres(administration_postgres):
    db = administration_postgres
    seed_base(db.engine)
    return db


def execute(db, command, *, principal=None, recorded_at=NOW):
    with db.factory() as session:
        try:
            if principal is None:
                admitted(session)
            else:
                lock_writer(session, principal, WriteAdmission.for_fixtures())
            result = QuoteRepository(session).apply(command, recorded_at=recorded_at)
            session.commit()
            return result
        except (QuoteConflictError, ApiError) as error:
            session.rollback()
            return error


def block_organization(session, organization_id="a"):
    assert (
        session.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == organization_id)
            .with_for_update()
        )
        is not None
    )


def race(db, *commands):
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=len(commands)) as executor:
        block_organization(blocker)
        futures = [executor.submit(execute, db, command) for command in commands]
        try:
            waiting = db.wait_for_lock_waiters(futures)
        finally:
            blocker.rollback()
        results = [future.result(timeout=25) for future in futures]
    assert len(waiting) == len(commands), "Every contender must reach a real PostgreSQL lock wait"
    return results


def inspect_history(db):
    with db.factory() as session:
        admitted(session)
        snapshot = QuoteRepository(session).load("a", "location-a", "order-a")
        return snapshot, counts(session)


@pytest.mark.parametrize("changed_proof", [False, True])
def test_concurrent_same_operation_replays_once_or_refuses_changed_proof(
    quote_postgres, changed_proof
):
    db = quote_postgres
    first = creation()
    second = creation(currency="USD") if changed_proof else first
    results = race(db, first, second)
    successes = [result for result in results if not isinstance(result, Exception)]
    failures = [result for result in results if isinstance(result, Exception)]
    if changed_proof:
        assert len(successes) == len(failures) == 1
        assert isinstance(failures[0], QuoteConflictError)
        assert not successes[0].replayed
    else:
        assert not failures and len(successes) == 2
        assert sorted(result.replayed for result in successes) == [False, True]
        assert successes[0].receipt == successes[1].receipt
    snapshot, stored = inspect_history(db)
    assert stored == (1, 1, 1, 1)
    assert len(snapshot.receipts) == 1
    assert snapshot.receipts[0] == successes[0].receipt


def test_two_first_creations_keep_exactly_one_lineage(quote_postgres):
    db = quote_postgres
    results = race(db, creation(), creation(operation_id=uid(300), quote_id=uid(3)))
    assert sum(isinstance(result, QuoteConflictError) for result in results) == 1
    winner = next(result for result in results if not isinstance(result, Exception))
    snapshot, stored = inspect_history(db)
    assert stored == (1, 1, 1, 1)
    assert snapshot.ledger.history.lineage_id == winner.receipt.quote_id


@pytest.mark.parametrize(
    "contenders", ["revisions", "revision_decision", "decisions", "corrections"]
)
def test_current_head_and_sequence_allow_only_one_competing_append(quote_postgres, contenders):
    db = quote_postgres
    assert not isinstance(execute(db, creation()), Exception)
    if contenders == "revisions":
        commands = (revision(), revision(operation_id=uid(202), quote_id=uid(3)))
    elif contenders == "revision_decision":
        commands = (revision(), decision())
    elif contenders == "decisions":
        commands = (decision(), decision(decision_id=uid(101)))
    else:
        assert not isinstance(execute(db, decision()), Exception)
        commands = tuple(
            decision(
                decision_id=uid(number),
                mode="record_correction",
                expected_decision_sequence=1,
                supersedes_entry_id=uid(100),
                reason="Synthetic correction",
            )
            for number in (101, 102)
        )
    results = race(db, *commands)
    assert sum(isinstance(result, QuoteConflictError) for result in results) == 1
    winner = next(result for result in results if not isinstance(result, Exception))
    snapshot, stored = inspect_history(db)
    expected_operations = 3 if contenders == "corrections" else 2
    assert stored == (
        1,
        winner.ledger.history.head.version,
        expected_operations,
        expected_operations,
    )
    assert snapshot.ledger == winner.ledger
    assert snapshot.receipts[-1] == winner.receipt


def test_rollback_releases_first_create_without_publishing_any_partial_effect(quote_postgres):
    db = quote_postgres
    with db.factory() as first, ThreadPoolExecutor(max_workers=1) as executor:
        admitted(first)
        tentative = QuoteRepository(first).apply(creation(), recorded_at=NOW)
        future = executor.submit(execute, db, creation())
        try:
            waiting = db.wait_for_lock_waiters([future])
            with db.factory() as observer:
                assert counts(observer) == (0, 0, 0, 0)
        finally:
            first.rollback()
        committed = future.result(timeout=25)
    assert len(waiting) == 1
    assert not isinstance(committed, Exception) and not committed.replayed
    assert committed.receipt.operation_id == tentative.receipt.operation_id
    assert committed.receipt.quote_outbox_id != tentative.receipt.quote_outbox_id
    snapshot, stored = inspect_history(db)
    assert stored == (1, 1, 1, 1)
    assert snapshot.receipts == (committed.receipt,)


@pytest.mark.parametrize("failure_stage", ["outbox", "receipt", "after_flush"])
def test_late_failure_rolls_back_savepoint_even_if_caller_commits(
    quote_postgres, monkeypatch, failure_stage
):
    db = quote_postgres
    from cycling_workshop.quotes import repository as module

    class InjectedFailure(RuntimeError):
        pass

    with db.factory() as session:
        admitted(session)
        repo = QuoteRepository(session)
        if failure_stage == "outbox":
            original = module.enqueue_outbox

            def fail_outbox(*args, **kwargs):
                original(*args, **kwargs)
                raise InjectedFailure("after outbox insertion")

            monkeypatch.setattr(module, "enqueue_outbox", fail_outbox)
        elif failure_stage == "receipt":
            original_add = session.add

            def fail_receipt(instance, **kwargs):
                original_add(instance, **kwargs)
                if isinstance(instance, QuoteOperationRecord):
                    raise InjectedFailure("after receipt added")

            monkeypatch.setattr(session, "add", fail_receipt)
        else:
            original_result = repo._result

            def fail_result(*args, **kwargs):
                original_result(*args, **kwargs)
                raise InjectedFailure("after every effect flushed")

            monkeypatch.setattr(repo, "_result", fail_result)
        with pytest.raises(InjectedFailure):
            repo.apply(creation(), recorded_at=NOW)
        assert counts(session) == (0, 0, 0, 0)
        session.commit()
    with db.factory() as session:
        assert counts(session) == (0, 0, 0, 0)


@pytest.mark.parametrize("change", ["revoke", "disable", "scope", "incarnation"])
@pytest.mark.parametrize("replay", [False, True])
def test_waiting_writer_revalidates_identity_before_new_write_or_exact_replay(
    quote_postgres, change, replay
):
    db = quote_postgres
    if replay:
        assert not isinstance(execute(db, creation()), Exception)
    with db.factory() as session:
        incarnation = session.get(OrganizationRecord, "a").dataset_incarnation
    principal = Principal(
        "actor-a", "a", "location-a", frozenset(), dataset_incarnation=incarnation
    )
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        block_organization(blocker)
        future = executor.submit(execute, db, creation(), principal=principal)
        try:
            waiting = db.wait_for_lock_waiters([future])
            actor = blocker.get(UserRecord, "actor-a")
            if change == "revoke":
                actor.session_version += 1
            elif change == "disable":
                actor.is_active = False
            elif change == "scope":
                actor.location_id = "other-location-a"
            else:
                blocker.get(OrganizationRecord, "a").dataset_incarnation = str(uuid4())
            blocker.commit()
        finally:
            blocker.rollback()
        result = future.result(timeout=25)
    assert len(waiting) == 1
    assert isinstance(result, ApiError) and result.code == "invalid_session"
    with db.factory() as session:
        assert counts(session) == ((1, 1, 1, 1) if replay else (0, 0, 0, 0))
        assert list(session.scalars(select(QuoteDecisionRecord))) == []


def test_unrelated_organization_is_not_blocked_by_quote_writer(quote_postgres):
    db = quote_postgres
    command = creation(
        operation_id=uid(300),
        quote_id=uid(3),
        organization_id="b",
        location_id="location-b",
        order_id="order-b",
        actor_id="actor-b",
        lines=tuple(
            replace(line, product_id="product-b") if hasattr(line, "product_id") else line
            for line in creation().lines
        ),
    )
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        block_organization(blocker)

        def independent():
            with db.factory() as session:
                admitted(session, "b")
                result = QuoteRepository(session).apply(command, recorded_at=NOW)
                session.commit()
                return result

        future = executor.submit(independent)
        try:
            result = future.result(timeout=10)
            assert not result.replayed and result.order.organization_id == "b"
        finally:
            blocker.rollback()


def test_post_wait_admission_preserves_the_already_narrowed_principal(quote_postgres):
    db = quote_postgres
    incoming = Principal("actor-a", "a", "location-a", frozenset({"orders.read"}))
    with db.factory.begin() as session:
        session.get(UserRecord, "actor-a").capabilities = ["orders.read"]
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        block_organization(blocker)

        def reauthorize():
            with db.factory() as session:
                return lock_writer(session, incoming, WriteAdmission.for_fixtures())

        future = executor.submit(reauthorize)
        try:
            waiting = db.wait_for_lock_waiters([future])
            blocker.get(UserRecord, "actor-a").capabilities = ["orders.read", "orders.write"]
            blocker.commit()
        finally:
            blocker.rollback()
        effective = future.result(timeout=25)
    assert len(waiting) == 1
    assert effective.capabilities == frozenset({"orders.read"})
    # This tests the existing admission intersection, not a future quote-grant boundary.
    with db.factory() as session:
        assert counts(session) == (0, 0, 0, 0)


def retained_quote_rows(engine):
    from cycling_workshop.db.base import Base
    from test_quote_schema import TABLES

    names = TABLES | {"outbox_events", "service_orders", "service_order_events", "sync_changes"}
    with engine.connect() as connection:
        return {
            name: list(
                connection.execute(
                    select(Base.metadata.tables[name]).order_by(
                        *Base.metadata.tables[name].primary_key.columns
                    )
                ).mappings()
            )
            for name in sorted(names)
        }


def test_real_dump_restore_preserves_history_proofs_effect_ids_and_fresh_admission_replay(
    disposable_databases,
    tmp_path,
    monkeypatch,
):
    from alembic import command as migrate
    from cycling_workshop.identity.cutover_cli import recover_cutover
    from cycling_workshop.identity.security import SessionTokenService
    from cycling_workshop.settings import Settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError
    from test_identity_migration import _config

    from scripts.database.backup_postgres import (
        create_backup_bundle,
        restore_backup_bundle,
        verify_backup_bundle,
    )

    source_url, target_url = disposable_databases
    monkeypatch.setenv("OCWP_DATABASE_URL", source_url)
    migrate.upgrade(_config(source_url), "head")
    source, target = create_engine(source_url), create_engine(target_url)
    tokens = SessionTokenService(
        secret="synthetic-quote-restore-signing-key-for-tests-only", clock=lambda: NOW
    )
    admission = WriteAdmission(protocol=1, enabled=True, tokens=tokens)
    commands = (
        creation(),
        decision(),
        decision(
            decision_id=uid(101),
            mode="record_correction",
            expected_decision_sequence=1,
            supersedes_entry_id=uid(100),
            reason="Synthetic correction",
        ),
        decision(
            decision_id=uid(102),
            mode="withdraw_record",
            outcome="WITHDRAW",
            approved_line_ids=(),
            evidence=None,
            expected_decision_sequence=2,
            supersedes_entry_id=uid(101),
            reason="Synthetic withdrawal",
        ),
        revision(expected_decision_sequence=3),
        decision(
            decision_id=uid(103),
            quote_id=uid(2),
            quote_version=2,
            expected_head_id=uid(2),
            expected_head_version=2,
            expected_decision_sequence=3,
        ),
    )
    try:
        with source.connect() as connection:
            assert int(connection.scalar(text("SHOW server_version_num"))) >= 180000
        seed_base(source)
        with Session(source) as session:
            admitted(session)
            repo = QuoteRepository(session)
            original = tuple(repo.apply(command, recorded_at=NOW) for command in commands)
            source_snapshot = repo.load("a", "location-a", "order-a")
            assert counts(session) == (1, 2, 6, 6)
            # Preserve delivery metadata too: replay never repackages a published event.
            outbox = session.get(OutboxRecord, original[0].receipt.quote_outbox_id)
            outbox.attempts, outbox.published_at = 2, NOW
            session.get(OrganizationRecord, "a").minimum_write_protocol = 1
            incarnation = session.get(OrganizationRecord, "a").dataset_incarnation
            session.commit()
        old_token = tokens.issue(
            Principal("actor-a", "a", "location-a", frozenset(), dataset_incarnation=incarnation)
        )
        before = retained_quote_rows(source)
        source.dispose()
        bundle = create_backup_bundle(source_url, tmp_path / "quote-generation")
        assert verify_backup_bundle(bundle)["status"] == "integrity_checked_not_restored"
        restored = restore_backup_bundle(bundle, target_url, confirm_empty_target=True)
        assert restored["status"] == "database_restore_checked"
        assert retained_quote_rows(target) == before
        with pytest.raises(IntegrityError, match="append-only"), target.begin() as connection:
            connection.execute(text("UPDATE quote_operations SET actor_id=actor_id"))
        with Session(target) as session:
            lock_writer(session, tokens.decode(old_token), admission)
            assert QuoteRepository(session).load("a", "location-a", "order-a") == source_snapshot
        # Explicit synthetic restored-target maintenance rotates the incarnation;
        # neither migration nor quote replay implicitly performs this operation.
        recovery = recover_cutover(
            Settings(environment="test", database_url=target_url, cutover_enabled=True),
            organization_id="a",
            expected_incarnation=incarnation,
        )
        assert recovery["changed"] is True and recovery["dataset_incarnation"] != incarnation
        with Session(target) as session:
            with pytest.raises(ApiError) as stale:
                lock_writer(session, tokens.decode(old_token), admission)
            assert stale.value.code == "invalid_session"
        fresh_token = tokens.issue(
            Principal(
                "actor-a",
                "a",
                "location-a",
                frozenset(),
                dataset_incarnation=recovery["dataset_incarnation"],
            )
        )
        with Session(target) as session:
            lock_writer(session, tokens.decode(fresh_token), admission)
            repo = QuoteRepository(session)
            for command, expected in zip(commands, original, strict=True):
                replay = repo.apply(command, recorded_at=NOW + timedelta(minutes=1))
                assert replay.replayed and replay.receipt == expected.receipt
                assert replay.ledger == source_snapshot.ledger
            assert repo.load("a", "location-a", "order-a") == source_snapshot
            assert counts(session) == (1, 2, 6, 6)
            session.commit()
        assert retained_quote_rows(target) == before
        assert retained_quote_rows(source) == before
    finally:
        source.dispose()
        target.dispose()
