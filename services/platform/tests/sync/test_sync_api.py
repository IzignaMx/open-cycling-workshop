from cycling_workshop.app import create_app
from cycling_workshop.db.base import Base
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from cycling_workshop.shared.ids import new_id
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_client(*, intake: bool = False) -> TestClient:
    capabilities = ["customers.read", "customers.write", "sync.pull", "sync.push"]
    if intake:
        capabilities += ["bicycles.write", "orders.write"]
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
                capabilities=capabilities,
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
            capabilities=frozenset(capabilities),
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
    assert first.headers["cache-control"] == second.headers["cache-control"] == "no-store"
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


def test_batch_with_one_conflict_preserves_independent_valid_mutations() -> None:
    client = build_client()
    first_customer = new_id()
    create = client.post(
        "/api/v1/sync/mutations",
        json={
            "mutations": [
                {
                    "mutation_id": new_id(),
                    "entity_type": "customer",
                    "entity_id": first_customer,
                    "operation": "create",
                    "organization_id": "org-1",
                    "location_id": "loc-1",
                    "base_version": None,
                    "occurred_at": "2026-08-31T10:00:00Z",
                    "payload": {"display_name": "Cliente Base"},
                }
            ]
        },
    )
    assert create.status_code == 200
    assert create.json()["results"][0]["status"] == "applied"

    valid_before = new_id()
    valid_after = new_id()
    stale_mutation = new_id()
    batch = client.post(
        "/api/v1/sync/mutations",
        json={
            "mutations": [
                {
                    "mutation_id": valid_before,
                    "entity_type": "customer",
                    "entity_id": new_id(),
                    "operation": "create",
                    "organization_id": "org-1",
                    "location_id": "loc-1",
                    "base_version": None,
                    "occurred_at": "2026-08-31T10:00:01Z",
                    "payload": {"display_name": "Cliente Valido Antes"},
                },
                {
                    "mutation_id": stale_mutation,
                    "entity_type": "customer",
                    "entity_id": first_customer,
                    "operation": "update",
                    "organization_id": "org-1",
                    "location_id": "loc-1",
                    "base_version": 99,
                    "occurred_at": "2026-08-31T10:00:02Z",
                    "payload": {"display_name": "Edicion Obsoleta"},
                },
                {
                    "mutation_id": valid_after,
                    "entity_type": "customer",
                    "entity_id": new_id(),
                    "operation": "create",
                    "organization_id": "org-1",
                    "location_id": "loc-1",
                    "base_version": None,
                    "occurred_at": "2026-08-31T10:00:03Z",
                    "payload": {"display_name": "Cliente Valido Despues"},
                },
            ]
        },
    )
    assert batch.status_code == 200
    statuses = [result["status"] for result in batch.json()["results"]]
    assert statuses == ["applied", "conflict", "applied"]
    assert batch.json()["results"][1]["mutation_id"] == stale_mutation

    feed = client.get("/api/v1/sync/changes", params={"cursor": 0, "location_id": "loc-1"})
    assert feed.status_code == 200
    created_names = [
        item["payload"].get("display_name")
        for item in feed.json()["items"]
        if item["operation"] == "create"
    ]
    assert "Cliente Valido Antes" in created_names
    assert "Cliente Valido Despues" in created_names
    assert "Edicion Obsoleta" not in str(feed.json())


def test_sync_authentication_refusal_is_not_cacheable() -> None:
    client = build_client()
    client.headers.pop("Authorization")
    response = client.post("/api/v1/sync/mutations", json={"mutations": []})
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_oversized_customer_fields_conflict_individually_and_valid_peer_commits():
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
    from sqlalchemy import func, select

    client = build_client()
    invalid = [
        ("display_name", "x" * 201),
        ("email", "a" * 315 + "@x.com"),
        ("phone", "1" * 65),
        ("email", "İ" * 158 + "@x.co"),
    ]
    mutations = []
    for field, value in [*invalid, ("display_name", "Valid public peer")]:
        mutations.append(
            {
                "mutation_id": new_id(),
                "entity_type": "customer",
                "entity_id": new_id(),
                "operation": "create",
                "organization_id": "org-1",
                "location_id": "loc-1",
                "base_version": None,
                "occurred_at": "2026-08-07T00:00:00Z",
                "payload": {"display_name": "Public", field: value},
            }
        )
    response = client.post("/api/v1/sync/mutations", json={"mutations": mutations})
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == ["conflict"] * 4 + ["applied"]
    assert all(r["error_code"] == "sync_conflict" for r in response.json()["results"][:4])
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 1
        assert session.scalar(select(func.count()).select_from(MutationReceiptRecord)) == 1
        assert (
            session.get(CustomerRecord, mutations[-1]["entity_id"]).display_name
            == "Valid public peer"
        )
        assert all(session.get(CustomerRecord, m["entity_id"]) is None for m in mutations[:-1])
    # Rejection creates no applied receipt; correcting the same id remains possible.
    corrected = {**mutations[0], "payload": {"display_name": "Corrected public customer"}}
    retried = client.post("/api/v1/sync/mutations", json={"mutations": [corrected]})
    assert retried.status_code == 200 and retried.json()["results"][0]["status"] == "applied"


def test_oversized_customer_updates_preserve_row_version_history_and_receipts():
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
    from sqlalchemy import func, select

    client = build_client()
    created = {
        "mutation_id": new_id(),
        "entity_type": "customer",
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": None,
        "occurred_at": "2026-08-07T00:00:00Z",
        "payload": {"display_name": "Original", "email": "public@example.invalid", "phone": "123"},
    }
    assert (
        client.post("/api/v1/sync/mutations", json={"mutations": [created]}).json()["results"][0][
            "status"
        ]
        == "applied"
    )
    invalid = [
        ("display_name", "x" * 201),
        ("email", "a" * 315 + "@x.com"),
        ("phone", "1" * 65),
        ("email", "İ" * 158 + "@x.co"),
    ]
    updates = [
        {
            **created,
            "mutation_id": new_id(),
            "operation": "update",
            "base_version": 1,
            "payload": {field: value},
        }
        for field, value in invalid
    ]
    response = client.post("/api/v1/sync/mutations", json={"mutations": updates})
    assert response.status_code == 200
    assert [result["status"] for result in response.json()["results"]] == ["conflict"] * 4
    with client.app.state.session_factory() as session:
        row = session.get(CustomerRecord, created["entity_id"])
        assert (row.display_name, row.email, row.phone, row.version) == (
            "Original",
            "public@example.invalid",
            "123",
            1,
        )
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 1
        assert session.scalar(select(func.count()).select_from(MutationReceiptRecord)) == 1
    corrected = {**updates[0], "payload": {"display_name": "Corrected"}}
    retry = client.post("/api/v1/sync/mutations", json={"mutations": [corrected]})
    assert retry.json()["results"][0]["entity_version"] == 2


def test_malformed_customer_types_conflict_per_item_preserve_existing_row_and_valid_peers():
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
    from sqlalchemy import func, select

    client = build_client()
    original = {
        "mutation_id": new_id(),
        "entity_type": "customer",
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": None,
        "occurred_at": "2026-08-07T00:00:00Z",
        "payload": {"display_name": "Original", "email": "public@example.test", "phone": "123"},
    }
    assert (
        client.post("/api/v1/sync/mutations", json={"mutations": [original]}).json()["results"][0][
            "status"
        ]
        == "applied"
    )
    canary = "PUBLIC-SYNTHETIC-PRIVATE-CANARY"
    malformed = [("display_name", None)] + [
        (field, value)
        for field in ("display_name", "email", "phone")
        for value in (123, True, {"value": canary}, [])
    ]
    invalid = []
    for operation in ("create", "update"):
        for field, value in malformed:
            invalid.append(
                {
                    **original,
                    "mutation_id": new_id(),
                    "entity_id": new_id() if operation == "create" else original["entity_id"],
                    "operation": operation,
                    "base_version": None if operation == "create" else 1,
                    "payload": (
                        {"display_name": "Public", field: value}
                        if operation == "create"
                        else {field: value}
                    ),
                }
            )
    before = {
        **original,
        "mutation_id": new_id(),
        "entity_id": new_id(),
        "payload": {"display_name": "Before", "unknown_compatibility_field": "ignored"},
    }
    after = {
        **original,
        "mutation_id": new_id(),
        "entity_id": new_id(),
        "payload": {"display_name": "After", "email": None, "phone": None},
    }
    response = client.post("/api/v1/sync/mutations", json={"mutations": [before, *invalid, after]})
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == [
        "applied",
        *["conflict"] * len(invalid),
        "applied",
    ]
    assert all(item["error_code"] == "sync_conflict" for item in response.json()["results"][1:-1])
    assert (canary in response.text) is False
    with client.app.state.session_factory() as session:
        row = session.get(CustomerRecord, original["entity_id"])
        assert (row.display_name, row.email, row.phone, row.version) == (
            "Original",
            "public@example.test",
            "123",
            1,
        )
        assert session.scalar(select(func.count()).select_from(CustomerRecord)) == 3
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 3
        assert session.scalar(select(func.count()).select_from(MutationReceiptRecord)) == 3
        assert all(
            session.get(MutationReceiptRecord, item["mutation_id"]) is None for item in invalid
        )
    # Same previously refused id can be explicitly corrected; then omission preserves.
    cleared = {**invalid[-1], "payload": {"email": None, "phone": None}}
    assert (
        client.post("/api/v1/sync/mutations", json={"mutations": [cleared]}).json()["results"][0][
            "entity_version"
        ]
        == 2
    )
    renamed = {
        **cleared,
        "mutation_id": new_id(),
        "base_version": 2,
        "payload": {"display_name": "Renamed"},
    }
    assert (
        client.post("/api/v1/sync/mutations", json={"mutations": [renamed]}).json()["results"][0][
            "entity_version"
        ]
        == 3
    )
    with client.app.state.session_factory() as session:
        row = session.get(CustomerRecord, original["entity_id"])
        assert (row.display_name, row.email, row.phone, row.version) == ("Renamed", None, None, 3)


def test_intake_invalid_items_preserve_rows_and_allow_valid_batch_peers():
    from cycling_workshop.bicycles.models import BicycleRecord
    from cycling_workshop.service_orders.models import ServiceOrderRecord
    from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
    from sqlalchemy import func, select

    client = build_client(intake=True)

    def mutation(entity, payload, *, entity_id=None, operation="create"):
        return {
            "mutation_id": new_id(),
            "entity_type": entity,
            "entity_id": entity_id or new_id(),
            "operation": operation,
            "organization_id": "org-1",
            "location_id": "loc-1",
            "base_version": 1 if operation == "update" else None,
            "occurred_at": "2026-08-07T00:00:00Z",
            "payload": payload,
        }

    customer = mutation("customer", {"display_name": "Public customer"})
    bike_payload = {
        "customer_id": customer["entity_id"],
        "brand": "Public brand",
        "model": "Keep",
        "notes": "Keep notes",
    }
    bike = mutation("bicycle", bike_payload)
    seed = client.post("/api/v1/sync/mutations", json={"mutations": [customer, bike]})
    assert [r["status"] for r in seed.json()["results"]] == ["applied", "applied"]
    bad_bike = [("brand", None), ("brand", "\u0085")] + [
        (field, value)
        for field, limit in [
            ("brand", 120),
            ("model", 120),
            ("bicycle_type", 60),
            ("wheel_size", 30),
            ("notes", 2000),
        ]
        for value in ["🚲" * (limit + 1), 123, True, {"public": "CANARY"}, []]
    ]
    invalid = []
    for field, value in bad_bike:
        invalid.append(mutation("bicycle", {**bike_payload, field: value}))
        invalid.append(
            mutation("bicycle", {field: value}, entity_id=bike["entity_id"], operation="update")
        )
    order_payload = {"customer_id": customer["entity_id"], "reported_problem": "Public repair"}
    bad_order = [
        ("reported_problem", "\u0085"),
        ("priority", "\u0085"),
        ("reported_problem", None),
        ("priority", None),
        ("priority", "🚲" * 31),
    ] + [
        (field, value)
        for field in ["reported_problem", "priority", "intake_condition", "accessories"]
        for value in [123, True, {"public": "CANARY"}, []]
    ]
    invalid += [
        mutation("service_order", {**order_payload, field: value}) for field, value in bad_order
    ]
    before = mutation(
        "service_order",
        {
            **order_payload,
            "intake_condition": None,
            "accessories": None,
            "unknown_compatibility": "ignored",
        },
    )
    after = mutation(
        "service_order",
        {
            **order_payload,
            "reported_problem": "x" * 4001,
            "intake_condition": "y" * 4001,
            "accessories": "z" * 2001,
        },
    )
    response = client.post("/api/v1/sync/mutations", json={"mutations": [before, *invalid, after]})
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == [
        "applied",
        *["conflict"] * len(invalid),
        "applied",
    ]
    assert "CANARY" not in response.text
    with client.app.state.session_factory() as session:
        row = session.get(BicycleRecord, bike["entity_id"])
        assert (row.brand, row.model, row.notes, row.version) == (
            "Public brand",
            "Keep",
            "Keep notes",
            1,
        )
        assert session.scalar(select(func.count()).select_from(BicycleRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ServiceOrderRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 4
        assert session.scalar(select(func.count()).select_from(MutationReceiptRecord)) == 4
        assert all(
            session.get(MutationReceiptRecord, item["mutation_id"]) is None for item in invalid
        )
        assert session.get(ServiceOrderRecord, before["entity_id"]).priority == "normal"
    # Explicit clear is valid; omitted fields retain their values.
    clear = {**invalid[1], "payload": {"model": None}}
    cleared = client.post("/api/v1/sync/mutations", json={"mutations": [clear]})
    assert cleared.json()["results"][0]["entity_version"] == 2
    with client.app.state.session_factory() as session:
        row = session.get(BicycleRecord, bike["entity_id"])
        assert (row.model, row.notes, row.version) == (None, "Keep notes", 2)
