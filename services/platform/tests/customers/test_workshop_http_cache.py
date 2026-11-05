"""Private workshop responses must not enter browser or shared HTTP caches."""

import logging

import pytest
from cycling_workshop.app import create_app
from cycling_workshop.db.dependencies import get_session
from cycling_workshop.identity.domain import Principal
from cycling_workshop.identity.models import UserRecord
from cycling_workshop.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_customer_api import build_client

ROOTS = ("/api/v1/customers", "/api/v1/bicycles", "/api/v1/service-orders")
CAPABILITIES = frozenset(
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
def workshop_client():
    original, tokens = build_client()
    with original.app.state.session_factory.begin() as session:
        session.get(UserRecord, "user-1").capabilities = sorted(CAPABILITIES)
    client = TestClient(original.app, raise_server_exceptions=False)
    client.headers["Authorization"] = "Bearer " + tokens.issue(
        Principal("user-1", "org-1", "loc-1", CAPABILITIES)
    )
    customer_body = {"location_id": "loc-1", "display_name": "Synthetic private customer"}
    customer = client.post(ROOTS[0], json=customer_body)
    assert customer.status_code == 201
    customer_id = customer.json()["customer_id"]
    bicycle_body = {
        "location_id": "loc-1",
        "customer_id": customer_id,
        "brand": "Synthetic bicycle",
    }
    bicycle = client.post(ROOTS[1], json=bicycle_body)
    assert bicycle.status_code == 201
    order_body = {
        "location_id": "loc-1",
        "customer_id": customer_id,
        "bicycle_id": bicycle.json()["bicycle_id"],
        "reported_problem": "Synthetic private diagnosis",
    }
    order = client.post(ROOTS[2], json=order_body)
    assert order.status_code == 201
    paths = (
        f"{ROOTS[0]}/{customer_id}",
        f"{ROOTS[1]}/{bicycle.json()['bicycle_id']}",
        f"{ROOTS[2]}/{order.json()['order_id']}",
    )
    operations = (
        ("POST", ROOTS[0], customer_body, 201),
        ("POST", ROOTS[1], bicycle_body, 201),
        ("POST", ROOTS[2], order_body, 201),
        *(("GET", path, None, 200) for path in paths),
        ("GET", paths[0] + "/bicycles", None, 200),
        ("GET", paths[2] + "/events", None, 200),
        ("POST", paths[2] + "/transitions", {"action": "start_diagnosis"}, 200),
    )
    try:
        yield client, paths, operations
    finally:
        client.close()
        original.close()
        original.app.state.session_factory.kw["bind"].dispose()


@pytest.mark.parametrize("operation", range(9))
@pytest.mark.parametrize("trailing_slash", [False, True])
def test_workshop_success_and_redirects_are_no_store(workshop_client, operation, trailing_slash):
    client, _, operations = workshop_client
    method, path, body, status = operations[operation]
    response = client.request(
        method, path + ("/" if trailing_slash else ""), json=body, follow_redirects=True
    )
    assert response.status_code == status, response.text
    assert response.headers.get("cache-control") == "no-store"
    assert len(response.history) == int(trailing_slash)
    for redirect in response.history:
        assert redirect.status_code == 307
        assert redirect.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("case", ["unauthenticated", "forbidden", "missing", "method", "invalid"])
def test_workshop_http_errors_are_no_store(workshop_client, index, case):
    client, paths, _ = workshop_client
    method, path, body = "GET", paths[index], None
    if case == "unauthenticated":
        client.headers.pop("Authorization")
        expected = 401
    elif case == "forbidden":
        with client.app.state.session_factory.begin() as session:
            session.get(UserRecord, "user-1").capabilities = []
        expected = 403
    elif case == "missing":
        path, expected = ROOTS[index] + "/missing", 404
    elif case == "method":
        method, expected = "DELETE", 405
    else:
        method, path, body, expected = "POST", ROOTS[index], {}, 422
    response = client.request(method, path, json=body)
    assert response.status_code == expected, response.text
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("failure,status", [(RuntimeError, 500), (SQLAlchemyError, 503)])
def test_workshop_unexpected_failures_are_sanitized_and_no_store(
    workshop_client, index, failure, status, caplog, monkeypatch
):
    client, paths, _ = workshop_client
    canary = "synthetic-private-driver-detail-and-password"
    monkeypatch.setattr(logging.getLogger("cycling_workshop.app"), "disabled", False)

    def fail():
        raise failure(canary)

    client.app.dependency_overrides[get_session] = fail
    response = client.get(paths[index])
    assert response.status_code == status, response.text
    assert response.headers.get("cache-control") == "no-store"
    if status == 500:
        assert response.json() == {"detail": "internal server error"}
    else:
        assert response.json()["error"]["code"] == "database_command_failed"
    assert canary not in response.text + caplog.text
    assert client.headers["Authorization"] not in response.text + caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize(
    "host", ["testserver", "testserver/forged", "testserver?forged", "testserver#forged"]
)
def test_decoded_workshop_routes_are_private_independent_of_host(workshop_client, index, host):
    client, paths, _ = workshop_client
    root = ROOTS[index]
    # Encode both one namespace letter and the resource separator, exactly once.
    encoded_root = "/api/v1/%" + format(ord(root[8]), "02x") + root[9:]
    path = encoded_root + "%2F" + paths[index].removeprefix(root + "/")
    response = client.get(path, headers={"Host": host})
    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("root", ROOTS)
def test_unknown_workshop_descendants_are_no_store(root):
    response = TestClient(create_app(Settings(environment="test"))).get(root + "/unknown/nested")
    assert response.status_code == 404
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize(
    "path", [*(root + "-extra/resource" for root in ROOTS), "/health/live", "/api/openapi.json"]
)
def test_nonworkshop_routes_keep_existing_cache_behavior(path):
    response = TestClient(create_app(Settings(environment="test"))).get(path)
    assert "cache-control" not in response.headers
