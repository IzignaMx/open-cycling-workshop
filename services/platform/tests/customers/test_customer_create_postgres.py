"""Real PostgreSQL workshop-ID collisions; only owned synthetic tenants are removed."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from cycling_workshop.app import create_app
from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(scope="module")
def customer_postgres_url() -> str:
    from cycling_workshop.db.url import normalize_database_url

    from scripts.e2e.prepare_e2e_database import validate_e2e_database_url

    raw = os.getenv("OCWP_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("OCWP_TEST_DATABASE_URL absent; customer PostgreSQL concurrency unverified")
    validate_e2e_database_url(raw)
    url = normalize_database_url(raw)
    service = Path(__file__).resolve().parents[2]
    config = Config(str(service / "alembic.ini"))
    config.set_main_option("script_location", str(service / "migrations"))
    config.set_main_option("prepend_sys_path", str(service / "src"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("OCWP_DATABASE_URL", url)
        command.upgrade(config, "head")
    return url


@dataclass
class CustomerPostgres:
    app: FastAPI
    engine: Engine
    factory: sessionmaker[Session]
    organizations: tuple[str, str]
    locations: tuple[str, str]
    headers: tuple[dict[str, str], dict[str, str]]
    application_name: str

    def create(self, customer_id: str, *, tenant: int = 0, name: str = "Synthetic") -> Response:
        with TestClient(self.app, raise_server_exceptions=False) as client:
            return client.post(
                "/api/v1/customers",
                headers=self.headers[tenant],
                json={
                    "customer_id": customer_id,
                    "location_id": self.locations[tenant],
                    "display_name": name,
                },
            )

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self.factory() as session:
            return {
                model.__tablename__: [
                    dict(row)
                    for row in session.execute(
                        select(model.__table__)
                        .where(model.organization_id.in_(self.organizations))
                        .order_by(*model.__table__.primary_key.columns)
                    ).mappings()
                ]
                for model in (
                    CustomerRecord,
                    BicycleRecord,
                    ServiceOrderRecord,
                    ServiceOrderEventRecord,
                    ChangeRecord,
                    OutboxRecord,
                    MutationReceiptRecord,
                )
            }

    def associated_create(
        self, kind: str, entity_id: str, customer_id: str, *, tenant: int = 0
    ) -> Response:
        fields = (
            {"bicycle_id": entity_id, "brand": "Synthetic bicycle"}
            if kind == "bicycles"
            else {"order_id": entity_id, "reported_problem": "Synthetic repair"}
        )
        with TestClient(self.app, raise_server_exceptions=False) as client:
            return client.post(
                f"/api/v1/{kind}",
                headers=self.headers[tenant],
                json={
                    **fields,
                    "customer_id": customer_id,
                    "location_id": self.locations[tenant],
                },
            )


@pytest.fixture
def customer_pg(customer_postgres_url: str) -> Iterator[CustomerPostgres]:
    organizations = (new_id(), new_id())
    locations = (new_id(), new_id())
    users = (new_id(), new_id())
    application_name = f"ocwp-customer-{organizations[0]}"
    engine = create_engine(
        customer_postgres_url,
        pool_size=5,
        max_overflow=0,
        connect_args={
            "application_name": application_name,
            "connect_timeout": 5,
            "options": "-c lock_timeout=15000 -c statement_timeout=20000",
        },
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    capabilities = frozenset(
        {
            "customers.read",
            "customers.write",
            "bicycles.read",
            "bicycles.write",
            "orders.read",
            "orders.write",
        }
    )
    try:
        with factory.begin() as session:
            for organization in organizations:
                session.add(OrganizationRecord(id=organization, name="Synthetic collision test"))
            session.flush()
            for organization, location in zip(organizations, locations, strict=True):
                session.add(LocationRecord(id=location, organization_id=organization, name="Test"))
            session.flush()
            for organization, location, user in zip(organizations, locations, users, strict=True):
                session.add(
                    UserRecord(
                        id=user,
                        organization_id=organization,
                        location_id=location,
                        username=f"synthetic-{user}",
                        display_name="Synthetic actor",
                        password_hash="unused-token-fixture",
                        capabilities=sorted(capabilities),
                        is_active=True,
                        session_version=1,
                    )
                )
        app = create_app(
            settings=Settings(
                environment="test",
                database_url=customer_postgres_url,
                log_level="WARNING",
                auth_secret="synthetic-customer-collision-secret-at-least-32-characters",
            ),
            session_factory=factory,
        )
        headers = tuple(
            {
                "Authorization": "Bearer "
                + app.state.session_tokens.issue(
                    Principal(user, organization, location, capabilities)
                )
            }
            for organization, location, user in zip(organizations, locations, users, strict=True)
        )
        yield CustomerPostgres(
            app,
            engine,
            factory,
            organizations,
            locations,
            (headers[0], headers[1]),
            application_name,
        )
    finally:
        with factory.begin() as session:
            for model in (
                OutboxRecord,
                ChangeRecord,
                MutationReceiptRecord,
                ServiceOrderEventRecord,
                ServiceOrderRecord,
                BicycleRecord,
                CustomerRecord,
                UserRecord,
                LocationRecord,
            ):
                session.execute(delete(model).where(model.organization_id.in_(organizations)))
            session.execute(
                delete(OrganizationRecord).where(OrganizationRecord.id.in_(organizations))
            )
        engine.dispose()


@pytest.mark.parametrize("tenant", [0, 1], ids=["same-tenant", "foreign-tenant"])
def test_postgres_duplicate_customer_is_conflict_with_unchanged_history(
    customer_pg: CustomerPostgres, tenant: int
) -> None:
    db = customer_pg
    customer_id = new_id()
    first = db.create(customer_id, name="Original private fixture")
    assert first.status_code == 201
    before = db.snapshot()
    duplicate = db.create(customer_id, tenant=tenant, name="Conflicting fixture")
    assert duplicate.status_code == 409
    assert "Original private fixture" not in duplicate.text
    assert customer_id not in duplicate.text
    assert db.snapshot() == before
    with TestClient(db.app) as client:
        readback = client.get(f"/api/v1/customers/{customer_id}", headers=db.headers[0])
        assert readback.status_code == 200
        assert readback.json() == first.json()
        foreign = client.get(f"/api/v1/customers/{customer_id}", headers=db.headers[1])
        assert foreign.status_code == 404
    assert db.create(new_id(), tenant=tenant).status_code == 201


@pytest.mark.parametrize("kind", ["bicycles", "service-orders"])
@pytest.mark.parametrize("tenant", [0, 1], ids=["same-tenant", "foreign-tenant"])
def test_postgres_associated_duplicate_preserves_entity_and_all_history(
    customer_pg: CustomerPostgres, kind: str, tenant: int
) -> None:
    db = customer_pg
    customers = (new_id(), new_id())
    for owner, customer in enumerate(customers):
        assert db.create(customer, tenant=owner).status_code == 201
    entity_id = new_id()
    first = db.associated_create(kind, entity_id, customers[0])
    assert first.status_code == 201
    before = db.snapshot()
    duplicate = db.associated_create(kind, entity_id, customers[tenant], tenant=tenant)
    assert duplicate.status_code == 409
    assert entity_id not in duplicate.text
    assert customers[0] not in duplicate.text
    assert db.snapshot() == before
    with TestClient(db.app) as client:
        readback = client.get(f"/api/v1/{kind}/{entity_id}", headers=db.headers[0])
        assert readback.status_code == 200
        assert readback.json() == first.json()
        foreign = client.get(f"/api/v1/{kind}/{entity_id}", headers=db.headers[1])
        assert foreign.status_code == 404
    assert db.associated_create(kind, new_id(), customers[tenant], tenant=tenant).status_code == 201


@pytest.mark.parametrize("kind", ["customers", "bicycles", "service-orders"])
def test_postgres_unrelated_outbox_conflict_remains_503_and_rolls_back_whole_create(
    customer_pg: CustomerPostgres, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import cycling_workshop.events.outbox as outbox

    db = customer_pg
    customer_id = new_id()
    assert db.create(customer_id).status_code == 201
    before = db.snapshot()
    event_id = before["outbox_events"][0]["event_id"]
    with monkeypatch.context() as patch:
        patch.setattr(outbox, "new_id", lambda: event_id)
        response = (
            db.create(new_id())
            if kind == "customers"
            else db.associated_create(kind, new_id(), customer_id)
        )
    assert response.status_code == 503
    assert event_id not in response.text
    assert db.snapshot() == before
    assert db.create(new_id()).status_code == 201


def test_concurrent_cross_tenant_customer_id_has_one_creation_and_one_conflict(
    customer_pg: CustomerPostgres,
) -> None:
    db = customer_pg
    inserted, release = Event(), Event()
    first_backend: list[int] = []
    customer_id = new_id()

    def hold_first_insert(connection, _cursor, statement, _parameters, _context, _many):
        if statement.startswith("INSERT INTO customers") and not inserted.is_set():
            first_backend.append(connection.scalar(text("SELECT pg_backend_pid()")))
            inserted.set()
            assert release.wait(10), "First synthetic insert was not released"

    event.listen(db.engine, "after_cursor_execute", hold_first_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(db.create, customer_id, tenant=0, name="First fixture")
            try:
                assert inserted.wait(5), "First request did not insert its customer"
                second = executor.submit(db.create, customer_id, tenant=1, name="Second fixture")
                observed_wait = False
                deadline = time.monotonic() + 5
                with db.engine.connect().execution_options(
                    isolation_level="AUTOCOMMIT"
                ) as observer:
                    while time.monotonic() < deadline:
                        observed_wait = bool(
                            observer.scalar(
                                text(
                                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                    "WHERE application_name = :name AND state = 'active' "
                                    "AND wait_event_type = 'Lock' "
                                    "AND query LIKE 'INSERT INTO customers%' "
                                    "AND :blocker = ANY(pg_blocking_pids(pid)))"
                                ),
                                {"name": db.application_name, "blocker": first_backend[0]},
                            )
                        )
                        if observed_wait or second.done():
                            break
                        time.sleep(0.02)
                assert observed_wait, "Second customer insert never waited on the unique-key owner"
            finally:
                release.set()
            assert first.result(timeout=10).status_code == 201
            assert second.result(timeout=10).status_code == 409
    finally:
        release.set()
        event.remove(db.engine, "after_cursor_execute", hold_first_insert)
    state = db.snapshot()
    assert len(state["customers"]) == len(state["sync_changes"]) == len(state["outbox_events"]) == 1
    assert state["sync_mutation_receipts"] == []
    assert state["customers"][0]["organization_id"] == db.organizations[0]
    assert state["customers"][0]["display_name"] == "First fixture"
    assert db.create(new_id(), tenant=1).status_code == 201
