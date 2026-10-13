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
        environment.setenv("OCWP_DATABASE_URL", url.replace("%", "%%"))
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
        """Force both HTTP commands to contend on the same real product lock."""
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
            futures = [executor.submit(self.post, payload) for payload in (first, second)]
            try:
                waiting_pids = self._wait_for_two_lock_waiters(futures)
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

    def _wait_for_two_lock_waiters(self, futures: list[Future[Response]]) -> set[int]:
        deadline = time.monotonic() + 10
        waiting_pids: set[int] = set()
        # Autocommit avoids retaining PostgreSQL's statistics snapshot while
        # polling. Application name isolates these requests from other tests.
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
            while time.monotonic() < deadline:
                waiting_pids = set(
                    observer.scalars(
                        text(
                            "SELECT pid FROM pg_stat_activity "
                            "WHERE application_name = :application_name "
                            "AND state = 'active' AND wait_event_type = 'Lock' "
                            "AND query ILIKE '%products%' "
                            "AND query ILIKE '%FOR UPDATE%'"
                        ),
                        {"application_name": self.application_name},
                    )
                )
                if len(waiting_pids) == 2 or any(future.done() for future in futures):
                    break
                time.sleep(0.02)
        return waiting_pids


@pytest.fixture
def inventory_postgres(inventory_postgres_url: str) -> Iterator[InventoryPostgres]:
    organization_id, location_id, user_id, customer_id, order_id = (new_id() for _ in range(5))
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
