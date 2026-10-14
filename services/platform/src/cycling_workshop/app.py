from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint

from cycling_workshop import __version__
from cycling_workshop.api.errors import install_error_handlers
from cycling_workshop.api.middleware import configure_logging, install_request_context
from cycling_workshop.api.schemas import HealthReadyResponse, HealthUnavailableResponse
from cycling_workshop.bicycles.router import router as bicycles_router
from cycling_workshop.branding.http import BrandingBodyLimit, branding_path
from cycling_workshop.branding.router import router as branding_router
from cycling_workshop.customers.router import router as customers_router
from cycling_workshop.db.registry import register_models
from cycling_workshop.identity.admin_router import router as administration_router
from cycling_workshop.identity.context import router as context_router
from cycling_workshop.identity.router import router as identity_router
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.inventory.router import router as inventory_router
from cycling_workshop.service_orders.router import router as service_orders_router
from cycling_workshop.settings import Settings
from cycling_workshop.sync.baseline_codec import BaselineCodec
from cycling_workshop.sync.baseline_http import BaselineBodyLimit, baseline_path
from cycling_workshop.sync.baseline_router import router as baseline_router
from cycling_workshop.sync.proof import MutationBodyProofMiddleware
from cycling_workshop.sync.router import router as sync_router


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    register_models()
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Open Cycling Workshop Platform API",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.session_tokens = SessionTokenService(secret=settings.auth_secret)
    app.state.baseline_codec = BaselineCodec(settings.auth_secret)
    app.add_middleware(BrandingBodyLimit)
    app.add_middleware(BaselineBodyLimit)
    app.add_middleware(MutationBodyProofMiddleware)
    install_error_handlers(app)

    @app.get("/health/live", tags=["health"])
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/health/ready",
        tags=["health"],
        response_model=HealthReadyResponse,
        responses={503: {"model": HealthUnavailableResponse}},
    )
    async def health_ready() -> HealthReadyResponse | JSONResponse:
        factory = app.state.session_factory
        if factory is None:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        try:
            with factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return HealthReadyResponse(environment=settings.environment)

    @app.middleware("http")
    async def private_no_store(request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path.rstrip("/")
        is_context = path == "/api/v1/auth/context" or baseline_path(request.url.path)
        is_private = (
            is_context
            or path
            in {
                "/api/v1/auth/login",
                "/api/v1/auth/me",
                "/api/v1/auth/logout-all",
                "/api/v1/auth/change-password",
                "/api/v1/admin",
                "/api/v1/locations",
                "/api/v1/sync/mutations",
            }
            or path.startswith("/api/v1/admin/")
            or path.startswith("/api/v2/admin/")
            or branding_path(request.url.path)
            or (
                path.startswith("/api/v1/service-orders/")
                and len(path.split("/")) == 6
                and path.endswith("/events")
            )
        )
        try:
            response = await call_next(request)
        except Exception:
            if not is_private:
                raise
            # Keep unexpected failures generic, without leaking driver/session
            # details or allowing caches to retain a private response.
            logging.getLogger(__name__).error(
                "authenticated context request failed" if is_context else "identity request failed"
            )
            response = JSONResponse(status_code=500, content={"detail": "internal server error"})
        if is_private:
            response.headers["Cache-Control"] = "no-store"
        return response

    install_request_context(app)
    app.include_router(baseline_router)
    app.include_router(context_router)
    app.include_router(identity_router)
    app.include_router(administration_router)
    app.include_router(branding_router)
    app.include_router(customers_router)
    app.include_router(bicycles_router)
    app.include_router(service_orders_router)
    app.include_router(sync_router)
    app.include_router(inventory_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("cycling_workshop.runtime:app", host="0.0.0.0", port=8000, reload=False)
