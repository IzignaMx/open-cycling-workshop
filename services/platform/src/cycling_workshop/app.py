from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from cycling_workshop import __version__
from cycling_workshop.api.errors import install_error_handlers
from cycling_workshop.api.middleware import configure_logging, install_request_context
from cycling_workshop.api.schemas import HealthReadyResponse, HealthUnavailableResponse
from cycling_workshop.customers.router import router as customers_router
from cycling_workshop.db.registry import register_models
from cycling_workshop.identity.router import router as identity_router
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.settings import Settings
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
    install_request_context(app)
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

    app.include_router(identity_router)
    app.include_router(customers_router)
    app.include_router(sync_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("cycling_workshop.runtime:app", host="0.0.0.0", port=8000, reload=False)
