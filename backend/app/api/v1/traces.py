"""Authenticated trace search, correlation, metrics and waterfall endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.api.v1.responses import errors
from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.schemas.trace import (
    TraceByActionResponse,
    TraceDetailResponse,
    TraceMetricsResponse,
    TraceSummaryPage,
)
from app.services import trace_service


router = APIRouter(
    prefix="/api/v1/traces",
    tags=["TRC"],
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR))],
)


@router.get("", operation_id="listTraces", response_model=TraceSummaryPage, responses=errors(401, 403, 422, 503))
async def list_traces(
    agent_id: UUID | None = None,
    action_id: UUID | None = None,
    has_error: bool | None = None,
    window_minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort_by: Literal["start_time", "duration_ms"] = "start_time",
    sort_order: Literal["asc", "desc"] = "desc",
):
    end = datetime.now(timezone.utc)
    summaries = await trace_service.find_trace_summaries(
        end - timedelta(minutes=window_minutes), end, limit,
        action_id=str(action_id) if action_id else None,
        agent_id=str(agent_id) if agent_id else None,
    )
    filtered = trace_service._filter_and_sort_trace_summaries(
        summaries, has_error=has_error, window_minutes=window_minutes, now=end,
        sort_by=sort_by, sort_order=sort_order,
    )
    return trace_service._paginate_trace_summaries(filtered, page, page_size)


@router.get(
    "/by-action/{action_id}", operation_id="getTracesByAction", response_model=TraceByActionResponse,
    responses=errors(401, 403, 422, 503),
)
async def get_traces_by_action(action_id: UUID):
    end = datetime.now(timezone.utc)
    summaries = await trace_service.find_trace_summaries(
        end - timedelta(hours=24), end, 200, action_id=str(action_id),
    )
    return trace_service._build_trace_by_action_response(str(action_id), summaries)


@router.get("/metrics", operation_id="getTraceMetrics", response_model=TraceMetricsResponse, responses=errors(401, 403, 422, 503))
async def get_trace_metrics(
    window_minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    bucket_seconds: Annotated[int, Query(ge=1, le=86400)] = 60,
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=window_minutes)
    # Jaeger search returns a bounded sample of recent traces.
    summaries = await trace_service.find_trace_summaries(start, end, 1000)
    return trace_service._generate_trace_metrics(summaries, start, end, bucket_seconds)


@router.get("/{trace_id}", operation_id="getTrace", response_model=TraceDetailResponse, responses=errors(401, 403, 404, 422, 503))
async def get_trace(trace_id: Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]):
    return await trace_service.get_trace_details(trace_id)
