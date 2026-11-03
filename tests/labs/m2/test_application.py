"""Actual ASGI functional proof, not PostgreSQL/network/TLS qualification."""

from __future__ import annotations

import importlib
import importlib.util
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

PATH = "/api/v1/connector-catalogue/products"


def components():
    assert importlib.util.find_spec("tests.labs.m2.application") is not None, (
        "dedicated laboratory application is not implemented"
    )
    authority = importlib.import_module("tests.labs.m2.authority")
    application = importlib.import_module("tests.labs.m2.application")
    return authority.LabAuthority, application.create_lab_app


@pytest.fixture
def lab() -> Iterator[tuple]:
    authority_class, create_app = components()
    authority = authority_class()
    try:
        credential = authority.issue("primary")
        with TestClient(create_app(authority)) as client:
            client.headers["Authorization"] = credential.authorization()
            try:
                yield authority, credential, client
            finally:
                client.headers.clear()
    finally:
        authority.close()


def test_catalogue_returns_closed_projection_for_actual_machine(lab):
    _, _, client = lab
    response = client.get(PATH)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "next_offset"}
    assert len(payload["items"]) > 0
    assert all(
        set(item) == {"product_id", "sku", "name", "unit", "version"} for item in payload["items"]
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert "etag" not in response.headers


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=51",
        "offset=-1",
        "offset=201",
        "limit=x",
        "limit=1&limit=2",
        "organization_id=org-2",
        "location_id=loc-2",
        "extra=true",
        "limit=1.0",
    ],
)
def test_closed_query_refuses_widening_and_invalid_bounds(lab, query):
    _, _, client = lab
    response = client.get(f"{PATH}?{query}")
    assert response.status_code == 422
    assert response.headers["cache-control"] == "private, no-store"


def test_query_authentication_precedes_validation(lab):
    _, _, client = lab
    client.headers.clear()
    response = client.get(f"{PATH}?limit=invalid")
    assert response.status_code == 401
    assert response.json() == {"detail": "laboratory request refused"}


def test_revoke_and_rotation_affect_real_http_reads(lab):
    authority, credential, client = lab
    replacement = authority.rotate(credential.credential_id)
    assert client.get(PATH).status_code == 401
    client.headers["Authorization"] = replacement.authorization()
    assert client.get(PATH).status_code == 200
    authority.revoke(replacement.credential_id)
    assert client.get(PATH).status_code == 401


def test_current_grants_not_cached_at_application_creation(lab):
    authority, credential, client = lab
    assert client.get(PATH).status_code == 200
    authority.update_grants(credential.credential_id, installation_read=False, machine_read=True)
    assert client.get(PATH).status_code == 403


def test_two_location_two_organization_http_results_never_mix(lab):
    authority, _, client = lab
    first = {row["product_id"] for row in client.get(PATH).json()["items"]}
    for fixture in ("other_location", "other_org"):
        credential = authority.issue(fixture)
        client.headers["Authorization"] = credential.authorization()
        response = client.get(PATH)
        assert response.status_code == 200
        current = {row["product_id"] for row in response.json()["items"]}
        assert current and not first.intersection(current)


def test_repeated_reads_have_no_lifecycle_or_product_side_effect(lab):
    _, _, client = lab
    first = client.get(PATH).json()
    assert client.get(PATH).json() == first


def test_unknown_routes_methods_and_private_errors_are_not_publicly_cached(lab):
    _, _, client = lab
    for response in (
        client.get("/api/v1/inventory/products"),
        client.post(PATH),
        client.get("/openapi.json"),
        client.get("/docs"),
    ):
        assert response.status_code in (404, 405)
        assert response.headers["cache-control"] == "private, no-store"
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "headers",
    [
        [("Authorization", "Bearer invalid"), ("Authorization", "Bearer invalid")],
        [("Authorization", "Bearer " + "x" * 129)],
        [("Authorization", "Bearer human.jwt.token")],
    ],
)
def test_ambiguous_oversized_or_human_credentials_refused(lab, headers):
    _, _, client = lab
    client.headers.clear()
    response = client.get(PATH, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "laboratory request refused"}


def test_body_and_oversized_query_header_are_bounded(lab):
    _, _, client = lab
    for response in (
        client.request("GET", PATH, content=b"x"),
        client.get(PATH + "?" + "x" * 1025),
        client.get(PATH, headers={"X-Too-Large": "x" * 8193}),
    ):
        assert response.status_code == 413
        assert response.headers["cache-control"] == "private, no-store"


def test_failed_auth_budget_closes_admission_for_entire_run(lab):
    _, credential, client = lab
    client.headers["Authorization"] = "Bearer invalid"
    for _ in range(20):
        assert client.get(PATH).status_code == 401
    client.headers["Authorization"] = credential.authorization()
    assert client.get(PATH).status_code == 429


def test_run_request_budget_counts_valid_requests(lab):
    _, _, client = lab
    for _ in range(120):
        assert client.get(PATH).status_code == 200
    assert client.get(PATH).status_code == 429


def test_credentials_not_reflected_in_error_or_success_body(lab):
    _, credential, client = lab
    success = client.get(PATH)
    refused = client.get(PATH + "?unknown=true")
    present = any(credential.authorization() in response.text for response in (success, refused))
    assert not present
    assert len(json.dumps(success.json()).encode()) < 65536


def test_server_concurrency_limit_refuses_without_wait_queue():
    import asyncio

    from tests.labs.m2.application import Boundary, RequestBudget

    async def scenario():
        release = asyncio.Event()
        entered = 0
        responses = []

        async def service(scope, receive, send):
            nonlocal entered
            entered += 1
            await release.wait()
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                responses.append(message["status"])

        boundary = Boundary(service, RequestBudget())
        scope = {"type": "http", "headers": [], "query_string": b""}
        first = asyncio.create_task(boundary(scope, receive, send))
        second = asyncio.create_task(boundary(scope, receive, send))
        for _ in range(30):
            if entered == 2:
                break
            await asyncio.sleep(0)
        assert entered == 2
        await asyncio.wait_for(boundary(scope, receive, send), timeout=1)
        assert responses == [429]
        release.set()
        await asyncio.gather(first, second)
        assert sorted(responses) == [204, 204, 429]

    asyncio.run(scenario())


def test_recreating_test_app_does_not_reset_authority_run_budgets(lab):
    authority, credential, client = lab
    client.headers["Authorization"] = "Bearer invalid"
    for _ in range(20):
        assert client.get(PATH).status_code == 401
    _, create_app = components()
    with TestClient(create_app(authority)) as other:
        other.headers["Authorization"] = credential.authorization()
        status = other.get(PATH).status_code
        other.headers.clear()
    assert status == 429


def test_production_composition_has_no_lab_route_permissions_or_models(monkeypatch):
    from cycling_workshop.app import create_app
    from cycling_workshop.db.base import Base
    from cycling_workshop.identity.roles import CAPABILITIES, LEGACY_WILDCARD_CAPABILITIES
    from cycling_workshop.settings import Settings

    monkeypatch.setenv("OCWP_M2_ENABLED", "true")
    monkeypatch.setenv("OCWP_CONNECTOR_ENABLED", "true")
    production = create_app(Settings(environment="test"))
    assert PATH not in production.openapi()["paths"]
    assert not any("catalogue" in value or "connector" in value for value in CAPABILITIES)
    assert not any(
        "catalogue" in value or "connector" in value for value in LEGACY_WILDCARD_CAPABILITIES
    )
    assert not any(name.startswith("m2_") for name in Base.metadata.tables)
    with TestClient(production) as client:
        response = client.get(PATH)
    assert response.status_code == 404


def test_unexpected_materialization_failure_has_no_partial_body_or_error_detail(lab, monkeypatch):
    from contextlib import contextmanager

    authority, _, client = lab
    original = authority.read

    @contextmanager
    def fails_after_materialization(authorization):
        with original(authorization) as admitted:
            yield admitted
            raise RuntimeError("synthetic-error-canary")

    monkeypatch.setattr(authority, "read", fails_after_materialization)
    response = client.get(PATH)
    assert response.status_code == 503
    assert response.json() == {"detail": "laboratory request refused"}
    assert "synthetic-error-canary" not in response.text
