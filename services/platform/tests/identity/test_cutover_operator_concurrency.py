"""Maintenance contention proofs use validated, isolated PostgreSQL schemas only."""

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from alembic import command
from cycling_workshop.api.errors import ApiError
from cycling_workshop.cli import bootstrap_admin
from cycling_workshop.identity.cutover_cli import activate_cutover, recover_cutover
from cycling_workshop.settings import Settings
from sqlalchemy import text
from test_identity_migration import _insert, _snapshot
from test_identity_migration import identity_migration_database as identity_migration_database


def configured(engine):
    application = f"ocwp-cutover-{uuid4().hex}"
    url = engine.url.update_query_dict({"application_name": application})
    return Settings(
        environment="test",
        database_url=url.render_as_string(hide_password=False),
        cutover_enabled=True,
    ), application


def observe_waiters(engine, application, futures, expected):
    deadline = time.monotonic() + 10
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        while time.monotonic() < deadline:
            count = observer.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE application_name=:application "
                    "AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid)) > 0"
                ),
                {"application": application},
            )
            if count == expected:
                return
            if any(future.done() for future in futures):
                break
            time.sleep(0.02)
    raise AssertionError("Independent maintenance requests must be observed blocked in PostgreSQL")


def test_concurrent_recovery_same_precondition_rotates_once_and_other_org_is_independent(
    identity_migration_database,
):
    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("Row-lock ordering proof requires PostgreSQL")
    command.upgrade(config, "0010")
    expected = str(uuid4())
    for name in ("org", "other"):
        _insert(
            engine,
            "organizations",
            dict(id=name, name=name, minimum_write_protocol=1, dataset_incarnation=expected),
        )
    settings, application = configured(engine)
    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=3) as executor:
        blocker.execute(text("SELECT id FROM organizations WHERE id='org' FOR UPDATE"))
        futures = [
            executor.submit(
                recover_cutover, settings, organization_id="org", expected_incarnation=expected
            )
            for _ in range(2)
        ]
        try:
            observe_waiters(engine, application, futures, 2)
            independent = executor.submit(
                recover_cutover, settings, organization_id="other", expected_incarnation=expected
            )
            assert independent.result(timeout=5)["changed"] is True
            blocker.commit()
        finally:
            blocker.rollback()
        results, errors = [], []
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except ApiError as failure:
                errors.append(failure.code)
    assert len(results) == 1
    assert errors == ["incarnation_precondition_failed"]
    audits = _snapshot(engine, "identity_audit_events")
    assert len(audits) == 2
    assert sum(row["organization_id"] == "org" for row in audits) == 1


def test_activation_waits_for_transaction_and_refuses_no_committed_history_on_rollback(
    identity_migration_database,
):
    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("Row-lock ordering proof requires PostgreSQL")
    command.upgrade(config, "0010")
    _insert(
        engine,
        "organizations",
        dict(id="org", name="org", minimum_write_protocol=0, dataset_incarnation=str(uuid4())),
    )
    settings, application = configured(engine)
    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=1) as executor:
        blocker.execute(text("UPDATE organizations SET minimum_write_protocol=1 WHERE id='org'"))
        future = executor.submit(activate_cutover, settings, organization_id="org")
        try:
            observe_waiters(engine, application, [future], 1)
            blocker.rollback()
        finally:
            blocker.rollback()
        assert future.result(timeout=10)["changed"] is True
    assert len(_snapshot(engine, "identity_audit_events")) == 1


def test_supported_bootstraps_serialize_empty_installation_predicate(
    identity_migration_database,
    tmp_path,
):
    config, engine = identity_migration_database
    if engine.dialect.name != "postgresql":
        pytest.skip("Advisory-lock bootstrap ordering proof requires PostgreSQL")
    command.upgrade(config, "0010")
    settings, application = configured(engine)
    password = tmp_path / "synthetic-bootstrap-password"
    password.write_text("synthetic-bootstrap-password-only")
    with engine.connect() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        blocker.execute(text("SELECT pg_advisory_xact_lock(1329813328, 1)"))
        futures = [
            executor.submit(
                bootstrap_admin,
                settings,
                organization_name="Synthetic",
                location_name="Fixture",
                username=f"synthetic-{index}",
                display_name="Synthetic",
                password_file=password,
            )
            for index in range(2)
        ]
        try:
            observe_waiters(engine, application, futures, 2)
            blocker.commit()
        finally:
            blocker.rollback()
        results, errors = [], []
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except RuntimeError as failure:
                errors.append(str(failure))
    assert len(results) == 1
    assert errors == ["bootstrap admin requires a fresh installation"]
    for name in ("organizations", "locations", "users"):
        assert len(_snapshot(engine, name)) == 1
    assert _snapshot(engine, "organizations")[0]["minimum_write_protocol"] == 0
