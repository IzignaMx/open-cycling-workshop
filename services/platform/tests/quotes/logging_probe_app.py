"""Disposable actual-Uvicorn fixtures; never mounted in the production app."""

from cycling_workshop.api.errors import ApiError
from cycling_workshop.app import create_app
from fastapi import HTTPException, Request

app = create_app()


@app.get("/api/v1/quotes/_logging/{kind}")
@app.get("/api/v1/service-orders/{order}/quotes/_logging/{kind}")
def probe(request: Request, kind: str, order: str = "") -> dict[str, str]:
    del order
    if kind == "internal":
        raise RuntimeError("private-quote-exception-canary")
    if kind == "http":
        raise HTTPException(403, {"private-quote-exception-canary": "evidence"})
    if kind == "api":
        raise ApiError(409, "private-quote-exception-canary", "evidence")
    return {"query": request.scope["query_string"].decode("ascii")}


@app.get("/api/v1/quotes-other")
def unrelated(request: Request) -> dict[str, str]:
    return {"query": request.scope["query_string"].decode("ascii")}
