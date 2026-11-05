"""Known workshop write text must be persistable before effects or reference binds."""

import json

import pytest
from cycling_workshop.bicycles.domain import Bicycle
from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.domain import Customer
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.service_orders.domain import ServiceOrder
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from sqlalchemy import event, func, select

from services.platform.tests.bicycles.test_bicycle_api import build_client

BAD = ("\x00", "\ud800", "\udfff")
CASES = [
    (
        "customer",
        Customer,
        {
            "customer_id": "c",
            "organization_id": "org-1",
            "location_id": "loc-1",
            "display_name": "Safe",
        },
        ("display_name", "email", "phone"),
    ),
    (
        "bicycle",
        Bicycle,
        {
            "bicycle_id": "b",
            "customer_id": "customer-1",
            "organization_id": "org-1",
            "location_id": "loc-1",
            "brand": "Safe",
        },
        ("brand", "model", "bicycle_type", "wheel_size", "notes"),
    ),
    (
        "service_order",
        ServiceOrder,
        {
            "order_id": "r",
            "customer_id": "customer-1",
            "organization_id": "org-1",
            "location_id": "loc-1",
            "reported_problem": "Safe",
        },
        ("reported_problem", "intake_condition", "accessories", "priority"),
    ),
]
FIELDS = [(name, domain, base, field) for name, domain, base, fields in CASES for field in fields]
MODELS = (
    CustomerRecord,
    BicycleRecord,
    ServiceOrderRecord,
    ServiceOrderEventRecord,
    ChangeRecord,
    MutationReceiptRecord,
    OutboxRecord,
)


def bad_value(field, char):
    return "private" + char + ("@example.com" if field == "email" else "text")


def history(client):
    with client.app.state.session_factory() as session:
        return [session.scalar(select(func.count()).select_from(model)) for model in MODELS]


def command(entity="customer", payload=None):
    return dict(
        mutation_id=new_id(),
        entity_type=entity,
        entity_id=new_id(),
        operation="create",
        organization_id="org-1",
        location_id="loc-1",
        base_version=None,
        occurred_at="2026-11-05T00:00:00Z",
        payload=payload or {"display_name": "Safe"},
    )


def post(client, path, body):
    return client.post(path, content=json.dumps(body), headers={"Content-Type": "application/json"})


@pytest.mark.parametrize("name,domain,base,field", FIELDS)
@pytest.mark.parametrize("char", BAD)
def test_domain_create_rejects_unpersistable_text(name, domain, base, field, char):
    with pytest.raises(ValueError, match="text"):
        domain.create(**{**base, field: bad_value(field, char)})


@pytest.mark.parametrize(
    "name,domain,base,field", [item for item in FIELDS if item[0] != "service_order"]
)
@pytest.mark.parametrize("char", BAD)
def test_domain_update_rejects_unpersistable_text(name, domain, base, field, char):
    existing = domain.create(**base)
    with pytest.raises(ValueError, match="text"):
        existing.update(**{field: bad_value(field, char)})
    assert existing.version == 1


@pytest.mark.parametrize("char", BAD)
def test_order_note_and_diagnosis_reject_unpersistable_text(char):
    order = ServiceOrder.create(**CASES[2][2])
    with pytest.raises(ValueError, match="text"):
        order.transition("start_diagnosis", actor_id="a", note=bad_value("note", char))
    diagnosis = order.transition("start_diagnosis", actor_id="a").order
    with pytest.raises(ValueError, match="text"):
        diagnosis.set_diagnosis(bad_value("diagnosis", char))


@pytest.mark.parametrize("name,domain,base,field", FIELDS)
@pytest.mark.parametrize("char", BAD)
def test_rest_refuses_text_without_effects(name, domain, base, field, char):
    client = build_client()
    before = history(client)
    body = {
        k: v
        for k, v in base.items()
        if k
        not in (
            "organization_id",
            "bicycle_id"
            if name == "bicycle"
            else "order_id"
            if name == "service_order"
            else "customer_id",
        )
    }
    body[field] = bad_value(field, char)
    route = {"customer": "customers", "bicycle": "bicycles", "service_order": "service-orders"}[
        name
    ]
    response = post(client, "/api/v1/" + route, body)
    assert response.status_code == 422
    assert "private" not in response.text
    assert history(client) == before


@pytest.mark.parametrize("name,domain,base,field", FIELDS)
@pytest.mark.parametrize("char", BAD)
def test_legacy_sync_invalid_first_preserves_valid_following(name, domain, base, field, char):
    client = build_client()
    before = history(client)
    payload = {
        k: v
        for k, v in base.items()
        if k
        not in (
            "organization_id",
            "location_id",
            "bicycle_id"
            if name == "bicycle"
            else "order_id"
            if name == "service_order"
            else "customer_id",
        )
    }
    payload[field] = bad_value(field, char)
    response = post(
        client, "/api/v1/sync/mutations", {"mutations": [command(name, payload), command()]}
    )
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == ["conflict", "applied"]
    assert "private" not in response.text
    after = history(client)
    assert [a - b for a, b in zip(after, before, strict=True)] == [1, 0, 0, 0, 1, 1, 1]


@pytest.mark.parametrize("field", ["mutation_id", "entity_id"])
def test_sync_invalid_identity_never_reaches_bind_and_following_applies(field):
    client = build_client()
    engine = client.app.state.session_factory.kw["bind"]

    @event.listens_for(engine, "before_cursor_execute")
    def refuse_invalid_bind(conn, cursor, statement, parameters, context, executemany):
        assert not any(isinstance(p, str) and "\x00" in p for p in parameters)

    invalid = command()
    invalid[field] = "x" * 35 + "\x00"
    response = post(client, "/api/v1/sync/mutations", {"mutations": [invalid, command()]})
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == ["conflict", "applied"]


@pytest.mark.parametrize(
    "entity,field",
    [("bicycle", "customer_id"), ("service_order", "customer_id"), ("service_order", "bicycle_id")],
)
@pytest.mark.parametrize("char", BAD)
def test_sync_invalid_reference_never_reaches_bind(entity, field, char):
    client = build_client()
    engine = client.app.state.session_factory.kw["bind"]

    @event.listens_for(engine, "before_cursor_execute")
    def refuse_invalid_bind(conn, cursor, statement, parameters, context, executemany):
        assert not any(isinstance(p, str) and char in p for p in parameters)

    payload = {
        "customer_id": "customer-1",
        "brand": "Safe",
        "reported_problem": "Safe",
        field: bad_value(field, char),
    }
    response = post(
        client, "/api/v1/sync/mutations", {"mutations": [command(entity, payload), command()]}
    )
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == ["conflict", "applied"]


@pytest.mark.parametrize("char", BAD)
def test_transition_action_invalid_text_is_not_reflected(char):
    client = build_client()
    created = client.post(
        "/api/v1/service-orders",
        json={"customer_id": "customer-1", "location_id": "loc-1", "reported_problem": "Safe"},
    )
    assert created.status_code == 201
    before = history(client)
    invalid = command("service_order", {"transition": {"action": bad_value("action", char)}})
    invalid.update(entity_id=created.json()["order_id"], operation="update", base_version=1)
    response = post(client, "/api/v1/sync/mutations", {"mutations": [invalid, command()]})
    assert response.status_code == 200
    assert [r["status"] for r in response.json()["results"]] == ["conflict", "applied"]
    assert "private" not in response.text
    assert history(client)[3] == before[3]


@pytest.mark.parametrize(
    "entity,field",
    [
        ("customers", "location_id"),
        ("bicycles", "location_id"),
        ("bicycles", "customer_id"),
        ("service-orders", "customer_id"),
        ("service-orders", "bicycle_id"),
    ],
)
def test_rest_invalid_reference_is_safe_422_before_bind(entity, field):
    client = build_client()
    before = history(client)
    engine = client.app.state.session_factory.kw["bind"]

    @event.listens_for(engine, "before_cursor_execute")
    def refuse_invalid_bind(conn, cursor, statement, parameters, context, executemany):
        assert not any(isinstance(p, str) and "\x00" in p for p in parameters)

    response = post(
        client,
        "/api/v1/" + entity,
        {
            "location_id": "loc-1",
            "customer_id": "customer-1",
            "display_name": "Safe",
            "brand": "Safe",
            "reported_problem": "Safe",
            field: "private\x00text",
        },
    )
    assert response.status_code == 422
    assert "private" not in response.text
    assert history(client) == before


def test_safe_scalars_controls_and_ignored_metadata_remain_compatible():
    from cycling_workshop.shared.text import validate_storage_text

    for text in ("", "\t\n\r", "\x01\x1f\x7f", "🚲 e\u0301 é 漢字"):
        assert validate_storage_text(text) == text
    client = build_client()
    item = command(payload={"display_name": "  🚲  漢字  ", "ignored": "legacy\x00\ud800"})
    response = post(client, "/api/v1/sync/mutations", {"mutations": [item]})
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "applied"
    before = history(client)
    replay = post(client, "/api/v1/sync/mutations", {"mutations": [item]})
    assert replay.json() == response.json()
    assert history(client) == before


def test_strict_surrogate_canonical_refusal_unchanged():
    client = build_client()
    client.headers["X-OCWP-Write-Protocol"] = "1"
    before = history(client)
    response = post(
        client,
        "/api/v1/sync/mutations",
        {"mutations": [command(payload={"display_name": "private\ud800"})]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_canonical_command"
    assert history(client) == before


@pytest.mark.parametrize("entity,field", [("customer", "display_name"), ("bicycle", "notes")])
@pytest.mark.parametrize("char", BAD)
def test_sync_update_refusal_keeps_version_history_and_replay(entity, field, char):
    client = build_client()
    payload = (
        {"display_name": "Safe"}
        if entity == "customer"
        else {"customer_id": "customer-1", "brand": "Safe"}
    )
    initial = command(entity, payload)
    assert (
        post(client, "/api/v1/sync/mutations", {"mutations": [initial]}).json()["results"][0][
            "status"
        ]
        == "applied"
    )
    before = history(client)
    invalid = command(entity, {field: bad_value(field, char)})
    invalid.update(entity_id=initial["entity_id"], operation="update", base_version=1)
    valid = command()
    body = {"mutations": [invalid, valid]}
    response = post(client, "/api/v1/sync/mutations", body)
    assert response.status_code == 200
    assert [row["status"] for row in response.json()["results"]] == ["conflict", "applied"]
    assert "private" not in response.text
    after = history(client)
    assert [a - b for a, b in zip(after, before, strict=True)] == [1, 0, 0, 0, 1, 1, 1]
    with client.app.state.session_factory() as session:
        model = CustomerRecord if entity == "customer" else BicycleRecord
        assert session.get(model, initial["entity_id"]).version == 1
        assert session.get(MutationReceiptRecord, invalid["mutation_id"]) is None
    assert post(client, "/api/v1/sync/mutations", body).json() == response.json()
    assert history(client) == after


@pytest.mark.parametrize("char", BAD)
def test_legacy_transition_note_refusal_preserves_order_and_following_item(char):
    client = build_client()
    created = client.post(
        "/api/v1/service-orders",
        json={"customer_id": "customer-1", "location_id": "loc-1", "reported_problem": "Safe"},
    )
    assert created.status_code == 201
    before = history(client)
    invalid = command(
        "service_order",
        {"transition": {"action": "start_diagnosis", "note": bad_value("note", char)}},
    )
    invalid.update(entity_id=created.json()["order_id"], operation="update", base_version=1)
    response = post(client, "/api/v1/sync/mutations", {"mutations": [invalid, command()]})
    assert response.status_code == 200
    assert [row["status"] for row in response.json()["results"]] == ["conflict", "applied"]
    assert "private" not in response.text
    after = history(client)
    assert [a - b for a, b in zip(after, before, strict=True)] == [1, 0, 0, 0, 1, 1, 1]
    with client.app.state.session_factory() as session:
        order = session.get(ServiceOrderRecord, invalid["entity_id"])
        assert order.version == 1 and order.state == "INTAKE"


def test_strict_nul_is_per_item_conflict_without_changing_canonicalization():
    from dataclasses import replace

    client = build_client()
    client.app.state.settings = replace(client.app.state.settings, cutover_enabled=True)
    context = client.get("/api/v1/auth/context")
    assert context.status_code == 200
    client.headers.update(
        {
            "X-OCWP-Write-Protocol": "1",
            "X-OCWP-Authorization-Epoch": context.json()["authorization_epoch"],
        }
    )
    response = post(
        client,
        "/api/v1/sync/mutations",
        {"mutations": [command(payload={"display_name": "private\x00"}), command()]},
    )
    assert response.status_code == 200
    assert [row["status"] for row in response.json()["results"]] == ["conflict", "applied"]


@pytest.mark.parametrize("char", BAD)
def test_rest_transition_note_refuses_before_event_or_order_change(char):
    client = build_client()
    created = client.post(
        "/api/v1/service-orders",
        json={"customer_id": "customer-1", "location_id": "loc-1", "reported_problem": "Safe"},
    )
    assert created.status_code == 201
    before = history(client)
    response = post(
        client,
        f"/api/v1/service-orders/{created.json()['order_id']}/transitions",
        {"action": "start_diagnosis", "note": bad_value("note", char)},
    )
    assert response.status_code == 422
    assert "private" not in response.text
    assert history(client) == before
    with client.app.state.session_factory() as session:
        assert session.get(ServiceOrderRecord, created.json()["order_id"]).version == 1
