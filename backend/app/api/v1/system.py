"""System endpoints (spec section 11.2). SYS-01 GET /system/health is public; SYS-02 GET /system/info needs a login."""

import logging
from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.enums import HealthStatus, RiskSource
from app.core.version import API_VERSION, APP_VERSION, CONTRACT_VERSION
from app.dependencies.auth import get_current_actor
from app.models.model_version import ModelVersion
from app.schemas import ActorContext, ComponentHealth, HealthResponse, SystemInfoResponse

router = APIRouter(tags=["SYS"])
logger = logging.getLogger("governance.health")


@router.get("/system/health", response_model=HealthResponse, operation_id="getSystemHealth")
async def get_health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    """Always answers 200. A broken database shows up as status DOWN, never as a crash."""
    started = perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        database = ComponentHealth(
            component_name="database",
            status=HealthStatus.OK,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            detail="ok",
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "not reachable"
        # The reason goes to the server log only; the response says just "unreachable".
        logger.warning("Health check: database not reachable (%s: %s)", type(exc).__name__, str(exc)[:200])
        database = ComponentHealth(
            component_name="database", status=HealthStatus.DOWN, latency_ms=None, detail="unreachable"
        )
    overall = HealthStatus.OK if database.status == HealthStatus.OK else HealthStatus.DOWN
    return HealthResponse(
        status=overall,
        version=APP_VERSION,
        checked_at=datetime.now(timezone.utc),
        components=[database],
    )


@router.get("/system/info", response_model=SystemInfoResponse, operation_id="getSystemInfo",
            summary="Build and configuration info")
async def get_system_info(_: ActorContext = Depends(get_current_actor),
                          session: AsyncSession = Depends(get_session)) -> SystemInfoResponse:
    """SYS-02, any logged-in role. The active model is the active ML_MODEL row if there is one; otherwise the
    active heuristic row, and the risk source is then HEURISTIC_FALLBACK. Nothing secret is returned."""
    settings = get_settings()
    active = list((await session.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True)))).scalars())
    ml = next((m for m in active if m.model_kind == RiskSource.ML_MODEL.value), None)
    chosen = ml or next((m for m in active if m.model_kind == RiskSource.HEURISTIC_FALLBACK.value), None)
    return SystemInfoResponse(
        app_version=APP_VERSION, contract_version=CONTRACT_VERSION, api_version=API_VERSION,
        environment=settings.app_env, active_model_version=chosen.model_version if chosen else None,
        active_risk_source=RiskSource.ML_MODEL if ml else RiskSource.HEURISTIC_FALLBACK,
        approval_ttl_seconds=settings.approval_ttl_seconds, risk_threshold_medium=settings.risk_threshold_medium,
        risk_threshold_high=settings.risk_threshold_high, risk_threshold_critical=settings.risk_threshold_critical)
