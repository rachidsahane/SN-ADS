"""Application factory. No business logic here."""

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.middleware import RequestContextMiddleware, RequestGuardMiddleware
from app.api.router import api_router
from app.config import Settings, get_settings
from app.infra.observability import init_observability


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_observability(settings)
    app = FastAPI(
        title="Soro Nua Campaign Predictor API",
        version="1.0.0",
        openapi_url=None if settings.is_production else "/api/openapi.json",
        docs_url=None,
        redoc_url=None,
        redirect_slashes=False,  # a 307 would expose the internal host (api:8000) behind the proxy
    )
    app.state.settings = settings
    register_error_handlers(app)
    app.add_middleware(RequestGuardMiddleware, max_upload_bytes=settings.max_upload_bytes)
    app.add_middleware(RequestContextMiddleware)  # added last = outermost
    app.include_router(api_router)
    return app
