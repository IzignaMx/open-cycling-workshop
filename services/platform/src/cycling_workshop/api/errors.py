from __future__ import annotations

from dataclasses import dataclass

from cycling_workshop.api.middleware import request_id_var
from cycling_workshop.branding.http import branding_path
from cycling_workshop.quotes.http import quote_path
from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, object] | None = None


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if quote_path(request.scope["path"]):
            return JSONResponse(status_code=422, content={"detail": "Invalid quote request"})
        if branding_path(request.url.path):
            # Thousands of unknown small keys can amplify a bounded request into
            # a multi-megabyte validation envelope. This private profile boundary
            # returns one bounded safe diagnostic, without names or image data.
            return JSONResponse(status_code=422, content={"detail": "Invalid branding request"})
        # Pydantic's input/context may contain plaintext credentials, even with
        # SecretStr or hide_input_in_errors. Never serialize or log either.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": error["loc"][:-1]
                        if error["type"] == "extra_forbidden"
                        else error["loc"],
                        "type": error["type"],
                        "msg": "Invalid request value",
                    }
                    for error in exc.errors()
                ]
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> Response:
        if quote_path(request.scope["path"]):
            # Never echo arbitrary exception detail, headers or evidence. Quote
            # routes are still unmounted; a future adapter owns typed errors.
            headers = None
            if exc.status_code == 405:
                allow = next(
                    (value for key, value in (exc.headers or {}).items() if key.lower() == "allow"),
                    "",
                )
                methods = [value.strip() for value in allow.split(",")] if len(allow) <= 128 else []
                standard = {
                    "GET",
                    "HEAD",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "OPTIONS",
                    "TRACE",
                    "CONNECT",
                }
                if methods and all(method in standard for method in methods):
                    # Preserve router method semantics without echoing arbitrary
                    # exception headers or allowing an unbounded header value.
                    headers = {"Allow": ", ".join(dict.fromkeys(methods))}
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": "Quote request refused"},
                headers=headers,
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        del request, exc
        # Driver exceptions can include SQL parameters (including password hashes).
        # Never return or log the exception; correlation identifies the failed call.
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "database_command_failed",
                    "message": "database command failed",
                    "details": {},
                    "request_id": request_id_var.get(),
                }
            },
        )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        if quote_path(request.scope["path"]):
            return JSONResponse(
                status_code=exc.status_code, content={"detail": "Quote request refused"}
            )
        retry = (exc.details or {}).get("retry_after_seconds")
        headers = {"Retry-After": str(retry)} if isinstance(retry, int) and retry > 0 else None
        return JSONResponse(
            headers=headers,
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or {},
                    "request_id": request_id_var.get(),
                }
            },
        )
