"""Real-auth write ingress with enforced SQLite FKs, not PostgreSQL concurrency proof."""

from dataclasses import replace

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.db.base import Base
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

CAPABILITIES = frozenset(
    {"customers.read", "customers.write", "bicycles.write", "orders.write", "sync.push"}
)
MODELS = (
    CustomerRecord,
    BicycleRecord,
    ServiceOrderRecord,
    ServiceOrderEventRecord,
    ChangeRecord,
    MutationReceiptRecord,
    OutboxRecord,
)
KINDS = [("customer", "customers"), ("bicycle", "bicycles"), ("service_order", "service-orders")]


def snapshot(client):
    with client.app.state.session_factory() as session:
        return {
            model.__tablename__: [
                dict(row) for row in session.execute(select(model.__table__)).mappings()
            ]
            for model in MODELS
        }


def credentials(client, *, account_location=None, token_location=None, capabilities=CAPABILITIES):
    with client.app.state.session_factory.begin() as session:
        actor = session.get(UserRecord, "actor")
        actor.location_id = account_location
        actor.capabilities = sorted(capabilities)
    token = client.app.state.session_tokens.issue(
        Principal("actor", "org", token_location, capabilities)
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        # Explicit BEGIN avoids SQLite legacy savepoints committing independently.
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def begin_transaction(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add_all(
            [
                OrganizationRecord(id="org", name="Synthetic"),
                OrganizationRecord(id="other", name="Other"),
            ]
        )
        session.flush()
        session.add_all(
            [
                LocationRecord(id="local", organization_id="org", name="Local"),
                LocationRecord(id="second", organization_id="org", name="Second"),
                LocationRecord(id="foreign", organization_id="other", name="Foreign"),
            ]
        )
        session.flush()
        session.add(
            UserRecord(
                id="actor",
                organization_id="org",
                location_id=None,
                username="synthetic",
                display_name="Synthetic actor",
                password_hash="unused-token-fixture",
                capabilities=sorted(CAPABILITIES),
                is_active=True,
                session_version=1,
            )
        )
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="synthetic-location-validation-secret",
    )
    app = create_app(settings=settings, session_factory=factory)
    with TestClient(app, raise_server_exceptions=False) as result:
        result.headers.update(credentials(result))
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        yield result
    engine.dispose()


def create_customer(client, location="local"):
    response = client.post(
        "/api/v1/customers", json={"location_id": location, "display_name": "Synthetic customer"}
    )
    assert response.status_code == 201, response.text
    return response.json()["customer_id"]


def payload(kind, customer):
    return {
        "customer": {"display_name": "Synthetic customer"},
        "bicycle": {"customer_id": customer, "brand": "Synthetic bicycle"},
        "service_order": {"customer_id": customer, "reported_problem": "Synthetic repair"},
    }[kind]


def mutation(kind, body, location="local"):
    return {
        "mutation_id": new_id(),
        "entity_type": kind,
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org",
        "location_id": location,
        "base_version": None,
        "occurred_at": "2026-11-05T09:00:00Z",
        "payload": body,
    }


@pytest.mark.parametrize("kind,path", KINDS)
@pytest.mark.parametrize("location", ["foreign", "missing"])
def test_rest_invalid_location_is_nondisclosing_client_error_without_effects(
    client, kind, path, location
):
    customer = create_customer(client)
    before = snapshot(client)
    response = client.post(
        f"/api/v1/{path}", json={**payload(kind, customer), "location_id": location}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "location not found"}
    assert snapshot(client) == before


@pytest.mark.parametrize("kind,_path", KINDS)
@pytest.mark.parametrize("location", ["foreign", "missing"])
def test_legacy_sync_invalid_location_is_item_conflict_and_preserves_batch_replay(
    client, kind, _path, location
):
    customer = create_customer(client)
    before = snapshot(client)
    invalid = mutation(kind, payload(kind, customer), location)
    valid = [mutation("customer", {"display_name": name}) for name in ("Before", "After")]
    batch = {"mutations": [valid[0], invalid, valid[1]]}
    first = client.post("/api/v1/sync/mutations", json=batch)
    assert first.status_code == 200, first.text
    results = first.json()["results"]
    assert [result["status"] for result in results] == ["applied", "conflict", "applied"]
    assert results[1] == {
        "mutation_id": invalid["mutation_id"],
        "status": "conflict",
        "entity_id": invalid["entity_id"],
        "entity_version": None,
        "error_code": "sync_conflict",
        "error_message": "location not found",
    }
    after = snapshot(client)
    for model in MODELS:
        rows = after[model.__tablename__]
        previous = before[model.__tablename__]
        if model in (CustomerRecord, ChangeRecord, MutationReceiptRecord, OutboxRecord):
            assert len(rows) == len(previous) + 2
            assert all(row in rows for row in previous)
        else:
            assert rows == previous
    with client.app.state.session_factory() as session:
        assert session.get(MutationReceiptRecord, invalid["mutation_id"]) is None
        for item in valid:
            assert session.get(CustomerRecord, item["entity_id"]) is not None
        assert (
            session.get(
                {
                    "customer": CustomerRecord,
                    "bicycle": BicycleRecord,
                    "service_order": ServiceOrderRecord,
                }[kind],
                invalid["entity_id"],
            )
            is None
        )
    replay = client.post("/api/v1/sync/mutations", json=batch)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert snapshot(client) == after


@pytest.mark.parametrize("kind,path", KINDS)
@pytest.mark.parametrize("transport", ["rest", "sync"])
@pytest.mark.parametrize("restriction", ["account", "token", "capability"])
def test_existing_authority_denial_precedes_location_validation(
    client, kind, path, transport, restriction
):
    customer = create_customer(client)
    capability = {
        "customer": "customers.write",
        "bicycle": "bicycles.write",
        "service_order": "orders.write",
    }[kind]
    headers = credentials(
        client,
        account_location="local" if restriction == "account" else None,
        token_location="local" if restriction == "token" else None,
        capabilities=CAPABILITIES - {capability} if restriction == "capability" else CAPABILITIES,
    )
    before = snapshot(client)
    body = payload(kind, customer)
    response = (
        client.post(f"/api/v1/{path}", headers=headers, json={**body, "location_id": "foreign"})
        if transport == "rest"
        else client.post(
            "/api/v1/sync/mutations",
            headers=headers,
            json={"mutations": [mutation(kind, body, "foreign")]},
        )
    )
    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "capability denied" if transport == "rest" else f"missing capability: {capability}"
        )
        if restriction == "capability"
        else "location scope denied"
    }
    assert snapshot(client) == before


@pytest.mark.parametrize("kind,_path", KINDS)
def test_protocol_one_valid_location_and_exact_replay_preserved(client, kind, _path):
    customer = create_customer(client)
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=True)
    context = client.get("/api/v1/auth/context?selected_location_id=local")
    assert context.status_code == 200
    headers = {
        "X-OCWP-Write-Protocol": "1",
        "X-OCWP-Authorization-Epoch": context.json()["authorization_epoch"],
    }
    batch = {"mutations": [mutation(kind, payload(kind, customer))]}
    first = client.post("/api/v1/sync/mutations", headers=headers, json=batch)
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "applied"
    after = snapshot(client)
    replay = client.post("/api/v1/sync/mutations", headers=headers, json=batch)
    assert replay.status_code == 200
    assert replay.json() == first.json()
    assert snapshot(client) == after


@pytest.mark.parametrize("transport", ["rest", "sync"])
def test_cross_location_parent_and_distinct_responsible_remain_valid(client, transport):
    owner = create_customer(client, "second")
    responsible = create_customer(client)
    bicycle = client.post(
        "/api/v1/bicycles",
        json={"location_id": "local", "customer_id": owner, "brand": "Synthetic"},
    )
    assert bicycle.status_code == 201
    body = {
        "customer_id": responsible,
        "bicycle_id": bicycle.json()["bicycle_id"],
        "reported_problem": "Synthetic",
    }
    if transport == "rest":
        response = client.post("/api/v1/service-orders", json={**body, "location_id": "second"})
        assert response.status_code == 201
    else:
        response = client.post(
            "/api/v1/sync/mutations",
            json={"mutations": [mutation("service_order", body, "second")]},
        )
        assert response.status_code == 200
        assert response.json()["results"][0]["status"] == "applied"


@pytest.mark.parametrize("kind,path", KINDS)
@pytest.mark.parametrize("transport", ["rest", "sync"])
def test_unexpected_database_failure_remains_503_without_effects(
    client, monkeypatch, kind, path, transport
):
    customer = create_customer(client)
    before = snapshot(client)

    def unavailable(*_args, **_kwargs):
        raise OperationalError("synthetic failure", {}, RuntimeError("synthetic"))

    target = (
        "cycling_workshop.sync.service.location_exists"
        if transport == "sync"
        else "cycling_workshop."
        + {"customer": "customers", "bicycle": "bicycles", "service_order": "service_orders"}[kind]
        + ".router.location_exists"
    )
    monkeypatch.setattr(target, unavailable)
    body = payload(kind, customer)
    response = (
        client.post(f"/api/v1/{path}", json={**body, "location_id": "local"})
        if transport == "rest"
        else client.post("/api/v1/sync/mutations", json={"mutations": [mutation(kind, body)]})
    )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "database_command_failed"
    assert error["message"] == "database command failed"
    assert error["details"] == {}
    assert "synthetic" not in response.text
    assert snapshot(client) == before
