"""FastAPI application. Run with:  uvicorn app.main:app --reload  (from the backend folder)."""

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.actions import router as actions_router
from app.api.v1.agent_registry import router as agents_router
from app.api.v1.agent_runs import router as agent_runs_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.auth import router as auth_router
from app.api.v1.evaluations import router as evaluations_router
from app.api.v1.executions import router as executions_router
from app.api.v1.governance_decisions import router as decisions_router
from app.api.v1.policies import router as policies_router
from app.api.v1.risk import router as risk_router
from app.api.v1.risk_models import router as risk_models_router
from app.api.v1.system import router as system_router
from app.api.v1.tools import router as tools_router
from app.api.v1.traces import router as traces_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.error_handlers import register_error_handlers
from app.core.version import APP_VERSION
from app.dependencies.auth import get_current_actor
from app.services.background import start_background_tasks, stop_background_tasks


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the approval sweeper and the execution reconciler with the server, and stop them with it."""
    handle = start_background_tasks(get_session_factory())
    try:
        yield
    finally:
        await stop_background_tasks(handle)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agent Governance Platform",
        version=APP_VERSION,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        lifespan=lifespan,
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
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(policies_router, prefix="/api/v1")
    app.include_router(decisions_router, prefix="/api/v1")
    app.include_router(actions_router, prefix="/api/v1")
    app.include_router(approvals_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(audit_events_router, prefix="/api/v1")
    # Student 2's routers. agent_runs checks the login and the role itself. risk and evaluations do not check the
    # login in their own code, so it is required here (fail closed): every request needs a valid token. The role
    # limits of the contract (RSK-01 and EVL-01) still have to be added inside those routers by their owner.
    app.include_router(agent_runs_router, prefix="/api/v1")
    app.include_router(risk_router, prefix="/api/v1", dependencies=[Depends(get_current_actor)])
    app.include_router(risk_models_router, prefix="/api/v1", dependencies=[Depends(get_current_actor)])
    app.include_router(evaluations_router, prefix="/api/v1", dependencies=[Depends(get_current_actor)])
    app.include_router(traces_router)  # router already has /api/v1/traces
    return app


@lru_cache
def _get_app() -> FastAPI:
    return create_app()


def __getattr__(name: str) -> FastAPI:
    """`app.main:app` is built on first use, so importing this module needs no settings."""
    if name == "app":
        return _get_app()
    raise AttributeError(name)
