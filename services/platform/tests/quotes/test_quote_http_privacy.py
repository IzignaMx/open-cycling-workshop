"""Private namespaces stay closed without exposing quote business routes."""

from __future__ import annotations

import logging

import pytest
from cycling_workshop.api.errors import ApiError
from cycling_workshop.app import create_app
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

CANARY = "private-quote-request-canary"
ROOTS = ("/api/v1/quotes", "/api/v1/service-orders/order-a/quotes")


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize("suffix", ["", "/", "/missing", "//missing", "/id/authorize"])
def test_unmounted_quote_namespace_is_private(root: str, suffix: str) -> None:
    client = TestClient(create_app())
    path = root + suffix
    first = client.get(path, headers={"X-Request-ID": CANARY})
    second = client.post(path, headers={"X-Request-ID": CANARY}, json={"note": CANARY})
    for response in (first, second):
        assert response.status_code == 404
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers["x-request-id"].startswith("req-")
        assert CANARY not in response.text + str(response.headers)
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize("status", [200, 401, 403, 405, 422, 500, 503])
def test_quote_status_errors_are_closed_and_private(
    root: str, status: int, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app()
    monkeypatch.setattr(logging.getLogger("cycling_workshop.app"), "disabled", False)

    @app.get(root + "/test-only")
    def endpoint() -> dict[str, bool]:
        if status == 500:
            raise RuntimeError(CANARY)
        if status == 503:
            raise SQLAlchemyError(CANARY)
        if status != 200:
            raise HTTPException(status, detail={CANARY: CANARY * 10000})
        return {"ok": True}

    with caplog.at_level(logging.ERROR):
        response = TestClient(app).get(root + "/test-only", headers={"X-Request-ID": CANARY})
    assert response.status_code == status
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert len(response.content) <= 8192
    assert CANARY not in response.text + str(response.headers) + caplog.text
    assert all(record.exc_info is None for record in caplog.records)


class ClosedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int


@pytest.mark.parametrize("root", ROOTS)
def test_quote_validation_error_count_and_locations_are_not_reflected(root: str) -> None:
    app = create_app()

    @app.post(root + "/test-only")
    def endpoint(body: ClosedInput) -> dict[str, int]:
        return {"count": body.count}

    response = TestClient(app).post(
        root + "/test-only", json={f"{CANARY}{n}": CANARY for n in range(1000)}
    )
    assert response.status_code == 422
    assert len(response.content) <= 8192
    assert CANARY not in response.text
    assert response.headers.get("cache-control") == "no-store"


@pytest.mark.parametrize("root", ROOTS)
def test_quote_api_error_never_reflects_arbitrary_internal_context(root: str) -> None:
    app = create_app()

    @app.get(root + "/test-only")
    def endpoint() -> None:
        raise ApiError(409, CANARY, CANARY, {CANARY: CANARY * 10000})

    response = TestClient(app).get(root + "/test-only")
    assert response.status_code == 409
    assert len(response.content) <= 8192
    assert CANARY not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/quotes-other",
        "/api/v1/quotesish/x",
        "/api/v1/service-orders/a/quotes-other",
        "/api/v1/service-orders/a/quote",
        "/api/v1/service-orders/a/b/quotes",
        "/other",
    ],
)
def test_unrelated_namespaces_keep_existing_behavior(path: str) -> None:
    app = create_app()

    @app.get(path)
    def endpoint(request: Request) -> dict[str, str]:
        return {"query": request.scope["query_string"].decode("ascii")}

    response = TestClient(app).get(path + "?note=" + CANARY, headers={"X-Request-ID": CANARY})
    assert response.json() == {"query": "note=" + CANARY}
    assert response.headers["x-request-id"] == CANARY
    assert "cache-control" not in response.headers


def test_quote_routes_are_absent_from_production_openapi() -> None:
    paths = create_app().openapi()["paths"]
    assert not any("/quotes" in path for path in paths)


@pytest.mark.parametrize("root", ROOTS)
def test_router_generated_method_refusal_is_private(root: str) -> None:
    app = create_app()

    @app.get(root + "/test-only")
    def endpoint() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).post(root + "/test-only", headers={"X-Request-ID": CANARY})
    assert response.status_code == 405
    assert response.headers.get("allow") == "GET"
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert len(response.content) <= 8192
    assert CANARY not in response.text + str(response.headers)


def test_nonquote_http_exception_body_and_headers_are_unchanged() -> None:
    app = create_app()

    @app.get("/public-error")
    def endpoint() -> None:
        raise HTTPException(409, detail={"reason": CANARY}, headers={"X-Example": CANARY})

    response = TestClient(app).get("/public-error", headers={"X-Request-ID": CANARY})
    assert response.status_code == 409
    assert response.json() == {"detail": {"reason": CANARY}}
    assert response.headers["x-example"] == CANARY
    assert response.headers["x-request-id"] == CANARY
    assert "cache-control" not in response.headers


@pytest.mark.parametrize("order", ["order%3Fa", "order%23a", "order%20a"])
def test_quote_privacy_uses_asgi_path_not_reparsed_url_components(order: str) -> None:
    response = TestClient(create_app()).get(
        f"/api/v1/service-orders/{order}/quotes", headers={"X-Request-ID": CANARY}
    )
    assert response.status_code == 404
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers["x-request-id"].startswith("req-")
    assert CANARY not in response.text + str(response.headers)


@pytest.mark.parametrize(
    "allow", [CANARY, "GET, " + CANARY, "GET," * 100, "GET\r\nX-Secret: " + CANARY]
)
def test_quote_method_refusal_never_reflects_untrusted_allow(allow: str) -> None:
    app = create_app()

    @app.get("/api/v1/quotes/test-only")
    def endpoint() -> None:
        raise HTTPException(405, CANARY, headers={"Allow": allow, "X-Secret": CANARY})

    response = TestClient(app).get("/api/v1/quotes/test-only")
    assert response.status_code == 405
    assert "allow" not in response.headers
    assert CANARY not in response.text + str(response.headers)
