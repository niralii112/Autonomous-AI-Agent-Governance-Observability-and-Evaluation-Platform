"""Student 3 trace service: backend-independent helpers.

Contract: OpenAPI v1.0.0
Master specification: sections 9.7, 12.16 and 16.4.

The canonical get_trace_details service will be added when the
shared schemas and AppError implementation are available.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


_TRACE_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)


def _is_valid_uuid(value: object) -> bool:
    """Validate standard RFC 4122 UUID string format."""
    return isinstance(value, str) and _UUID_PATTERN.fullmatch(value) is not None

# Exact gov.* attribute allow-list from master specification 9.7.
_ALLOWED_GOV_ATTRIBUTES = frozenset(
    {
        "gov.action_id",
        "gov.agent_id",
        "gov.execution_id",
        "gov.approval_id",
        "gov.user_id",
        "gov.action_type",
        "gov.tool_name",
        "gov.policy_result",
        "gov.final_decision",
        "gov.decision_rule_id",
        "gov.risk_score",
        "gov.risk_level",
        "gov.risk_source",
        "gov.model_version",
        "gov.approval_status",
        "gov.execution_status",
        "gov.attempt_number",
        "gov.error_code",
        "gov.evaluation_type",
        "gov.sample_size",
    }
)


def _is_valid_trace_id(trace_id: object) -> bool:
    """Recognize exactly 32 lowercase hexadecimal characters."""
    return (
        isinstance(trace_id, str)
        and _TRACE_ID_PATTERN.fullmatch(trace_id) is not None
    )


_ALLOWED_HTTP_ATTRIBUTES = frozenset(
    {
        "http.method",
        "http.status_code",
    }
)


def _filter_span_attributes(
    attributes: Mapping[str, Any],
) -> dict[str, Any]:
    """Return only explicitly approved trace attributes.

    HTTP header values and unknown attributes are excluded.
    The original input mapping is not modified.
    """
    return {
        key: value
        for key, value in attributes.items()
        if isinstance(key, str)
        and (
            key in _ALLOWED_GOV_ATTRIBUTES
            or key in _ALLOWED_HTTP_ATTRIBUTES
        )
    }


def _sanitize_span(
    span: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a copy of a canonical span with filtered attributes."""
    result = dict(span)
    attributes = result.get("attributes")

    if isinstance(attributes, Mapping):
        result["attributes"] = _filter_span_attributes(attributes)
    else:
        result["attributes"] = {}

    return result


def _parse_start_time(value: str) -> datetime:
    """Parse an ISO-8601 timestamp for chronological ordering."""
    if not isinstance(value, str):
        raise ValueError("Span start_time must be a string")

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Span start_time must include a timezone")

    return parsed


def _sanitize_and_sort_spans(
    spans: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Sort canonical spans by start_time and filter attributes."""
    return [
        _sanitize_span(span)
        for span in sorted(
            spans,
            key=lambda span: _parse_start_time(span["start_time"]),
        )
    ]


def _build_trace_detail(
    trace_id: str,
    start_time: str,
    duration_ms: float,
    spans: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the exact OpenAPI TraceDetailResponse field structure.

    Input spans must already be normalized to SpanDetail fields.
    Jaeger-specific decoding belongs only in trace_query_client.py.

    This helper returns plain data. Student 1's Pydantic response
    model will validate the final public service response.
    """
    if not _is_valid_trace_id(trace_id):
        raise ValueError("Invalid OpenTelemetry trace_id")

    _parse_start_time(start_time)

    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, (int, float))
        or not (0 <= duration_ms < float("inf"))
    ):
        raise ValueError("Invalid trace duration")

    if not isinstance(spans, list) or not spans:
        raise ValueError("Trace must contain at least one span")

    required = {
        "span_id",
        "parent_span_id",
        "span_name",
        "service_name",
        "start_time",
        "duration_ms",
        "status",
        "attributes",
    }

    normalized = []

    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError("Invalid span")

        if set(span.keys()) != required:
            raise ValueError("Span fields do not match SpanDetail")

        if span["status"] not in ("OK", "ERROR", "UNSET"):
            raise ValueError("Invalid span status")

        span_duration = span["duration_ms"]

        if (
            isinstance(span_duration, bool)
            or not isinstance(span_duration, (int, float))
            or not (0 <= span_duration < float("inf"))
        ):
            raise ValueError("Invalid span duration")

        if not isinstance(span["attributes"], Mapping):
            raise ValueError("Invalid span attributes")

        normalized.append(span)

    ordered = _sanitize_and_sort_spans(normalized)

    return {
        "trace_id": trace_id,
        "start_time": start_time,
        "duration_ms": duration_ms,
        "span_count": len(ordered),
        "error_count": sum(
            span["status"] == "ERROR" for span in ordered
        ),
        "spans": ordered,
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    """Calculate a linearly interpolated percentile."""
    if not 0 <= percentile <= 100:
        raise ValueError("Percentile must be between 0 and 100")

    if not values:
        return None

    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not (0 <= value < float("inf"))
        for value in values
    ):
        raise ValueError("Invalid percentile input")

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower

    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _paginate_trace_summaries(
    summaries: list[Mapping[str, Any]],
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Build the canonical TraceSummaryPage structure."""
    if (
        isinstance(page, bool)
        or isinstance(page_size, bool)
        or not isinstance(page, int)
        or not isinstance(page_size, int)
        or page < 1
        or not 1 <= page_size <= 100
    ):
        raise ValueError("Invalid pagination parameters")

    total_items = len(summaries)
    total_pages = (total_items + page_size - 1) // page_size

    start = (page - 1) * page_size

    return {
        "items": list(summaries[start:start + page_size]),
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def _build_trace_metrics_bucket(
    bucket_start: str,
    durations_ms: list[float],
    error_count: int,
) -> dict[str, Any]:
    """Build the canonical TraceMetricsBucket structure."""
    _parse_start_time(bucket_start)

    if (
        isinstance(error_count, bool)
        or not isinstance(error_count, int)
        or error_count < 0
        or error_count > len(durations_ms)
    ):
        raise ValueError("Invalid error count")

    if any(
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not (0 <= duration < float("inf"))
        for duration in durations_ms
    ):
        raise ValueError("Invalid duration")

    return {
        "bucket_start": bucket_start,
        "request_count": len(durations_ms),
        "error_count": error_count,
        "p50_ms": _percentile(durations_ms, 50),
        "p95_ms": _percentile(durations_ms, 95),
    }


def _build_trace_summary(
    trace_id: str,
    root_span_name: str,
    service_name: str,
    start_time: str,
    duration_ms: float | int,
    span_count: int,
    error_count: int,
    action_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Build the exact OpenAPI TraceSummary field structure."""
    if not _is_valid_trace_id(trace_id):
        raise ValueError("Invalid OpenTelemetry trace_id: must be 32 lowercase hex characters")

    if not isinstance(root_span_name, str) or not root_span_name.strip():
        raise ValueError("root_span_name must be a non-empty string")

    if not isinstance(service_name, str) or not service_name.strip():
        raise ValueError("service_name must be a non-empty string")

    _parse_start_time(start_time)

    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, (int, float))
        or not (0 <= duration_ms < float("inf"))
    ):
        raise ValueError("Invalid trace duration")

    if (
        isinstance(span_count, bool)
        or not isinstance(span_count, int)
        or span_count < 1
    ):
        raise ValueError("span_count must be an integer >= 1")

    if (
        isinstance(error_count, bool)
        or not isinstance(error_count, int)
        or error_count < 0
        or error_count > span_count
    ):
        raise ValueError("error_count must be an integer between 0 and span_count")

    if action_id is not None and not _is_valid_uuid(action_id):
        raise ValueError("action_id must be a valid UUID or None")

    if agent_id is not None and not _is_valid_uuid(agent_id):
        raise ValueError("agent_id must be a valid UUID or None")

    return {
        "trace_id": trace_id,
        "root_span_name": root_span_name,
        "service_name": service_name,
        "start_time": start_time,
        "duration_ms": float(duration_ms) if isinstance(duration_ms, int) else duration_ms,
        "span_count": span_count,
        "error_count": error_count,
        "action_id": action_id,
        "agent_id": agent_id,
    }


def _filter_and_sort_trace_summaries(
    summaries: list[Mapping[str, Any]],
    agent_id: str | None = None,
    action_id: str | None = None,
    has_error: bool | None = None,
    window_minutes: int | None = None,
    now: datetime | str | None = None,
    sort_by: str = "start_time",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    """Filter and order trace summaries according to TRC-01 contract parameters."""
    if not isinstance(summaries, list):
        raise ValueError("summaries must be a list")

    if agent_id is not None and not _is_valid_uuid(agent_id):
        raise ValueError("Invalid agent_id parameter: must be a valid UUID")

    if action_id is not None and not _is_valid_uuid(action_id):
        raise ValueError("Invalid action_id parameter: must be a valid UUID")

    if has_error is not None and not isinstance(has_error, bool):
        raise ValueError("has_error parameter must be a boolean")

    if window_minutes is not None:
        if (
            isinstance(window_minutes, bool)
            or not isinstance(window_minutes, int)
            or not (1 <= window_minutes <= 1440)
        ):
            raise ValueError("window_minutes must be an integer between 1 and 1440")

    if sort_by not in ("start_time", "duration_ms"):
        raise ValueError("sort_by must be 'start_time' or 'duration_ms'")

    if sort_order not in ("asc", "desc"):
        raise ValueError("sort_order must be 'asc' or 'desc'")

    now_dt: datetime | None = None
    if window_minutes is not None:
        if now is None:
            if summaries:
                times = [
                    _parse_start_time(s["start_time"])
                    for s in summaries
                    if isinstance(s, Mapping) and "start_time" in s
                ]
                now_dt = max(times) if times else datetime.now(timezone.utc)
            else:
                now_dt = datetime.now(timezone.utc)
        elif isinstance(now, str):
            now_dt = _parse_start_time(now)
        elif isinstance(now, datetime):
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("now timestamp must include timezone")
            now_dt = now
        else:
            raise ValueError("now must be a string or datetime")

    filtered: list[dict[str, Any]] = []
    cutoff_dt = (
        (now_dt - timedelta(minutes=window_minutes))
        if (window_minutes is not None and now_dt is not None)
        else None
    )

    for item in summaries:
        if not isinstance(item, Mapping):
            raise ValueError("Summary item must be a mapping")

        # agent_id filter
        if agent_id is not None and item.get("agent_id") != agent_id:
            continue

        # action_id filter
        if action_id is not None and item.get("action_id") != action_id:
            continue

        # has_error filter
        if has_error is not None:
            item_error_count = item.get("error_count", 0)
            if has_error and item_error_count <= 0:
                continue
            if not has_error and item_error_count > 0:
                continue

        # window_minutes filter
        if cutoff_dt is not None and now_dt is not None:
            item_time = _parse_start_time(item["start_time"])
            if item_time < cutoff_dt or item_time > now_dt:
                continue

        filtered.append(dict(item))

    # Sorting
    if sort_by == "start_time":
        filtered.sort(
            key=lambda s: _parse_start_time(s["start_time"]),
            reverse=(sort_order == "desc"),
        )
    elif sort_by == "duration_ms":
        filtered.sort(
            key=lambda s: s["duration_ms"],
            reverse=(sort_order == "desc"),
        )

    return filtered


def _build_trace_by_action_response(
    action_id: str,
    summaries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build canonical TraceByActionResponse structure."""
    if not _is_valid_uuid(action_id):
        raise ValueError("action_id must be a valid UUID")

    if not isinstance(summaries, list):
        raise ValueError("summaries must be a list")

    matching = [
        dict(s)
        for s in summaries
        if isinstance(s, Mapping) and s.get("action_id") == action_id
    ]

    return {
        "action_id": action_id,
        "traces": matching,
    }


def _build_trace_metrics_response(
    window_start: str,
    window_end: str,
    bucket_seconds: int,
    buckets: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build canonical TraceMetricsResponse structure."""
    start_dt = _parse_start_time(window_start)
    end_dt = _parse_start_time(window_end)

    if start_dt > end_dt:
        raise ValueError("window_start cannot be after window_end")

    if (
        isinstance(bucket_seconds, bool)
        or not isinstance(bucket_seconds, int)
        or not (1 <= bucket_seconds <= 86400)
    ):
        raise ValueError("bucket_seconds must be an integer between 1 and 86400")

    if not isinstance(buckets, list):
        raise ValueError("buckets must be a list")

    required_bucket_keys = {
        "bucket_start",
        "request_count",
        "error_count",
        "p50_ms",
        "p95_ms",
    }

    validated_buckets = []
    for bucket in buckets:
        if not isinstance(bucket, Mapping):
            raise ValueError("Invalid bucket entry")
        if set(bucket.keys()) != required_bucket_keys:
            raise ValueError("Bucket entry fields do not match TraceMetricsBucket schema")
        validated_buckets.append(dict(bucket))

    return {
        "window_start": window_start,
        "window_end": window_end,
        "bucket_seconds": bucket_seconds,
        "buckets": validated_buckets,
    }


def _generate_trace_metrics(
    summaries: list[Mapping[str, Any]],
    window_start: str | datetime,
    window_end: str | datetime,
    bucket_seconds: int = 60,
) -> dict[str, Any]:
    """Derive canonical TraceMetricsResponse from trace summaries over time window."""
    start_dt = (
        _parse_start_time(window_start)
        if isinstance(window_start, str)
        else window_start
    )
    end_dt = (
        _parse_start_time(window_end)
        if isinstance(window_end, str)
        else window_end
    )

    if start_dt.tzinfo is None or start_dt.utcoffset() is None:
        raise ValueError("window_start must have timezone")
    if end_dt.tzinfo is None or end_dt.utcoffset() is None:
        raise ValueError("window_end must have timezone")
    if start_dt > end_dt:
        raise ValueError("window_start cannot be after window_end")

    if (
        isinstance(bucket_seconds, bool)
        or not isinstance(bucket_seconds, int)
        or not (1 <= bucket_seconds <= 86400)
    ):
        raise ValueError("bucket_seconds must be an integer between 1 and 86400")

    step = timedelta(seconds=bucket_seconds)
    buckets: list[dict[str, Any]] = []

    curr_start = start_dt
    while curr_start < end_dt:
        curr_end = min(curr_start + step, end_dt)
        durations: list[float] = []
        errors = 0

        for item in summaries:
            item_dt = _parse_start_time(item["start_time"])
            if curr_start <= item_dt < curr_end:
                durations.append(float(item["duration_ms"]))
                if item.get("error_count", 0) > 0:
                    errors += 1

        bucket_start_iso = curr_start.isoformat().replace("+00:00", "Z")
        buckets.append(
            _build_trace_metrics_bucket(
                bucket_start=bucket_start_iso,
                durations_ms=durations,
                error_count=errors,
            )
        )
        curr_start += step

    start_iso = start_dt.isoformat().replace("+00:00", "Z")
    end_iso = end_dt.isoformat().replace("+00:00", "Z")

    return _build_trace_metrics_response(
        window_start=start_iso,
        window_end=end_iso,
        bucket_seconds=bucket_seconds,
        buckets=buckets,
    )



async def get_trace_details(trace_id: str) -> "TraceDetailResponse":
    """Canonical Student 3 trace-detail service boundary.

    Integration requirements:
    - Student 1's TraceDetailResponse schema and AppError
    - Verified Jaeger query adapter response format
    - TRACE_NOT_FOUND and TELEMETRY_UNAVAILABLE mappings

    No unverified telemetry is returned.
    """
    if not _is_valid_trace_id(trace_id):
        raise ValueError("Trace ID must be 32 lowercase hexadecimal characters")

    from backend.app.observability.trace_query_client import (
        fetch_trace,
    )

    raw_trace = await fetch_trace(trace_id)

    raise RuntimeError(
        "Trace mapping requires the verified Jaeger adapter "
        "and shared backend schemas"
    )
