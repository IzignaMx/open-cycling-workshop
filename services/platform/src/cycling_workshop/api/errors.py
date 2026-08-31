from __future__ import annotations

from dataclasses import dataclass

from cycling_workshop.api.middleware import request_id_var
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, object] | None = None


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        del request
        return JSONResponse(
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
