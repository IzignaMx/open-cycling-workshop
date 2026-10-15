"""The inventory HTTP namespace must stay private on every response path."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from services.platform.tests.inventory.test_inventory_api import InventoryAPI
from services.platform.tests.inventory.test_inventory_api import (
    inventory_api as inventory_api_fixture,
)

ROOT = "/api/v1/inventory"
CANARY = "private-inventory-http-canary"


@pytest.fixture
def privacy_api() -> Iterator[InventoryAPI]:
    yield from inventory_api_fixture.__wrapped__()


@pytest.mark.parametrize("path", [ROOT, ROOT + "/", ROOT + "/missing", ROOT + "//missing"])
def test_unknown_inventory_namespace_is_no_store(privacy_api: InventoryAPI, path: str) -> None:
    response = privacy_api.client().get(path)
    assert response.status_code == 404
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("status", [200, 401, 403, 422, 503])
def test_existing_inventory_statuses_are_no_store(privacy_api: InventoryAPI, status: int) -> None:
    client = privacy_api.client(capabilities=[] if status == 403 else None)
    params = {"location_id": "loc-1", "limit": "1"}
    if status == 401:
        client.headers.pop("Authorization")
    elif status == 422:
        params["limit"] = CANARY
    elif status == 503:

        @client.app.get(ROOT + "/database-error")
        def database_error() -> None:
            raise SQLAlchemyError(CANARY)

    path = ROOT + ("/database-error" if status == 503 else "/products")
    response = client.get(path, params=params)
    assert response.status_code == status, response.text
    assert response.headers.get("cache-control") == "no-store"
    assert CANARY not in response.text


def test_private_inventory_error_retains_safe_context_only(
    privacy_api: InventoryAPI, caplog: pytest.LogCaptureFixture
) -> None:
    client = privacy_api.client()

    @client.app.get(ROOT + "/internal-error")
    def internal_error() -> None:
        raise RuntimeError("driver parameter " + CANARY)

    with caplog.at_level(logging.ERROR):
        response = client.get(ROOT + "/internal-error", headers={"X-Request-ID": CANARY})
    assert response.status_code == 500
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert "server-timing" in response.headers
    assert CANARY not in response.text + str(response.headers) + caplog.text
    assert "inventory request failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert ROOT + "/internal-error" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("path", [ROOT, ROOT + "/", ROOT + "/products"])
def test_inventory_request_ids_cannot_contain_client_text(
    privacy_api: InventoryAPI, path: str
) -> None:
    response = privacy_api.client().get(path, headers={"X-Request-ID": CANARY})
    assert response.headers["x-request-id"].startswith("req-")
    assert CANARY not in str(response.headers) + response.text


@pytest.mark.parametrize("path", [ROOT + "-other", ROOT + "ish/products", "/other"])
def test_unrelated_namespace_keeps_existing_behavior(privacy_api: InventoryAPI, path: str) -> None:
    client = privacy_api.client()

    @client.app.get(path)
    def unrelated(request: Request) -> dict[str, str]:
        return {"query": request.scope["query_string"].decode("ascii")}

    response = client.get(path + "?before=" + CANARY, headers={"X-Request-ID": CANARY})
    assert response.status_code == 200
    assert "cache-control" not in response.headers
    assert response.headers["x-request-id"] == CANARY
    assert response.json() == {"query": "before=" + CANARY}
