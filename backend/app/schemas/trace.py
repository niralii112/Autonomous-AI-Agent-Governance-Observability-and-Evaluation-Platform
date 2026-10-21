"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.trace
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    SpanStatus,
)


class SpanDetail(BaseModel):
    """One span; attributes contain only allow-listed gov.* keys plus standard http.* keys."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    span_id: str
    parent_span_id: str | None
    span_name: str
    service_name: str
    start_time: datetime
    duration_ms: float
    status: SpanStatus
    attributes: dict[str, Any]


class TraceSummary(BaseModel):
    """Trace list row."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    trace_id: str
    root_span_name: str
    service_name: str
    start_time: datetime
    duration_ms: float
    span_count: int
    error_count: int
    action_id: UUID | None
    agent_id: UUID | None


class TraceByActionResponse(BaseModel):
    """Traces linked to an action."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID
    traces: list[TraceSummary]


class TraceDetailResponse(BaseModel):
    """Full trace."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    trace_id: str
    start_time: datetime
    duration_ms: float
    span_count: int
    error_count: int
    spans: list[SpanDetail]


class TraceMetricsBucket(BaseModel):
    """Latency bucket derived from traces."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    bucket_start: datetime
    request_count: int
    error_count: int
    p50_ms: float | None
    p95_ms: float | None


class TraceMetricsResponse(BaseModel):
    """Latency series."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    window_start: datetime
    window_end: datetime
    bucket_seconds: int
    buckets: list[TraceMetricsBucket]


class TraceSummaryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[TraceSummary]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
