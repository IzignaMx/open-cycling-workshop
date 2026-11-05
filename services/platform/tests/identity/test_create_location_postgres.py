"""Real PostgreSQL item isolation; unavailable guarded database is an explicit skip."""

import pytest
from cycling_workshop.bicycles.models import BicycleRecord
from cycling_workshop.customers.models import CustomerRecord
from cycling_workshop.events.models import OutboxRecord
from cycling_workshop.service_orders.models import ServiceOrderEventRecord, ServiceOrderRecord
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.models import ChangeRecord, MutationReceiptRecord
from sqlalchemy import select
from test_administration_postgres import HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres

MODELS = (
    CustomerRecord,
    BicycleRecord,
    ServiceOrderRecord,
    ServiceOrderEventRecord,
    ChangeRecord,
    MutationReceiptRecord,
    OutboxRecord,
)


def _snapshot(db):
    with db.factory() as session:
        return {
            model.__tablename__: [
                dict(row)
                for row in session.execute(
                    select(model.__table__).order_by(*model.__table__.primary_key.columns)
                ).mappings()
            ]
            for model in MODELS
        }


def _mutation(db, kind, payload, location):
    return {
        "mutation_id": new_id(),
        "entity_type": kind,
        "entity_id": new_id(),
        "operation": "create",
        "organization_id": db.organization_id,
        "location_id": location,
        "base_version": None,
        "occurred_at": "2026-11-05T09:00:00Z",
        "payload": payload,
    }


@pytest.mark.parametrize("kind", ["customer", "bicycle", "service_order"])
@pytest.mark.parametrize("location_kind", ["foreign", "missing"])
def test_invalid_location_conflicts_without_aborting_independent_items_and_replays(
    administration_postgres, kind, location_kind
):
    db = administration_postgres
    headers = db.headers(db.seed())
    created = db.request(
        HttpCommand(
            "POST",
            "/api/v1/customers",
            headers,
            {"location_id": db.location_id, "display_name": "Synthetic parent"},
        )
    )
    assert created.status_code == 201
    customer = created.json()["customer_id"]
    payload = {
        "customer": {"display_name": "Invalid location"},
        "bicycle": {"customer_id": customer, "brand": "Invalid location"},
        "service_order": {"customer_id": customer, "reported_problem": "Invalid location"},
    }[kind]
    location = db.foreign_location_id if location_kind == "foreign" else new_id()
    invalid = _mutation(db, kind, payload, location)
    valid = [
        _mutation(db, "customer", {"display_name": name}, db.location_id)
        for name in ("Before", "After")
    ]
    command = HttpCommand(
        "POST",
        "/api/v1/sync/mutations",
        headers,
        {"mutations": [valid[0], invalid, valid[1]]},
    )
    before = _snapshot(db)
    response = db.request(command)
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [row["status"] for row in results] == ["applied", "conflict", "applied"]
    assert results[1] == {
        "mutation_id": invalid["mutation_id"],
        "status": "conflict",
        "entity_id": invalid["entity_id"],
        "entity_version": None,
        "error_code": "sync_conflict",
        "error_message": "location not found",
    }
    after = _snapshot(db)
    for model in MODELS:
        previous, current = before[model.__tablename__], after[model.__tablename__]
        if model in (CustomerRecord, ChangeRecord, MutationReceiptRecord, OutboxRecord):
            assert len(current) == len(previous) + 2
            assert all(row in current for row in previous)
        else:
            assert current == previous
    with db.factory() as session:
        assert session.get(MutationReceiptRecord, invalid["mutation_id"]) is None
        for item in valid:
            assert session.get(CustomerRecord, item["entity_id"]) is not None
        model = {
            "customer": CustomerRecord,
            "bicycle": BicycleRecord,
            "service_order": ServiceOrderRecord,
        }[kind]
        assert session.get(model, invalid["entity_id"]) is None
    replay = db.request(command)
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert _snapshot(db) == after
