"""System endpoints. SYS-01 GET /api/v1/system/health is public (spec section 11.2)."""

import logging
from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.enums import HealthStatus
from app.core.version import APP_VERSION
from app.schemas import ComponentHealth, HealthResponse

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
