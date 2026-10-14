"""Real PostgreSQL proof for inventory command serialization and atomicity.

Only OCWP_TEST_DATABASE_URL may select the database. Each test owns a unique
organization and removes only its own rows; migrations never reset the schema.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.app import create_app
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.url import normalize_database_url
from cycling_workshop.identity.administration import AdministrationService
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.identity.security import PasswordService
from cycling_workshop.inventory.models import InventoryMovementRecord, ProductRecord
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker


def _safe_postgres_url(raw_url: str) -> str:
    url = normalize_database_url(raw_url)
    parsed = make_url(url)
    if (
        parsed.drivername != "postgresql+psycopg"
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").endswith(("_test", "_e2e"))
        # libpq query parameters such as host/service can override the URL host.
        or parsed.query
    ):
        raise ValueError("inventory integration requires a dedicated local PostgreSQL test URL")
    return url


@pytest.fixture(scope="module")
def inventory_postgres_url() -> str:
    raw_url = os.getenv("OCWP_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("OCWP_TEST_DATABASE_URL not configured; PostgreSQL concurrency unverified")
    url = _safe_postgres_url(raw_url)
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "migrations"))
    config.set_main_option("prepend_sys_path", str(service_root / "src"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    # env.py reads OCWP_DATABASE_URL ahead of Config. Never let an unrelated
    # application URL override the explicitly validated test database.
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("OCWP_DATABASE_URL", url)
        command.upgrade(config, "head")
    return url


@dataclass
class InventoryPostgres:
    app: FastAPI
    engine: Engine
    factory: sessionmaker[Session]
    application_name: str
    organization_id: str
    location_id: str
    other_location_id: str
    user_id: str
    order_id: str
    headers: dict[str, str]

    def product(self) -> str:
        with TestClient(self.app) as client:
            response = client.post(
                "/api/v1/inventory/products",
                headers=self.headers,
                json={
                    "location_id": self.location_id,
                    "sku": f"PG-{new_id()}",
                    "name": "PostgreSQL concurrency test part",
                },
            )
        assert response.status_code == 201, response.text
        return str(response.json()["product_id"])

    def command(
        self,
        product_id: str,
        kind: str,
        quantity: int,
        *,
        reference: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "movement_id": new_id(),
            "product_id": product_id,
            "kind": kind,
            "quantity": quantity,
        }
        if kind != "ADJUST":
            payload["order_id"] = self.order_id
        if reference is not None:
            payload["reference_movement_id"] = reference
        return payload

    def post(self, payload: dict[str, Any]) -> Response:
        # Each caller gets an independent ASGI client and request DB session.
        with TestClient(self.app) as client:
            return client.post("/api/v1/inventory/movements", headers=self.headers, json=payload)

    def record(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.post(payload)
        assert response.status_code == 201, response.text
        return dict(response.json())

    def rows(self, product_id: str) -> list[InventoryMovementRecord]:
        with self.factory() as session:
            return list(
                session.scalars(
                    select(InventoryMovementRecord).where(
                        InventoryMovementRecord.organization_id == self.organization_id,
                        InventoryMovementRecord.product_id == product_id,
                    )
                )
            )

    def assert_stock(self, product_id: str, expected: int) -> None:
        with self.factory() as session:
            actual = session.scalar(
                select(func.coalesce(func.sum(InventoryMovementRecord.quantity), 0)).where(
                    InventoryMovementRecord.organization_id == self.organization_id,
                    InventoryMovementRecord.product_id == product_id,
                )
            )
        assert actual == expected
        with TestClient(self.app) as client:
            response = client.get(
                f"/api/v1/inventory/products/{product_id}/stock", headers=self.headers
            )
        assert response.status_code == 200, response.text
        assert response.json()["available_quantity"] == expected

    def race(self, first: dict[str, Any], second: dict[str, Any]) -> list[Response]:
        """Observe product→blocker and organization→first-writer wait edges."""
        assert first["product_id"] == second["product_id"]
        with self.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
            blocker.scalar(
                select(ProductRecord)
                .where(
                    ProductRecord.id == first["product_id"],
                    ProductRecord.organization_id == self.organization_id,
                )
                .with_for_update()
            )
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            futures = [executor.submit(self.post, payload) for payload in (first, second)]
            try:
                waiting_pids = self._wait_for_two_lock_waiters(futures, blocker_pid)
            finally:
                # Always unblock requests, including on a test assertion/error.
                blocker.rollback()
            responses = [future.result(timeout=20) for future in futures]
        assert len(waiting_pids) == 2, (
            "Both HTTP commands must contend in separate PostgreSQL sessions; "
            f"observed {len(waiting_pids)} lock waiters, "
            f"responses={[(r.status_code, r.text) for r in responses]}"
        )
        return responses

    def _wait_for_two_lock_waiters(
        self, futures: list[Future[Response]], blocker_pid: int
    ) -> set[int]:
        deadline = time.monotonic() + 10
        waiting_pids: set[int] = set()
        # Autocommit avoids retaining PostgreSQL's statistics snapshot while
        # polling. Application name isolates these requests from other tests.
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            while time.monotonic() < deadline:
                waiters = list(
                    observer.execute(
                        text(
                            "SELECT pid, query, pg_blocking_pids(pid) FROM pg_stat_activity "
                            "WHERE application_name = :application_name "
                            "AND state = 'active' AND wait_event_type = 'Lock' "
                            "AND query ILIKE '%FOR UPDATE%'"
                        ),
                        {"application_name": self.application_name},
                    )
                )
                product = [row for row in waiters if "FROM products" in row.query]
                organization = [row for row in waiters if "FROM organizations" in row.query]
                if (
                    len(product) == len(organization) == 1
                    and blocker_pid in product[0].pg_blocking_pids
                    and product[0].pid in organization[0].pg_blocking_pids
                ):
                    waiting_pids = {row.pid for row in waiters}
                    break
                if any(future.done() for future in futures):
                    break
                time.sleep(0.02)
        return waiting_pids

    def wait_for_blocked_writer(self, future: Future[Any], blocker_pid: int) -> int:
        """Observe the actual lock dependency, without assuming its wait site."""
        deadline = time.monotonic() + 10
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            while time.monotonic() < deadline:
                pid = observer.scalar(
                    text(
                        "SELECT pid FROM pg_stat_activity "
                        "WHERE application_name = :name AND state = 'active' "
                        "AND wait_event_type = 'Lock' "
                        "AND :blocker = ANY(pg_blocking_pids(pid))"
                    ),
                    {"name": self.application_name, "blocker": blocker_pid},
                )
                if pid is not None:
                    assert not future.done()
                    return int(pid)
                if future.done():
                    future.result()
                    pytest.fail("HTTP writer completed before a real lock wait was observed")
                time.sleep(0.02)
        pytest.fail("No PostgreSQL writer blocked by the expected transaction")


@pytest.fixture
def inventory_postgres(inventory_postgres_url: str) -> Iterator[InventoryPostgres]:
    organization_id, location_id, user_id, customer_id, order_id = (new_id() for _ in range(5))
    other_location_id = new_id()
    application_name = f"ocwp-inventory-{organization_id}"
    engine = create_engine(
        inventory_postgres_url,
        pool_size=6,
        max_overflow=0,
        connect_args={
            "application_name": application_name,
            "connect_timeout": 5,
            "options": "-c lock_timeout=15000 -c statement_timeout=20000",
        },
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    password = "inventory concurrency test password"
    try:
        with factory() as session:
            session.add(OrganizationRecord(id=organization_id, name="Inventory integration"))
            session.flush()
            session.add(
                LocationRecord(id=location_id, organization_id=organization_id, name="Test")
            )
            session.add(
                LocationRecord(id=other_location_id, organization_id=organization_id, name="Other")
            )
            session.flush()
            session.add(
                UserRecord(
                    id=user_id,
                    organization_id=organization_id,
                    location_id=location_id,
                    username=f"inventory-{user_id}",
                    display_name="Inventory integration",
                    password_hash=PasswordService().hash(password),
                    capabilities=["inventory.read", "inventory.write"],
                    is_active=True,
                )
            )
            session.add(
                CustomerRecord(
                    id=customer_id,
                    organization_id=organization_id,
                    location_id=location_id,
                    display_name="Inventory test customer",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            session.add(
                ServiceOrderRecord(
                    id=order_id,
                    organization_id=organization_id,
                    location_id=location_id,
                    customer_id=customer_id,
                    state="INTAKE",
                    reported_problem="Inventory concurrency verification",
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        app = create_app(
            settings=Settings(
                environment="test",
                database_url=inventory_postgres_url,
                log_level="WARNING",
                auth_secret="inventory-postgres-test-secret-at-least-32-characters",
            ),
            session_factory=factory,
        )
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "organization_id": organization_id,
                    "username": f"inventory-{user_id}",
                    "password": password,
                },
            )
        assert login.status_code == 200, login.text
        yield InventoryPostgres(
            app=app,
            engine=engine,
            factory=factory,
            application_name=application_name,
            organization_id=organization_id,
            location_id=location_id,
            other_location_id=other_location_id,
            user_id=user_id,
            order_id=order_id,
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
    finally:
        try:
            with factory.begin() as session:
                # This random organization belongs exclusively to this fixture.
                # Delete dependent rows first, respecting PostgreSQL RESTRICT FKs.
                for record in (
                    InventoryMovementRecord,
                    ProductRecord,
                    ServiceOrderEventRecord,
                    ServiceOrderRecord,
                    CustomerRecord,
                    UserRecord,
                    LocationRecord,
                ):
                    session.execute(delete(record).where(record.organization_id == organization_id))
                session.execute(
                    delete(OrganizationRecord).where(OrganizationRecord.id == organization_id)
                )
        finally:
            engine.dispose()


def test_concurrent_reservations_cannot_oversell(inventory_postgres: InventoryPostgres) -> None:
    db = inventory_postgres
    product_id = db.product()
    initial = db.record(db.command(product_id, "ADJUST", 5))
    commands = [db.command(product_id, "RESERVE", 4) for _ in range(2)]

    responses = db.race(*commands)

    assert sorted(response.status_code for response in responses) == [201, 409]
    winner = next(response.json() for response in responses if response.status_code == 201)
    loser = commands[responses.index(next(r for r in responses if r.status_code == 409))]
    rows = db.rows(product_id)
    assert {row.movement_id for row in rows} == {initial["movement_id"], winner["movement_id"]}
    assert loser["movement_id"] not in {row.movement_id for row in rows}
    assert sorted((row.kind, row.quantity) for row in rows) == [("ADJUST", 5), ("RESERVE", -4)]
    db.assert_stock(product_id, 1)


def test_concurrent_release_and_consume_finalize_once(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product_id = db.product()
    db.record(db.command(product_id, "ADJUST", 5))
    reservation = db.record(db.command(product_id, "RESERVE", 4))
    commands = [
        db.command(product_id, kind, 4, reference=reservation["movement_id"])
        for kind in ("RELEASE", "CONSUME")
    ]

    responses = db.race(*commands)

    assert sorted(response.status_code for response in responses) == [201, 409]
    winner = next(response.json() for response in responses if response.status_code == 201)
    rows = db.rows(product_id)
    finalizations = [row for row in rows if row.kind in {"RELEASE", "CONSUME"}]
    assert len(finalizations) == 1
    assert finalizations[0].movement_id == winner["movement_id"]
    assert finalizations[0].reference_movement_id == reservation["movement_id"]
    assert finalizations[0].quantity == 4
    outflows = [row for row in rows if row.kind == "ADJUST" and row.quantity < 0]
    if winner["kind"] == "CONSUME":
        assert len(rows) == 4
        assert len(outflows) == 1
        assert outflows[0].quantity == -4
        db.assert_stock(product_id, 1)
    else:
        assert len(rows) == 3
        assert not outflows
        db.assert_stock(product_id, 5)
    # Retrying the losing command cannot add a delayed partial finalization.
    loser = next(payload for payload in commands if payload["movement_id"] != winner["movement_id"])
    assert db.post(loser).status_code == 409
    assert {row.movement_id for row in db.rows(product_id)} == {row.movement_id for row in rows}


@pytest.mark.parametrize("kind", ["RESERVE", "CONSUME"])
def test_concurrent_identical_command_has_one_effect(
    inventory_postgres: InventoryPostgres, kind: str
) -> None:
    db = inventory_postgres
    product_id = db.product()
    db.record(db.command(product_id, "ADJUST", 5))
    reservation = db.record(db.command(product_id, "RESERVE", 4)) if kind == "CONSUME" else None
    payload = db.command(
        product_id, kind, 4, reference=reservation["movement_id"] if reservation else None
    )
    payload["note"] = "Same command delivered by two clients"

    responses = db.race(payload, dict(payload))

    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json() == responses[1].json()
    assert responses[0].json()["movement_id"] == payload["movement_id"]
    rows = db.rows(product_id)
    assert sum(row.movement_id == payload["movement_id"] for row in rows) == 1
    assert len(rows) == (4 if kind == "CONSUME" else 2)
    if kind == "CONSUME":
        assert sorted((row.kind, row.quantity) for row in rows) == [
            ("ADJUST", -4),
            ("ADJUST", 5),
            ("CONSUME", 4),
            ("RESERVE", -4),
        ]
    db.assert_stock(product_id, 1)
    assert db.post(payload).json() == responses[0].json()
    assert len(db.rows(product_id)) == len(rows)


def test_concurrent_reused_id_with_changed_command_conflicts(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product_id = db.product()
    db.record(db.command(product_id, "ADJUST", 10))
    payload = db.command(product_id, "RESERVE", 2)
    altered = {**payload, "quantity": 3}

    responses = db.race(payload, altered)

    assert sorted(response.status_code for response in responses) == [201, 409]
    winner = next(response.json() for response in responses if response.status_code == 201)
    rows = db.rows(product_id)
    assert len(rows) == 2
    reservations = [row for row in rows if row.kind == "RESERVE"]
    assert len(reservations) == 1
    assert reservations[0].movement_id == payload["movement_id"]
    assert reservations[0].quantity == winner["quantity"]
    assert winner["quantity"] in {-2, -3}
    db.assert_stock(product_id, 10 + winner["quantity"])


@pytest.mark.parametrize("kind", ["product", "movement"])
@pytest.mark.parametrize(
    "change", ["session", "inactive", "grants", "location", "narrow_scope", "rollback"]
)
def test_inventory_rechecks_authority_after_observed_admin_wait(
    inventory_postgres: InventoryPostgres, kind: str, change: str
) -> None:
    db = inventory_postgres
    product_id = db.product()
    candidate_id = new_id()
    if change == "narrow_scope":
        with db.factory.begin() as session:
            actor = session.get(UserRecord, db.user_id)
            assert actor is not None
            actor.location_id = None
        token = db.app.state.session_tokens.issue(
            Principal(db.user_id, db.organization_id, None, frozenset({"inventory.write"}))
        )
        db.headers = {"Authorization": f"Bearer {token}"}

    def request() -> Response:
        if kind == "movement":
            return db.post({**db.command(product_id, "ADJUST", 3), "movement_id": candidate_id})
        with TestClient(db.app) as client:
            return client.post(
                "/api/v1/inventory/products",
                headers=db.headers,
                json={
                    "product_id": candidate_id,
                    "location_id": db.location_id,
                    "sku": f"WAIT-{candidate_id}",
                    "name": "Synthetic wait regression",
                },
            )

    with db.factory() as admin, ThreadPoolExecutor(max_workers=1) as executor:
        # Same supported lock order as administration. The old committed actor
        # remains visible to the HTTP dependency until this transaction commits.
        admin.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == db.organization_id)
            .with_for_update()
        )
        actor = admin.scalar(
            select(UserRecord).where(UserRecord.id == db.user_id).with_for_update()
        )
        assert actor is not None
        admin.scalar(select(ProductRecord).where(ProductRecord.id == product_id).with_for_update())
        blocker_pid = admin.scalar(text("SELECT pg_backend_pid()"))
        future = executor.submit(request)
        try:
            # Before the fix: movement/product-lock or product/INSERT FK wait.
            # After the fix: organization-lock wait. Both prove the dependency
            # already accepted the previous committed account state.
            db.wait_for_blocked_writer(future, blocker_pid)
            if change in {"session", "rollback"}:
                actor.session_version += 1
            elif change == "inactive":
                actor.is_active = False
            elif change == "grants":
                actor.capabilities = ["inventory.read"]
            else:
                actor.location_id = db.other_location_id
            if change == "rollback":
                admin.flush()
                admin.rollback()
            else:
                admin.commit()
        finally:
            admin.rollback()
        response = future.result(timeout=20)

    expected = 201 if change == "rollback" else 403 if change in {"grants", "narrow_scope"} else 401
    assert response.status_code == expected, response.text
    with db.factory() as session:
        assert (session.get(ProductRecord, candidate_id) is not None) == (
            kind == "product" and change == "rollback"
        )
        assert (session.get(InventoryMovementRecord, candidate_id) is not None) == (
            kind == "movement" and change == "rollback"
        )
    rows = db.rows(product_id)
    assert [(row.movement_id, row.quantity) for row in rows] == (
        [(candidate_id, 3)] if kind == "movement" and change == "rollback" else []
    )


def test_inventory_writer_commits_before_later_revocation(
    inventory_postgres: InventoryPostgres,
) -> None:
    db = inventory_postgres
    product_id = db.product()
    payload = db.command(product_id, "ADJUST", 3)

    def revoke() -> None:
        with db.factory.begin() as session:
            actor, _ = AdministrationService.for_fixtures(session).lock_actor(
                Principal(
                    db.user_id,
                    db.organization_id,
                    db.location_id,
                    frozenset({"inventory.write"}),
                )
            )
            actor.session_version += 1

    with db.factory() as blocker, ThreadPoolExecutor(max_workers=2) as executor:
        blocker.scalar(
            select(ProductRecord).where(ProductRecord.id == product_id).with_for_update()
        )
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        writer = executor.submit(db.post, payload)
        try:
            writer_pid = db.wait_for_blocked_writer(writer, blocker_pid)
            # Writer already holds organization→actor and is now on product.
            revocation = executor.submit(revoke)
            db.wait_for_blocked_writer(revocation, writer_pid)
        finally:
            blocker.rollback()
        response = writer.result(timeout=20)
        revocation.result(timeout=20)
    assert response.status_code == 201, response.text
    assert [(row.movement_id, row.quantity) for row in db.rows(product_id)] == [
        (payload["movement_id"], 3)
    ]
    # Exact replay remains an authenticated action and is now refused.
    assert db.post(payload).status_code == 401
    assert len(db.rows(product_id)) == 1


@pytest.fixture
def other_inventory_postgres(inventory_postgres_url: str) -> Iterator[InventoryPostgres]:
    yield from inventory_postgres.__wrapped__(inventory_postgres_url)


def test_inventory_authority_barrier_does_not_block_another_organization(
    inventory_postgres: InventoryPostgres, other_inventory_postgres: InventoryPostgres
) -> None:
    blocked, independent = inventory_postgres, other_inventory_postgres
    product_id, independent_product = blocked.product(), independent.product()
    with blocked.factory() as admin, ThreadPoolExecutor(max_workers=1) as executor:
        admin.scalar(
            select(OrganizationRecord)
            .where(OrganizationRecord.id == blocked.organization_id)
            .with_for_update()
        )
        blocker_pid = admin.scalar(text("SELECT pg_backend_pid()"))
        waiting = executor.submit(blocked.post, blocked.command(product_id, "ADJUST", 2))
        try:
            blocked.wait_for_blocked_writer(waiting, blocker_pid)
            response = independent.post(independent.command(independent_product, "ADJUST", 4))
            assert response.status_code == 201, response.text
            assert not waiting.done()
        finally:
            admin.rollback()
        assert waiting.result(timeout=20).status_code == 201
    blocked.assert_stock(product_id, 2)
    independent.assert_stock(independent_product, 4)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://ocwp@db.example/ocwp_test",
        "postgresql://ocwp@127.0.0.1/ocwp",
        "postgresql://ocwp@localhost/ocwp_test_backup",
        "postgresql://ocwp@127.0.0.1/ocwp_test?host=db.example",
        "postgresql://ocwp@localhost/ocwp_test?service=production",
        "sqlite:///ocwp_test",
    ],
)
def test_inventory_postgres_fixture_rejects_unsafe_database_urls(url: str) -> None:
    with pytest.raises(ValueError, match="dedicated local PostgreSQL test URL"):
        _safe_postgres_url(url)


def test_fixture_preserves_percent_encoded_url_before_any_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy

    class StopBeforeConnection(Exception):
        pass

    captured: list[str] = []
    synthetic_url = "postgresql+psycopg://ocwp:p%40ss%25word@127.0.0.1/ocwp_test"
    monkeypatch.setenv("OCWP_TEST_DATABASE_URL", synthetic_url)

    def capture_config(configuration: dict[str, Any], **kwargs: Any) -> None:
        captured.append(configuration["sqlalchemy.url"])
        raise StopBeforeConnection

    monkeypatch.setattr(sqlalchemy, "engine_from_config", capture_config)
    with pytest.raises(StopBeforeConnection):
        inventory_postgres_url.__wrapped__()
    assert captured == [synthetic_url]
    assert make_url(captured[0]).password == "p@ss%word"
