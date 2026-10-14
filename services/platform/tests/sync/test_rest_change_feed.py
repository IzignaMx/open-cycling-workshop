from datetime import datetime

import pytest
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.sync.models import ChangeRecord
from sqlalchemy import func, select

from services.platform.tests.bicycles.test_bicycle_api import FULL_CAPABILITIES, build_client


def test_rest_writes_publish_complete_projections_and_outbox_once() -> None:
    client = build_client(capabilities=[*FULL_CAPABILITIES, "sync.pull"])
    customer = client.post(
        "/api/v1/customers",
        json={
            "location_id": "loc-1",
            "display_name": "REST customer",
        },
    )
    assert customer.status_code == 201
    bicycle = client.post(
        "/api/v1/bicycles",
        json={
            "customer_id": customer.json()["customer_id"],
            "location_id": "loc-1",
            "brand": "Test",
        },
    )
    assert bicycle.status_code == 201
    order = client.post(
        "/api/v1/service-orders",
        json={
            "customer_id": customer.json()["customer_id"],
            "bicycle_id": bicycle.json()["bicycle_id"],
            "location_id": "loc-1",
            "reported_problem": "Brake noise",
        },
    )
    assert order.status_code == 201
    changed = client.post(
        f"/api/v1/service-orders/{order.json()['order_id']}/transitions",
        json={"action": "start_diagnosis"},
    )
    assert changed.status_code == 200
    page = client.get("/api/v1/sync/changes").json()
    assert [
        (item["entity_type"], item["operation"], item["entity_version"]) for item in page["items"]
    ] == [
        ("customer", "create", 1),
        ("bicycle", "create", 1),
        ("service_order", "create", 1),
        ("service_order", "update", 2),
    ]
    for item, response in zip(page["items"], [customer, bicycle, order, changed], strict=True):
        expected = response.json()
        actual = item["payload"]
        for field in ("created_at", "updated_at"):
            expected[field] = datetime.fromisoformat(expected[field])
            actual[field] = datetime.fromisoformat(actual[field])
        assert actual == expected
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 4
        assert session.scalar(select(func.count()).select_from(OutboxRecord)) == 4
    assert len(client.get(f"/api/v1/service-orders/{order.json()['order_id']}/events").json()) == 1


def test_rest_failure_after_feed_append_rolls_back_domain_feed_outbox_and_event(
    monkeypatch,
) -> None:
    from cycling_workshop.service_orders import router as order_router
    from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
    from sqlalchemy.exc import SQLAlchemyError

    client = build_client()
    created = client.post(
        "/api/v1/service-orders",
        json={
            "customer_id": "customer-1",
            "location_id": "loc-1",
            "reported_problem": "Noise",
        },
    ).json()
    original = order_router.append_change

    def fail_after_append(*args, **kwargs):
        original(*args, **kwargs)
        raise SQLAlchemyError("injected failure after feed allocation")

    monkeypatch.setattr(order_router, "append_change", fail_after_append)
    response = client.post(
        f"/api/v1/service-orders/{created['order_id']}/transitions",
        json={"action": "start_diagnosis"},
    )
    assert response.status_code == 503
    with client.app.state.session_factory() as session:
        order = session.get(ServiceOrderRecord, created["order_id"])
        assert (order.version, order.state) == (1, "INTAKE")
        assert session.scalar(select(func.count()).select_from(ServiceOrderEventRecord)) == 0
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxRecord)) == 1


@pytest.mark.parametrize("entity", ["customer", "bicycle", "service_order"])
def test_rest_create_feed_failure_preserves_no_partial_domain_row(monkeypatch, entity) -> None:
    from importlib import import_module

    from cycling_workshop.bicycles.models import BicycleRecord
    from cycling_workshop.customers.models import CustomerRecord
    from cycling_workshop.service_orders.models import ServiceOrderRecord
    from sqlalchemy.exc import SQLAlchemyError

    client = build_client()
    module, path, payload, model = {
        "customer": (
            "customers",
            "/api/v1/customers",
            {
                "location_id": "loc-1",
                "display_name": "Failed customer",
            },
            CustomerRecord,
        ),
        "bicycle": (
            "bicycles",
            "/api/v1/bicycles",
            {
                "location_id": "loc-1",
                "customer_id": "customer-1",
                "brand": "Failed bicycle",
            },
            BicycleRecord,
        ),
        "service_order": (
            "service_orders",
            "/api/v1/service-orders",
            {
                "location_id": "loc-1",
                "customer_id": "customer-1",
                "reported_problem": "Failed order",
            },
            ServiceOrderRecord,
        ),
    }[entity]
    with client.app.state.session_factory() as session:
        before = session.scalar(select(func.count()).select_from(model))
    router = import_module(f"cycling_workshop.{module}.router")
    original = router.append_change

    def fail_after_append(*args, **kwargs):
        original(*args, **kwargs)
        raise SQLAlchemyError("injected failure after feed allocation")

    monkeypatch.setattr(router, "append_change", fail_after_append)
    assert client.post(path, json=payload).status_code == 503
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(model)) == before
        assert session.scalar(select(func.count()).select_from(ChangeRecord)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxRecord)) == 0
