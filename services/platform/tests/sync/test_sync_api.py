from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add(OrganizationRecord(id="org-1", name="Taller Uno"))
        session.add(LocationRecord(id="loc-1", organization_id="org-1", name="Principal"))
        session.add(
            UserRecord(
                id="user-1",
                organization_id="org-1",
                location_id="loc-1",
                username="test-user",
                display_name="Test User",
                password_hash="unused-in-token-tests",
                capabilities=["customers.read", "customers.write", "sync.pull", "sync.push"],
                is_active=True,
                session_version=1,
            )
        )
        session.commit()
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        log_level="WARNING",
        auth_secret="test-secret-that-is-long-enough-for-tests",
    )
    app = create_app(settings=settings, session_factory=factory)
    token = app.state.session_tokens.issue(
        Principal(
            user_id="user-1",
            organization_id="org-1",
            location_id="loc-1",
            capabilities=frozenset({"sync.push", "sync.pull", "customers.write", "customers.read"}),
        )
    )
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_sync_push_duplicate_and_pull_change() -> None:
    client = build_client()
    mutation_id = new_id()
    customer_id = new_id()
    payload = {
        "mutations": [
            {
                "mutation_id": mutation_id,
                "entity_type": "customer",
                "entity_id": customer_id,
                "operation": "create",
                "organization_id": "org-1",
                "location_id": "loc-1",
                "base_version": None,
                "occurred_at": "2026-08-07T00:00:00Z",
                "payload": {"display_name": "Ana Rivera"},
            }
        ]
    }

    first = client.post("/api/v1/sync/mutations", json=payload)
    second = client.post("/api/v1/sync/mutations", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["results"][0]["entity_version"] == 1
    assert second.json()["results"][0]["entity_version"] == 1

    pulled = client.get("/api/v1/sync/changes", params={"cursor": 0, "location_id": "loc-1"})
    assert pulled.status_code == 200
    assert len(pulled.json()["items"]) == 1
    assert pulled.json()["items"][0]["entity_id"] == customer_id


def test_sync_push_rejects_body_tenant_mismatch() -> None:
    client = build_client()
    response = client.post(
        "/api/v1/sync/mutations",
        json={
            "mutations": [
                {
                    "mutation_id": new_id(),
                    "entity_type": "customer",
                    "entity_id": new_id(),
                    "operation": "create",
                    "organization_id": "org-other",
                    "location_id": "loc-1",
                    "base_version": None,
                    "occurred_at": "2026-08-07T00:00:00Z",
                    "payload": {"display_name": "Ana Rivera"},
                }
            ]
        },
    )
    assert response.status_code == 403


def test_sync_batch_isolates_permanent_conflict_without_rolling_back_valid_mutation() -> None:
    client = build_client()
    existing_customer_id = new_id()
    create_existing = {
        "mutations": [
            {
                "mutation_id": new_id(),
                "entity_type": "customer",
                "entity_id": existing_customer_id,
                "operation": "create",
                "organization_id": "org-1",
                "location_id": "loc-1",
                "base_version": None,
                "occurred_at": "2026-08-07T00:00:00Z",
                "payload": {"display_name": "Existing"},
            }
        ]
    }
    assert client.post("/api/v1/sync/mutations", json=create_existing).status_code == 200

    valid_customer_id = new_id()
    batch = {
        "mutations": [
            {
                "mutation_id": new_id(),
                "entity_type": "customer",
                "entity_id": valid_customer_id,
                "operation": "create",
                "organization_id": "org-1",
                "location_id": "loc-1",
                "base_version": None,
                "occurred_at": "2026-08-07T00:01:00Z",
                "payload": {"display_name": "Valid"},
            },
            {
                "mutation_id": new_id(),
                "entity_type": "customer",
                "entity_id": existing_customer_id,
                "operation": "update",
                "organization_id": "org-1",
                "location_id": "loc-1",
                "base_version": 0,
                "occurred_at": "2026-08-07T00:02:00Z",
                "payload": {"display_name": "Stale"},
            },
        ]
    }

    response = client.post("/api/v1/sync/mutations", json=batch)

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == ["applied", "conflict"]
    assert results[1]["error_code"] == "sync_conflict"
    assert "base version" in results[1]["error_message"]

    pulled = client.get("/api/v1/sync/changes", params={"cursor": 0, "location_id": "loc-1"})
    entity_ids = [item["entity_id"] for item in pulled.json()["items"]]
    assert valid_customer_id in entity_ids
    assert entity_ids.count(existing_customer_id) == 1
