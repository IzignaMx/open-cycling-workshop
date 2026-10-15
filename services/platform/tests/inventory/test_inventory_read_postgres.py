"""Actual PostgreSQL18 budgets, post-wait authority, cleanup and measured plans.

Uses the existing guarded local dedicated-test fixture; never substitutes SQLite.
Unavailable PostgreSQL is an explicit skip, not concurrency/timeout evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.inventory import read_guard, router
from cycling_workshop.inventory.cursor import InventoryCursor, canonical_timestamp
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord
from cycling_workshop.inventory.read_repository import movement_statement
from cycling_workshop.inventory.repository import SqlAlchemyInventoryRepository
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import event, func, insert, select, text

from services.platform.tests.inventory.test_inventory_postgres import InventoryPostgres
from services.platform.tests.inventory.test_inventory_postgres import (
    inventory_postgres as inventory_postgres,
)
from services.platform.tests.inventory.test_inventory_postgres import (
    inventory_postgres_url as inventory_postgres_url,
)

ROUTES = ("catalog", "stock", "movements")
WAIT_CHANGES = ("revoke", "deactivate", "scope", "grants", "incarnation", "expiry")
EXPECTED_CASES = {
    *(
        f"wait:{route}:{barrier}:{change}"
        for route in ROUTES
        for barrier in ("organization", "actor")
        for change in WAIT_CHANGES
        if not (barrier == "actor" and change == "incarnation")
    ),
    *(f"read-first:{route}" for route in ROUTES),
    "budget-order",
    "lock:organization",
    "lock:actor",
    "statement",
    "transaction",
    "competing",
    "plans",
}
_EVIDENCE: dict = {}


def evidence_directory() -> Path:
    return Path(os.getenv("OCWP_INVENTORY_READ_EVIDENCE_DIR", "artifacts/inventory-read"))


def write_evidence() -> None:
    path = evidence_directory() / "backend-postgres-evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_EVIDENCE, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@pytest.fixture(scope="module", autouse=True)
def postgres_evidence_run():
    root = Path(__file__).resolve().parents[4]
    sources = [
        "services/platform/src/cycling_workshop/inventory/read_guard.py",
        "services/platform/src/cycling_workshop/inventory/read_repository.py",
        "services/platform/src/cycling_workshop/inventory/cursor.py",
        "services/platform/src/cycling_workshop/inventory/router.py",
        "services/platform/tests/inventory/test_inventory_read_postgres.py",
    ]
    _EVIDENCE.clear()
    _EVIDENCE.update(
        {
            "schema": 1,
            "status": "incomplete",
            "started_at": datetime.now(UTC).isoformat(),
            "expected_cases": sorted(EXPECTED_CASES),
            "cases": {},
            "source_sha256": {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources
            },
            "scope": "disposable synthetic PostgreSQL test data; no deployment qualification",
        }
    )
    write_evidence()
    yield
    _EVIDENCE["status"] = (
        "cases_complete" if set(_EVIDENCE["cases"]) == EXPECTED_CASES else "incomplete"
    )
    _EVIDENCE["finished_at"] = datetime.now(UTC).isoformat()
    write_evidence()


def record_case(name: str, **values: object) -> None:
    assert name in EXPECTED_CASES
    assert name not in _EVIDENCE["cases"]
    _EVIDENCE["cases"][name] = values
    write_evidence()


def get(db: InventoryPostgres, product: str, route: str = "movements"):
    path = (
        f"/api/v1/inventory/products?location_id={db.location_id}"
        if route == "catalog"
        else f"/api/v1/inventory/products/{product}/{route}"
    )
    with TestClient(db.app, raise_server_exceptions=False) as client:
        return client.get(path, headers=db.headers)


def lock(db: InventoryPostgres, blocker, barrier: str):
    model, identifier = (
        (OrganizationRecord, db.organization_id)
        if barrier == "organization"
        else (UserRecord, db.user_id)
    )
    assert blocker.scalar(select(model).where(model.id == identifier).with_for_update()) is not None
    return blocker.scalar(text("SELECT pg_backend_pid()"))


def assert_released(db: InventoryPostgres, product: str) -> float:
    # A new public command and then revocation must acquire the same barriers
    # immediately. This also detects leaked failed transactions/pool poisoning.
    started = time.monotonic()
    assert db.post(db.command(product, "ADJUST", 1)).status_code == 201
    with db.factory() as session:
        session.execute(text("SET LOCAL lock_timeout = '500ms'"))
        lock(db, session, "organization")
        user = session.scalar(
            select(UserRecord).where(UserRecord.id == db.user_id).with_for_update()
        )
        assert user is not None
        user.session_version += 1
        session.commit()
    elapsed = time.monotonic() - started
    assert elapsed < 2
    return elapsed


@pytest.mark.parametrize("route", ["catalog", "stock", "movements"])
@pytest.mark.parametrize(
    "barrier,change,status",
    [
        (barrier, change, status)
        for barrier in ("organization", "actor")
        for change, status in [
            ("revoke", 401),
            ("deactivate", 401),
            ("scope", 401),
            ("grants", 403),
            ("incarnation", 401),
            ("expiry", 401),
        ]
        if not (barrier == "actor" and change == "incarnation")
    ],
)
def test_waited_read_refetches_current_authority(
    inventory_postgres: InventoryPostgres,
    route: str,
    barrier: str,
    change: str,
    status: int,
) -> None:
    db = inventory_postgres
    product = db.product()
    now = [datetime(2026, 10, 15, tzinfo=UTC)]
    tokens = SessionTokenService(
        secret="synthetic-read-race-clock-secret-long-enough",
        ttl=timedelta(seconds=60),
        clock=lambda: now[0],
    )
    db.app.state.session_tokens = tokens
    with db.factory() as session:
        organization = session.get(OrganizationRecord, db.organization_id)
        assert organization is not None
        incarnation = organization.dataset_incarnation
    db.headers = {
        "Authorization": "Bearer "
        + tokens.issue(
            Principal(
                db.user_id,
                db.organization_id,
                db.location_id,
                frozenset({"inventory.read", "inventory.write"}),
                dataset_incarnation=incarnation,
            )
        )
    }
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        pid = lock(db, blocker, barrier)
        started = time.monotonic()
        future = pool.submit(get, db, product, route)
        try:
            db.wait_for_blocked_writer(future, pid)
            observed_wait_seconds = time.monotonic() - started
            if change == "incarnation":
                organization = blocker.get(OrganizationRecord, db.organization_id)
                assert organization is not None
                organization.dataset_incarnation = str(uuid4())
            elif change == "expiry":
                now[0] += timedelta(seconds=60)
            else:
                actor = blocker.get(UserRecord, db.user_id)
                assert actor is not None
                if change == "revoke":
                    actor.session_version += 1
                elif change == "deactivate":
                    actor.is_active = False
                elif change == "scope":
                    actor.location_id = db.other_location_id
                else:
                    actor.capabilities = ["inventory.write"]
            blocker.commit()
        finally:
            blocker.rollback()
        response = future.result(timeout=10)
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert db.rows(product) == []
    record_case(
        f"wait:{route}:{barrier}:{change}",
        observed_lock_wait=True,
        wait_observed_seconds=observed_wait_seconds,
        response_status=response.status_code,
        inventory_unchanged=True,
    )


@pytest.mark.parametrize("route", ["catalog", "stock", "movements"])
def test_read_first_materializes_before_waiting_revocation(
    inventory_postgres: InventoryPostgres,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    db = inventory_postgres
    product = db.product()
    reached, release = Event(), Event()
    reader_pid = []
    owner = router if route == "movements" else SqlAlchemyInventoryRepository
    name = {
        "catalog": "list_products",
        "stock": "available_quantity",
        "movements": "read_movement_page",
    }[route]
    original = getattr(owner, name)

    def pause(*args, **kwargs):
        session = args[0] if route == "movements" else args[0]._session
        result = original(*args, **kwargs)
        reader_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
        reached.set()
        assert release.wait(1.5), "Revoker observation must fit the 2s read lock budget"
        return result

    monkeypatch.setattr(owner, name, pause)

    def revoke():
        with db.factory() as session:
            lock(db, session, "organization")
            actor = session.scalar(
                select(UserRecord).where(UserRecord.id == db.user_id).with_for_update()
            )
            assert actor is not None
            actor.session_version += 1
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(get, db, product, route)
        assert reached.wait(5)
        revoker = pool.submit(revoke)
        try:
            db.wait_for_blocked_writer(revoker, reader_pid[0])
        finally:
            release.set()
        assert reader.result(timeout=5).status_code == 200
        revoker.result(timeout=5)
    assert get(db, product, route).status_code == 401
    record_case(
        f"read-first:{route}",
        observed_revoker_lock_wait=True,
        read_response_status=200,
        subsequent_response_status=401,
    )


def test_inventory_budgets_precede_every_org_actor_statement(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product = db.product()
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", capture)
    try:
        response = get(db, product)
    finally:
        event.remove(db.engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert statements[:3] == [
        "SET LOCAL transaction_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
        "SET LOCAL statement_timeout = '5s'",
    ]
    assert "FROM organizations" in statements[3] and "FOR UPDATE" in statements[3]
    assert "FROM users" in statements[4] and "FOR UPDATE" in statements[4]
    assert sum("FROM organizations" in sql for sql in statements) == 1
    assert sum("FROM users" in sql for sql in statements) == 1
    with db.factory() as session:
        assert session.scalar(text("SHOW lock_timeout")) == "15s"
        assert session.scalar(text("SHOW statement_timeout")) == "20s"
        assert session.scalar(text("SHOW transaction_timeout")) == "0"
    record_case(
        "budget-order",
        settings_precede_authority=True,
        authority_sessions=1,
        lock_timeout_seconds=2,
        statement_timeout_seconds=5,
        transaction_timeout_seconds=8,
        settings_restored=True,
    )


@pytest.mark.parametrize("barrier", ["organization", "actor"])
def test_two_second_lock_budget_returns_safe_503_and_releases_every_lock(
    inventory_postgres: InventoryPostgres,
    barrier: str,
) -> None:
    db = inventory_postgres
    product = db.product()
    with db.factory() as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        pid = lock(db, blocker, barrier)
        started = time.monotonic()
        future = pool.submit(get, db, product)
        try:
            db.wait_for_blocked_writer(future, pid)
            response = future.result(timeout=7)
        finally:
            blocker.rollback()
    elapsed = time.monotonic() - started
    assert 1.7 <= elapsed < 5, elapsed
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "inventory_read_unavailable"
    assert response.headers["cache-control"] == "no-store"
    assert db.rows(product) == []
    cleanup_seconds = assert_released(db, product)
    record_case(
        f"lock:{barrier}",
        observed_lock_wait=True,
        elapsed_seconds=elapsed,
        response_status=503,
        code="inventory_read_unavailable",
        inventory_unchanged=True,
        subsequent_writer_status=201,
        revocation_committed=True,
        cleanup_seconds=cleanup_seconds,
    )


@pytest.mark.parametrize(
    "budget,seconds,lower,upper", [("statement", [6], 4.5, 8), ("transaction", [3, 3, 3], 7.5, 11)]
)
def test_database_statement_and_total_transaction_budgets_cleanup(
    inventory_postgres: InventoryPostgres,
    monkeypatch: pytest.MonkeyPatch,
    budget: str,
    seconds: list[int],
    lower: float,
    upper: float,
) -> None:
    db = inventory_postgres
    product = db.product()
    completed = []

    def slow_page(session, **_kwargs):
        for delay in seconds:
            session.execute(text("SELECT pg_sleep(:delay)"), {"delay": delay})
            completed.append(delay)
        pytest.fail("Database must terminate over-budget query/transaction")

    monkeypatch.setattr(router, "read_movement_page", slow_page)
    started = time.monotonic()
    response = get(db, product)
    elapsed = time.monotonic() - started
    assert lower <= elapsed < upper, (budget, elapsed)
    assert completed == ([] if budget == "statement" else [3, 3])
    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == "inventory_read_unavailable"
    assert response.headers["cache-control"] == "no-store"
    assert "pg_sleep" not in response.text
    assert db.rows(product) == []
    cleanup_seconds = assert_released(db, product)
    record_case(
        budget,
        elapsed_seconds=elapsed,
        individually_completed_sleep_seconds=completed,
        response_status=503,
        code="inventory_read_unavailable",
        inventory_unchanged=True,
        subsequent_writer_status=201,
        revocation_committed=True,
        cleanup_seconds=cleanup_seconds,
    )


def test_competing_reads_and_writes_finish_without_deadlock(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product = db.product()
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [
            pool.submit(get, db, product, route) for route in ["catalog", "stock", "movements"] * 2
        ]
        writers = [pool.submit(db.post, db.command(product, "ADJUST", 1)) for _ in range(3)]
        assert all(future.result(timeout=10).status_code == 200 for future in futures)
        assert all(future.result(timeout=10).status_code == 201 for future in writers)
    db.assert_stock(product, 3)
    record_case(
        "competing",
        reads=6,
        writes=3,
        reads_status=200,
        writes_status=201,
        final_available_quantity=3,
        deadlock=False,
    )


def test_large_ledger_and_high_offset_plans_fit_unchanged_budgets(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product = db.product()
    now = datetime(2026, 10, 15, tzinfo=UTC)
    # Representative bounded qualification fixture: 20k catalog / 100k ledger.
    # Existing schema/indexes only. No test or production index is introduced.
    with db.factory() as session:
        for start in range(0, 20000, 1000):
            session.execute(
                insert(ProductRecord),
                [
                    {
                        "id": new_id(),
                        "organization_id": db.organization_id,
                        "location_id": db.location_id,
                        "sku": f"EXPLAIN-{n:06}",
                        "name": f"Part {n:06}",
                        "unit": "piece",
                        "created_at": now,
                        "updated_at": now,
                        "version": 1,
                    }
                    for n in range(start, start + 1000)
                ],
            )
        for start in range(0, 100000, 1000):
            session.execute(
                insert(InventoryMovementRecord),
                [
                    {
                        "movement_id": new_id(),
                        "product_id": product,
                        "organization_id": db.organization_id,
                        "location_id": db.location_id,
                        "kind": "ADJUST",
                        "quantity": 1,
                        "actor_id": db.user_id,
                        "occurred_at": now + timedelta(microseconds=n),
                    }
                    for n in range(start, start + 1000)
                ],
            )
        session.commit()
    cursor = InventoryCursor(
        db.organization_id,
        db.location_id,
        product,
        canonical_timestamp(now + timedelta(microseconds=50000)),
        "middle",
    )
    catalog = (
        select(ProductRecord)
        .where(
            ProductRecord.organization_id == db.organization_id,
            ProductRecord.location_id == db.location_id,
        )
        .order_by(ProductRecord.name, ProductRecord.id)
        .limit(50)
        .offset(19950)
    )
    stock = select(func.sum(InventoryMovementRecord.quantity)).where(
        InventoryMovementRecord.organization_id == db.organization_id,
        InventoryMovementRecord.location_id == db.location_id,
        InventoryMovementRecord.product_id == product,
    )
    statements = {"catalog_offset19950": catalog, "stock_100000": stock}
    for label, before in [("history_newest", None), ("history_middle", cursor)]:
        statements[label] = movement_statement(
            organization_id=db.organization_id,
            location_id=db.location_id,
            product_id=product,
            limit=50,
            before=before,
            dialect="postgresql",
        )
    plans = {}
    for label, statement in statements.items():
        with db.factory() as session:
            read_guard.set_read_budgets(session)
            sql = str(
                statement.compile(dialect=db.engine.dialect, compile_kwargs={"literal_binds": True})
            )
            result = session.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
            assert result and result[0]["Execution Time"] < 5000
            plans[label] = result
            session.rollback()
    path = evidence_directory() / "backend-postgres-explain.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Plans expose predicate literals. Replace every synthetic UUID, retaining
    # actual plan structure, buffers, counts and measured times without IDs.
    safe_json = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<synthetic-id>",
        json.dumps({"products": 20001, "movements": 100000, "plans": plans}, indent=2),
    )
    path.write_text(safe_json + "\n", encoding="utf-8")
    record_case(
        "plans",
        products=20001,
        movements=100000,
        execution_milliseconds={
            label: result[0]["Execution Time"] for label, result in plans.items()
        },
        explain_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        schema_or_index_changes=False,
        statement_budget_milliseconds=5000,
    )
