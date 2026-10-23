"""Student 3 FastAPI router: TRC-01 to TRC-04 trace endpoints.

Contract: OpenAPI v1.0.0
Routes registered (static before dynamic):
  GET /api/v1/traces                        -> TRC-01  listTraces
  GET /api/v1/traces/by-action/{action_id}  -> TRC-02  getTracesByAction
  GET /api/v1/traces/metrics                -> TRC-03  getTraceMetrics
  GET /api/v1/traces/{trace_id}             -> TRC-04  getTrace

Error mappings
  TraceQueryUnavailable  -> 503 TELEMETRY_UNAVAILABLE
  trace_id not found     -> 404 TRACE_NOT_FOUND
  Invalid trace_id fmt   -> 422 VALIDATION_ERROR
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Optional

try:
    from fastapi import APIRouter, Query
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    raise

from backend.app.observability.trace_query_client import TraceQueryUnavailable
from backend.app.services.trace_service import (
    _is_valid_trace_id,
    _is_valid_uuid,
)


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

def _telemetry_unavailable(detail: str = "Telemetry service is unavailable.") -> JSONResponse:
    """Return a canonical 503 TELEMETRY_UNAVAILABLE response."""
    return JSONResponse(
        status_code=503,
        content={"error_code": "TELEMETRY_UNAVAILABLE", "detail": detail},
    )


def _trace_not_found(trace_id: str) -> JSONResponse:
    """Return a canonical 404 TRACE_NOT_FOUND response."""
    return JSONResponse(
        status_code=404,
        content={
            "error_code": "TRACE_NOT_FOUND",
            "detail": f"Trace '{trace_id}' was not found in telemetry.",
        },
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/traces", tags=["TRC"])


# TRC-01 - listTraces
@router.get("", operation_id="listTraces", summary="Paginated trace list")
async def list_traces(
    agent_id: Annotated[Optional[str], Query(description="Filter by agent UUID")] = None,
    action_id: Annotated[Optional[str], Query(description="Filter by action UUID")] = None,
    has_error: Annotated[Optional[bool], Query(description="Filter by error presence")] = None,
    window_minutes: Annotated[
        Optional[int], Query(description="Sliding time window (max 1440)", ge=1, le=1440)
    ] = 60,
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort_by: Annotated[Optional[str], Query(description="start_time or duration_ms")] = "start_time",
    sort_order: Annotated[Optional[str], Query()] = "desc",
) -> Any:
    """TRC-01 - Paginated, filtered list of trace summaries from Jaeger.

    Returns 503 TELEMETRY_UNAVAILABLE while the Jaeger adapter is not
    yet connected.  No synthetic data is emitted.
    """
    return _telemetry_unavailable(
        "Trace list is temporarily unavailable while the telemetry adapter is initialising."
    )


# TRC-02 - getTracesByAction (static, must precede /{trace_id})
@router.get(
    "/by-action/{action_id}",
    operation_id="getTracesByAction",
    summary="Traces linked to an action",
)
async def get_traces_by_action(action_id: str) -> Any:
    """TRC-02 - All traces associated with a specific action_id UUID.

    Returns 422 when action_id is not a valid UUID.
    Returns 503 TELEMETRY_UNAVAILABLE while Jaeger is not connected.
    """
    if not _is_valid_uuid(action_id):
        return JSONResponse(
            status_code=422,
            content={"error_code": "VALIDATION_ERROR", "detail": "action_id must be a valid UUID."},
        )
    return _telemetry_unavailable("Trace-by-action lookup is temporarily unavailable.")


# TRC-03 - getTraceMetrics (static, must precede /{trace_id})
@router.get(
    "/metrics",
    operation_id="getTraceMetrics",
    summary="Latency series derived from traces",
)
async def get_trace_metrics(
    window_minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    bucket_seconds: Annotated[int, Query(ge=1, le=86400)] = 60,
) -> Any:
    """TRC-03 - Time-bucketed p50/p95 latency series for the trace explorer.

    Returns 503 TELEMETRY_UNAVAILABLE while Jaeger is not connected.
    """
    return _telemetry_unavailable(
        "Trace metrics are temporarily unavailable while the telemetry adapter is initialising."
    )


# TRC-04 - getTrace (dynamic, must be last)
@router.get(
    "/{trace_id}",
    operation_id="getTrace",
    summary="Full trace detail with span waterfall",
)
async def get_trace(trace_id: str) -> Any:
    """TRC-04 - Full span waterfall for a 32-hex-character trace_id.

    Status codes:
      200  TraceDetailResponse
      404  TRACE_NOT_FOUND   (trace_id unknown to Jaeger)
      422  VALIDATION_ERROR  (malformed trace_id)
      503  TELEMETRY_UNAVAILABLE (Jaeger unreachable)
    """
    if not _is_valid_trace_id(trace_id):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "detail": "trace_id must be 32 lowercase hexadecimal characters.",
            },
        )

    try:
        from backend.app.services.trace_service import get_trace_details
        result = await get_trace_details(trace_id)
        return result
    except TraceQueryUnavailable as exc:
        return _telemetry_unavailable(str(exc))
    except ValueError:
        return _trace_not_found(trace_id)
    except RuntimeError as exc:
        # get_trace_details raises RuntimeError until Jaeger adapter is verified.
        return _telemetry_unavailable(str(exc))
