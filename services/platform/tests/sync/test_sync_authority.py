"""HTTP regressions for actor attribution and receipt envelope binding."""

import pytest
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from cycling_workshop.tenancy.models import LocationRecord
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_sync_api import build_client


def _mutation(entity_type: str = "customer", **changes: object) -> dict[str, object]:
    return {
        "mutation_id": new_id(),
        "entity_type": entity_type,
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": None,
        "occurred_at": "2026-10-14T10:00:00Z",
        "payload": {"display_name": "Synthetic customer"},
        **changes,
    }


def _authorized_client() -> TestClient:
    client = build_client()
    grants = frozenset({"sync.push", "customers.write", "orders.write", "bicycles.write"})
    with client.app.state.session_factory.begin() as session:
        session.add(LocationRecord(id="loc-other", organization_id="org-1", name="Other workshop"))
        user = session.get(UserRecord, "user-1")
        assert user is not None
        user.capabilities = sorted(grants)
        user.location_id = None
    token = client.app.state.session_tokens.issue(Principal("user-1", "org-1", None, grants))
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.mark.parametrize("claimed_actor", ["forged-user", "user-1", None, 17])
def test_sync_transition_attributes_authenticated_actor_and_replays_once(
    claimed_actor: object,
) -> None:
    client = _authorized_client()
    customer = _mutation()
    order = _mutation(
        "service_order",
        payload={"customer_id": customer["entity_id"], "reported_problem": "Synthetic repair"},
    )
    created = client.post("/api/v1/sync/mutations", json={"mutations": [customer, order]})
    assert [result["status"] for result in created.json()["results"]] == ["applied", "applied"]
    transition: dict[str, object] = {"action": "start_diagnosis", "note": "Synthetic note"}
    if claimed_actor is not None:
        transition["actor_id"] = claimed_actor
    mutation = _mutation(
        "service_order",
        entity_id=order["entity_id"],
        operation="update",
        base_version=1,
        payload={"transition": transition},
    )

    first = client.post("/api/v1/sync/mutations", json={"mutations": [mutation]})
    replay = client.post("/api/v1/sync/mutations", json={"mutations": [mutation]})

    assert first.status_code == replay.status_code == 200
    assert first.json()["results"][0]["status"] == "applied"
    assert replay.json() == first.json()
    with client.app.state.session_factory() as session:
        events = list(session.scalars(select(ServiceOrderEventRecord)))
        assert len(events) == 1
        assert events[0].actor_id == "user-1"
        assert events[0].note == "Synthetic note"
        stored = session.get(ServiceOrderRecord, order["entity_id"])
        assert stored is not None and (stored.state, stored.version) == ("DIAGNOSIS", 2)
        for model in (ChangeRecord, OutboxRecord, MutationReceiptRecord):
            assert session.scalar(select(func.count()).select_from(model)) == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("location_id", "loc-other"),
        ("entity_type", "bicycle"),
        ("entity_id", "018f0000-0000-7000-8000-000000000999"),
        ("operation", "update"),
    ],
)
def test_receipt_tuple_mismatch_conflicts_without_blocking_independent_batch_items(
    field: str, value: str
) -> None:
    client = _authorized_client()  # Authorized for both locations: receipt guard must decide.
    original = _mutation()
    assert (
        client.post("/api/v1/sync/mutations", json={"mutations": [original]}).json()["results"][0][
            "status"
        ]
        == "applied"
    )
    before, after = _mutation(), _mutation()

    response = client.post(
        "/api/v1/sync/mutations",
        json={"mutations": [before, {**original, field: value}, after]},
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [result["status"] for result in results] == ["applied", "conflict", "applied"]
    assert results[1]["error_code"] == "sync_conflict"
    assert results[1]["entity_version"] is None
    with client.app.state.session_factory() as session:
        for model in (CustomerRecord, ChangeRecord, OutboxRecord, MutationReceiptRecord):
            assert session.scalar(select(func.count()).select_from(model)) == 3
        receipt = session.get(MutationReceiptRecord, original["mutation_id"])
        assert receipt is not None
        assert (receipt.location_id, receipt.entity_type, receipt.entity_id, receipt.operation) == (
            "loc-1",
            "customer",
            original["entity_id"],
            "create",
        )


@pytest.mark.parametrize("change", ["grants", "location", "session"])
def test_receipt_replay_still_requires_current_authority(change: str) -> None:
    client = _authorized_client()
    original = _mutation()
    created = client.post("/api/v1/sync/mutations", json={"mutations": [original]})
    assert created.json()["results"][0]["status"] == "applied"
    with client.app.state.session_factory.begin() as session:
        actor = session.get(UserRecord, "user-1")
        assert actor is not None
        if change == "grants":
            actor.capabilities = ["sync.push"]
        elif change == "location":
            actor.location_id = "loc-other"
        else:
            actor.session_version += 1

    replay = client.post("/api/v1/sync/mutations", json={"mutations": [original]})

    assert replay.status_code == (401 if change == "session" else 403)
    with client.app.state.session_factory() as session:
        for model in (CustomerRecord, ChangeRecord, OutboxRecord, MutationReceiptRecord):
            assert session.scalar(select(func.count()).select_from(model)) == 1
