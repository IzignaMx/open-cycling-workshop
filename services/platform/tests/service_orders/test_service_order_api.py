from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from services.platform.tests.bicycles.test_bicycle_api import FULL_CAPABILITIES, build_client


def _order_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "customer_id": "customer-1",
        "location_id": "loc-1",
        "reported_problem": "  Cadena saltando ",
        "intake_condition": "Rayado leve",
        "accessories": "Canasto",
        "priority": "high",
    }
    payload.update(overrides)
    return payload


def _create_order(client, **overrides: object) -> dict[str, object]:
    response = client.post("/api/v1/service-orders", json=_order_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def test_order_create_starts_at_intake() -> None:
    client = build_client()

    body = _create_order(client)

    assert body["state"] == "INTAKE"
    assert body["reported_problem"] == "Cadena saltando"
    assert body["priority"] == "high"
    assert body["version"] == 1
    assert len(body["order_id"]) == 36


def test_order_create_unknown_customer_is_404() -> None:
    client = build_client()

    response = client.post(
        "/api/v1/service-orders",
        json=_order_payload(customer_id="00000000-0000-7000-8000-000000000099"),
    )

    assert response.status_code == 404


def test_order_endpoints_require_capabilities() -> None:
    shared = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    writer = build_client(engine=shared)
    reader = build_client(capabilities=["orders.read"], engine=shared)
    created = _create_order(writer)

    forbidden = reader.post(
        f"/api/v1/service-orders/{created['order_id']}/transitions",
        json={"action": "start_diagnosis"},
    )
    assert forbidden.status_code == 403

    allowed = reader.get(f"/api/v1/service-orders/{created['order_id']}")
    assert allowed.status_code == 200


def test_order_transition_executes_and_returns_updated_order() -> None:
    client = build_client()
    created = _create_order(client)

    response = client.post(
        f"/api/v1/service-orders/{created['order_id']}/transitions",
        json={"action": "start_diagnosis", "note": " revisión inicial "},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "DIAGNOSIS"
    assert body["version"] == created["version"] + 1


def test_order_invalid_transition_is_409() -> None:
    client = build_client()
    created = _create_order(client)

    response = client.post(
        f"/api/v1/service-orders/{created['order_id']}/transitions",
        json={"action": "mark_ready"},
    )

    assert response.status_code == 409
    assert "invalid_state_transition" in response.json()["detail"]


def test_order_unknown_transition_action_is_422() -> None:
    client = build_client()
    created = _create_order(client)

    response = client.post(
        f"/api/v1/service-orders/{created['order_id']}/transitions",
        json={"action": "explode"},
    )

    assert response.status_code == 422


def test_order_timeline_lists_events_newest_first() -> None:
    client = build_client()
    created = _create_order(client)
    order_id = created["order_id"]
    for action in ("start_diagnosis", "authorize", "start_work"):
        transitioned = client.post(
            f"/api/v1/service-orders/{order_id}/transitions", json={"action": action}
        )
        assert transitioned.status_code == 200

    timeline = client.get(f"/api/v1/service-orders/{order_id}/events")

    assert timeline.status_code == 200
    events = timeline.json()
    assert [event["action"] for event in events] == [
        "start_diagnosis",
        "authorize",
        "start_work",
    ]
    assert events[0]["from_state"] == "INTAKE"
    assert events[-1]["to_state"] == "IN_PROGRESS"
    assert all(event["actor_id"] == "user-1" for event in events)


def test_order_get_returns_404_for_unknown() -> None:
    client = build_client()

    response = client.get("/api/v1/service-orders/00000000-0000-7000-8000-0000000000ff")

    assert response.status_code == 404


def test_sync_push_maps_entity_capabilities() -> None:
    # A token without orders.write must not push service_order mutations even
    # with sync.push; the router enforces per-entity capabilities.
    customer_only = build_client(
        capabilities=[c for c in FULL_CAPABILITIES if c not in ("orders.write",)]
    )
    created = _create_order(build_client())

    stale_update = {
        "mutation_id": "00000000-0000-7000-8000-00000000aaaa",
        "entity_type": "service_order",
        "entity_id": created["order_id"],
        "operation": "update",
        "organization_id": "org-1",
        "location_id": "loc-1",
        "base_version": 99,
        "occurred_at": "2026-08-31T10:00:00Z",
        "payload": {"transition": {"action": "authorize", "actor_id": "user-1"}},
    }
    response = customer_only.post("/api/v1/sync/mutations", json={"mutations": [stale_update]})

    assert response.status_code == 403
