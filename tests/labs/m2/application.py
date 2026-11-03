"""Functional ASGI laboratory; no listener, production route or execution switch.

Application limits are not transport/parser, TLS or process-isolation evidence.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qsl
from weakref import WeakKeyDictionary

from cycling_workshop.inventory.models import ProductRecord
from fastapi import FastAPI, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tests.labs.m2.authority import LabAuthority, LabDenied

PATH = "/api/v1/connector-catalogue/products"
PRIVATE = {"Cache-Control": "private, no-store"}


def refused(status: int) -> JSONResponse:
    return JSONResponse(
        {"detail": "laboratory request refused"}, status_code=status, headers=PRIVATE
    )


@dataclass
class RequestBudget:
    requests: int = 0
    failures: int = 0
    lock: Lock = field(default_factory=Lock)
    active: BoundedSemaphore = field(default_factory=lambda: BoundedSemaphore(2))

    def admit(self) -> bool:
        with self.lock:
            if self.requests >= 120 or self.failures >= 20:
                return False
            self.requests += 1
            return True

    def failed_auth(self) -> None:
        with self.lock:
            self.failures += 1


_BUDGETS: WeakKeyDictionary[LabAuthority, RequestBudget] = WeakKeyDictionary()
_BUDGET_LOCK = Lock()


def budget_for(authority: LabAuthority) -> RequestBudget:
    with _BUDGET_LOCK:
        if authority not in _BUDGETS:
            _BUDGETS[authority] = RequestBudget()
        return _BUDGETS[authority]


class Boundary:
    def __init__(self, app: ASGIApp, budget: RequestBudget) -> None:
        self.app = app
        self.budget = budget

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def private_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in (b"cache-control", b"etag")
                ]
                message = {
                    **message,
                    "headers": [*headers, (b"cache-control", b"private, no-store")],
                }
            await send(message)

        if not self.budget.admit() or not self.budget.active.acquire(blocking=False):
            await refused(429)(scope, receive, private_send)
            return
        try:
            headers = scope.get("headers", [])
            if (
                sum(len(k) + len(v) for k, v in headers) > 8192
                or len(scope.get("query_string", b"")) > 1024
            ):
                await refused(413)(scope, receive, private_send)
                return
            # ASGI payload cap only: transport/parser limits remain an execution gate.
            try:
                first = await asyncio.wait_for(receive(), timeout=2)
            except TimeoutError:
                await refused(408)(scope, receive, private_send)
                return
            if first["type"] != "http.request":
                return
            if first.get("body") or first.get("more_body"):
                await refused(413)(scope, receive, private_send)
                return

            async def empty_receive() -> Message:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def count_send(message: Message) -> None:
                if message["type"] == "http.response.start" and message["status"] == 401:
                    self.budget.failed_auth()
                await private_send(message)

            await self.app(scope, empty_receive, count_send)
        finally:
            self.budget.active.release()


def query_window(raw: bytes) -> tuple[int, int]:
    try:
        pairs = parse_qsl(
            raw.decode("ascii"),
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=2,
            errors="strict",
        )
    except (ValueError, UnicodeError) as exc:
        raise LabDenied(422) from exc
    values: dict[str, int] = {}
    for key, value in pairs:
        if (
            key not in ("limit", "offset")
            or key in values
            or not value.isascii()
            or not value.isdecimal()
        ):
            raise LabDenied(422)
        if len(value) > 3:
            raise LabDenied(422)
        values[key] = int(value)
    limit, offset = values.get("limit", 25), values.get("offset", 0)
    if not 1 <= limit <= 50 or not 0 <= offset <= 200:
        raise LabDenied(422)
    return limit, offset


def create_lab_app(authority: LabAuthority) -> FastAPI:
    """Only supplied fixture authority; no settings/env/DSN or production mounting."""
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.add_middleware(Boundary, budget=budget_for(authority))

    @app.get(PATH)
    def catalogue(request: Request) -> JSONResponse:
        try:
            values = request.headers.getlist("authorization")
            if len(values) != 1 or len(values[0]) > 128:
                raise LabDenied(401)
            with authority.read(values[0]) as (machine, session):
                limit, offset = query_window(request.scope.get("query_string", b""))
                products = session.scalars(
                    select(ProductRecord)
                    .where(
                        ProductRecord.organization_id == machine.organization_id,
                        ProductRecord.location_id == machine.location_id,
                    )
                    .order_by(ProductRecord.id)
                    .offset(offset)
                    .limit(limit + 1)
                ).all()
                items = [
                    {
                        "product_id": row.id,
                        "sku": row.sku,
                        "name": row.name,
                        "unit": row.unit,
                        "version": row.version,
                    }
                    for row in products[:limit]
                ]
                next_offset = (
                    offset + limit if len(products) > limit and offset + limit <= 200 else None
                )
                response = JSONResponse(
                    {"items": items, "next_offset": next_offset}, headers=PRIVATE
                )
                if len(response.body) > 65536:
                    raise LabDenied(503)
            # Full serialization and authority cleanup have completed before any send.
            return response
        except LabDenied as exc:
            return refused(exc.status)
        except (SQLAlchemyError, ValueError, TypeError):
            return refused(503)

    return app
