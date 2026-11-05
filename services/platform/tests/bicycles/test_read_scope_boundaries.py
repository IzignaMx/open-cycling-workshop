"""Real HTTP authorization for mixed-location business records (SQLite only)."""

import pytest
from cycling_workshop.bicycles.repository import SqlAlchemyBicycleRepository
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.tenancy.models import LocationRecord, OrganizationRecord
from fastapi.testclient import TestClient

from services.platform.tests.customers.test_customer_api import build_client

CAPS = frozenset(
    {
        "customers.read",
        "customers.write",
        "bicycles.read",
        "bicycles.write",
        "orders.read",
        "orders.write",
    }
)


@pytest.fixture
def scoped_records():
    original, tokens = build_client()
    client = TestClient(original.app, raise_server_exceptions=False)
    factory = client.app.state.session_factory
    with factory.begin() as session:
        actor = session.get(UserRecord, "user-1")
        actor.location_id = None
        actor.capabilities = sorted(CAPS)
        session.add(LocationRecord(id="loc-2", organization_id="org-1", name="Second"))
        session.add(OrganizationRecord(id="org-2", name="Other tenant"))
        session.add(LocationRecord(id="loc-3", organization_id="org-2", name="Other"))
        session.add(
            UserRecord(
                id="user-2",
                organization_id="org-2",
                location_id="loc-3",
                username="other",
                display_name="Other",
                password_hash="unused",
                capabilities=sorted(CAPS),
                is_active=True,
                session_version=1,
            )
        )

    def headers(user="user-1", org="org-1", location=None):
        return {"Authorization": "Bearer " + tokens.issue(Principal(user, org, location, CAPS))}

    admin = headers()
    records = []
    for location in ("loc-1", "loc-2"):
        customer = client.post(
            "/api/v1/customers",
            headers=admin,
            json={"location_id": location, "display_name": "Synthetic customer"},
        )
        assert customer.status_code == 201
        cid = customer.json()["customer_id"]
        order = client.post(
            "/api/v1/service-orders",
            headers=admin,
            json={
                "location_id": location,
                "customer_id": cid,
                "reported_problem": "Synthetic problem",
            },
        )
        assert order.status_code == 201
        records.append({"customer": cid, "order": order.json()["order_id"]})
    # Both bicycles belong to the accessible customer; their resource scopes differ.
    for index, location in enumerate(("loc-1", "loc-2")):
        bicycle = client.post(
            "/api/v1/bicycles",
            headers=admin,
            json={
                "location_id": location,
                "customer_id": records[0]["customer"],
                "brand": "Z visible" if index == 0 else "A hidden",
                "notes": f"private-{location}",
            },
        )
        assert bicycle.status_code == 201
        records[index]["bicycle"] = bicycle.json()["bicycle_id"]
    with factory.begin() as session:
        session.get(UserRecord, "user-1").location_id = "loc-1"
    yield client, records, headers, factory
    client.close()
    original.close()
    factory.kw["bind"].dispose()


def path(record, kind):
    return {
        "customer": f"/api/v1/customers/{record['customer']}",
        "bicycle": f"/api/v1/bicycles/{record['bicycle']}",
        "order": f"/api/v1/service-orders/{record['order']}",
        "events": f"/api/v1/service-orders/{record['order']}/events",
        "nested": f"/api/v1/customers/{record['customer']}/bicycles",
    }[kind]


@pytest.mark.parametrize("kind", ["customer", "bicycle", "order", "events", "nested"])
@pytest.mark.parametrize(
    "scope,expected", [("same", 200), ("foreign-location", 403), ("foreign-tenant", 404)]
)
def test_read_scope_status(scoped_records, kind, scope, expected):
    client, records, headers, _ = scoped_records
    record = records[1] if scope == "foreign-location" else records[0]
    auth = (
        headers("user-2", "org-2", "loc-3")
        if scope == "foreign-tenant"
        else headers(location="loc-1")
    )
    response = client.get(path(record, kind), headers=auth)
    assert response.status_code == expected, response.text
    if expected != 200:
        assert "private-loc-2" not in response.text


@pytest.mark.parametrize(
    "account_location,token_location",
    [("loc-1", None), ("loc-1", "loc-1"), (None, "loc-1")],
)
def test_nested_list_filters_each_bicycle_for_persisted_and_token_scope(
    scoped_records, account_location, token_location
):
    client, records, headers, factory = scoped_records
    with factory.begin() as session:
        session.get(UserRecord, "user-1").location_id = account_location
    response = client.get(path(records[0], "nested"), headers=headers(location=token_location))
    assert response.status_code == 200
    assert [row["bicycle_id"] for row in response.json()] == [records[0]["bicycle"]]
    assert "private-loc-2" not in response.text


def test_organization_wide_nested_list_preserves_both_locations(scoped_records):
    client, records, headers, factory = scoped_records
    with factory.begin() as session:
        session.get(UserRecord, "user-1").location_id = None
    response = client.get(path(records[0], "nested"), headers=headers())
    assert response.status_code == 200
    assert {row["bicycle_id"] for row in response.json()} == {
        record["bicycle"] for record in records
    }


def test_repository_filters_location_before_limit(scoped_records):
    _, records, _, factory = scoped_records
    with factory() as session:
        repository = SqlAlchemyBicycleRepository(session)
        visible = repository.list_by_customer(
            customer_id=records[0]["customer"],
            organization_id="org-1",
            location_id="loc-1",
            limit=1,
        )
        assert [row.bicycle_id for row in visible] == [records[0]["bicycle"]]
        assert (
            repository.list_by_customer(
                customer_id=records[0]["customer"],
                organization_id="org-2",
                location_id="loc-1",
                limit=1,
            )
            == []
        )


@pytest.mark.parametrize("kind", ["customer", "bicycle", "order", "events", "nested"])
def test_conflicting_persisted_and_token_location_rejects_session(scoped_records, kind):
    client, records, headers, _ = scoped_records
    response = client.get(path(records[0], kind), headers=headers(location="loc-2"))
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid session"}
    assert "private-loc-" not in response.text
