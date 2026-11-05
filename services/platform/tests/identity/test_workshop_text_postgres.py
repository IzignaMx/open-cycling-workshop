"""Real PostgreSQL text admission; requires the guarded dedicated test database."""

import pytest
from cycling_workshop.shared.ids import new_id
from test_administration_postgres import HttpCommand
from test_administration_postgres import administration_postgres as administration_postgres
from test_create_location_postgres import _mutation, _snapshot


@pytest.mark.parametrize(
    "kind,field",
    [
        ("customer", "display_name"),
        ("bicycle", "brand"),
        ("service_order", "reported_problem"),
        ("bicycle", "customer_id"),
        ("service_order", "bicycle_id"),
    ],
)
def test_postgres_nul_item_is_permanent_and_independent_following_item_commits(
    administration_postgres, kind, field
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
    payload = {
        "customer_id": created.json()["customer_id"],
        "display_name": "Safe",
        "brand": "Safe",
        "reported_problem": "Safe",
        field: "private\x00text",
    }
    invalid = _mutation(db, kind, payload, db.location_id)
    valid = _mutation(db, "customer", {"display_name": "Valid 🚲"}, db.location_id)
    request = HttpCommand(
        "POST", "/api/v1/sync/mutations", headers, {"mutations": [invalid, valid]}
    )
    before = _snapshot(db)
    response = db.request(request)
    assert response.status_code == 200
    assert [item["status"] for item in response.json()["results"]] == ["conflict", "applied"]
    assert "private" not in response.text
    after = _snapshot(db)
    for table in before:
        expected = (
            1
            if table in ("customers", "sync_changes", "sync_mutation_receipts", "outbox_events")
            else 0
        )
        assert len(after[table]) == len(before[table]) + expected
        assert all(row in after[table] for row in before[table])
    replay = db.request(request)
    assert replay.json() == response.json()
    assert _snapshot(db) == after


@pytest.mark.parametrize(
    "route,field",
    [("customers", "display_name"), ("bicycles", "customer_id"), ("service-orders", "bicycle_id")],
)
def test_postgres_rest_nul_is_safe_422_without_effects(administration_postgres, route, field):
    db = administration_postgres
    headers = db.headers(db.seed())
    before = _snapshot(db)
    response = db.request(
        HttpCommand(
            "POST",
            "/api/v1/" + route,
            headers,
            {
                "location_id": db.location_id,
                "customer_id": new_id(),
                "display_name": "Safe",
                "brand": "Safe",
                "reported_problem": "Safe",
                field: "private\x00text",
            },
        )
    )
    assert response.status_code == 422
    assert "private" not in response.text
    assert _snapshot(db) == before
