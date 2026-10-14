"""Full-head baseline migration and guarded reverse path preserve identity history."""

from datetime import timedelta

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from test_identity_migration import (
    NOW,
    _audit,
    _insert,
    _revision,
    _seed_tenant,
    _snapshot,
    _user,
)
from test_identity_migration import identity_migration_database as identity_migration_database


def test_baseline_upgrade_empty_downgrade_reupgrade_preserves_identity_and_audit(
    identity_migration_database,
):
    config, engine = identity_migration_database
    command.upgrade(config, "0008")
    org, location = _seed_tenant(engine)
    _insert(engine, "users", _user(org, location_id=location))
    _insert(engine, "identity_audit_events", _audit(org))
    _insert(
        engine,
        "customers",
        dict(
            id="preserved-customer",
            organization_id=org,
            location_id=location,
            display_name="Preserved domain row",
            email=None,
            phone=None,
            created_at=NOW,
            updated_at=NOW,
            version=7,
        ),
    )
    customers = _snapshot(engine, "customers")
    users, audits = _snapshot(engine, "users"), _snapshot(engine, "identity_audit_events")
    for target in ("0009", "0008", "0009"):
        if target == "0008":
            command.downgrade(config, target)
        else:
            command.upgrade(config, target)
        assert _revision(engine) == target
        assert _snapshot(engine, "users") == users
        assert _snapshot(engine, "customers") == customers
        assert _snapshot(engine, "identity_audit_events") == audits
        assert ("sync_baseline_families" in inspect(engine).get_table_names()) == (target == "0009")
        for statement in (
            "UPDATE identity_audit_events SET action='changed'",
            "DELETE FROM identity_audit_events",
        ):
            with engine.begin() as connection, pytest.raises(IntegrityError):
                connection.execute(text(statement))


def test_baseline_downgrade_refuses_retained_proof_without_schema_or_history_loss(
    identity_migration_database,
):
    config, engine = identity_migration_database
    command.upgrade(config, "head")
    org, location = _seed_tenant(engine)
    user = _user(org, location_id=location)
    _insert(engine, "users", user)
    _insert(engine, "identity_audit_events", _audit(org))
    values = dict(
        reference_hash="a" * 64,
        baseline_id="baseline",
        organization_id=org,
        user_id=user["id"],
        location_id=location,
        request_id="request",
        epoch="epoch",
        phase="scan",
        sequence=0,
        created_at=NOW,
        baseline_expires_at=NOW + timedelta(minutes=30),
        family_expires_at=NOW + timedelta(hours=8),
        retention_until=NOW + timedelta(minutes=30),
        start_json="{}",
        state_json="{}",
    )
    _insert(engine, "sync_baseline_families", values)
    users, audits = _snapshot(engine, "users"), _snapshot(engine, "identity_audit_events")
    with pytest.raises(RuntimeError, match="Baseline proofs remain"):
        command.downgrade(config, "0008")
    assert _revision(engine) == "0009"
    assert _snapshot(engine, "users") == users
    assert _snapshot(engine, "identity_audit_events") == audits
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM sync_baseline_families")) == 1


def test_postgres_downgrade_lock_observes_concurrent_insert_before_emptiness_check(
    identity_migration_database,
):
    import time
    from concurrent.futures import ThreadPoolExecutor

    from test_identity_migration import _table

    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("Access-exclusive migration serialization requires PostgreSQL")
    command.upgrade(config, "head")
    org, location = _seed_tenant(engine)
    user = _user(org, location_id=location)
    _insert(engine, "users", user)
    values = dict(
        reference_hash="b" * 64,
        baseline_id="concurrent",
        organization_id=org,
        user_id=user["id"],
        location_id=location,
        request_id="request",
        epoch="epoch",
        phase="scan",
        sequence=0,
        created_at=NOW,
        baseline_expires_at=NOW + timedelta(minutes=30),
        family_expires_at=NOW + timedelta(hours=8),
        retention_until=NOW + timedelta(minutes=30),
        start_json="{}",
        state_json="{}",
    )
    table = _table(engine, "sync_baseline_families")
    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        blocker.execute(text("LOCK TABLE sync_baseline_families IN ROW EXCLUSIVE MODE"))
        pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        future = executor.submit(command.downgrade, config, "0008")
        try:
            deadline = time.monotonic() + 10
            waiting = False
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
                while time.monotonic() < deadline and not future.done():
                    waiting = bool(
                        observer.scalar(
                            text(
                                "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE "
                                ":blocker = ANY(pg_blocking_pids(pid)) AND wait_event_type='Lock' "
                                "AND query ILIKE '%LOCK TABLE sync_baseline_families%')"
                            ),
                            {"blocker": pid},
                        )
                    )
                    if waiting:
                        break
                    time.sleep(0.02)
            assert waiting, "Migration must wait for the concurrent inserting transaction"
            blocker.execute(table.insert(), values)
            blocker.commit()
        finally:
            blocker.rollback()
        with pytest.raises(RuntimeError, match="Baseline proofs remain"):
            future.result(timeout=15)
    assert _revision(engine) == "0009"
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM sync_baseline_families")) == 1
