"""Disposable real-Uvicorn fixture; no production routes or accounts are added."""

from __future__ import annotations

from cycling_workshop.api.errors import ApiError
from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError

from services.platform.tests.inventory.test_inventory_api import inventory_api

_fixture = inventory_api.__wrapped__()
_api = next(_fixture)
app = _api.client().app


@app.get("/api/v1/inventory/_logging/internal-error")
def internal_error() -> None:
    raise RuntimeError("private-driver-error-canary")


@app.get("/api/v1/inventory/_logging/database-error")
def database_error() -> None:
    raise SQLAlchemyError("private-sql-parameter-canary")


@app.get("/api/v1/inventory/_logging/budget-error")
def budget_error() -> None:
    raise ApiError(503, "inventory_read_unavailable", "inventory read unavailable")


@app.get("/api/v1/inventory/_logging/scope")
def query_scope(request: Request) -> dict[str, str]:
    return {"query": request.scope["query_string"].decode("ascii")}


@app.get("/api/v1/inventory-other")
def unrelated(request: Request) -> dict[str, str]:
    return {"query": request.scope["query_string"].decode("ascii")}
