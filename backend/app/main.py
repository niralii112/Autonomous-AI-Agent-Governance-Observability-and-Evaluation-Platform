"""FastAPI application. Run with:  uvicorn app.main:app --reload  (from the backend folder)."""

from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.system import router as system_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.version import APP_VERSION


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agent Governance Platform",
        version=APP_VERSION,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,  # only CORS_ALLOWED_ORIGINS
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    return app


@lru_cache
def _get_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    """`app.main:app` is built on first use, so importing this module needs no settings."""
    if name == "app":
        return _get_app()
    raise AttributeError(name)
