"""Translate Jaeger's query responses into AgentGuard trace data."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import get_settings


_TRACE_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


class TraceQueryUnavailable(Exception):
    """Jaeger could not return usable telemetry."""


class TraceNotFound(Exception):
    """Jaeger has no trace with the requested ID."""


def _validate_trace_id(trace_id: str) -> None:
    if not isinstance(trace_id, str) or _TRACE_ID_PATTERN.fullmatch(trace_id) is None:
        raise ValueError("trace_id must contain exactly 32 lowercase hex characters")


def _query_settings() -> tuple[str, float]:
    settings = get_settings()
    url = settings.jaeger_query_url.strip().rstrip("/")
    timeout = settings.telemetry_query_timeout_seconds
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL as exc:
        raise TraceQueryUnavailable("Jaeger query URL is invalid") from exc
    if parsed.scheme not in ("http", "https") or not parsed.host:
        raise TraceQueryUnavailable("Jaeger query URL is invalid")
    if not 0 < timeout <= 300:
        raise TraceQueryUnavailable("Jaeger query timeout is invalid")
    return url, timeout


async def _get(client: httpx.AsyncClient, path: str, **kwargs: Any) -> httpx.Response:
    try:
        response = await client.get(path, **kwargs)
        if response.status_code != 404:
            response.raise_for_status()
        return response
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        raise TraceQueryUnavailable("Jaeger query failed") from exc


def _trace_data(response: httpx.Response) -> list[dict[str, Any]]:
    if response.status_code == 404:
        raise TraceQueryUnavailable("Jaeger search endpoint is unavailable")
    try:
        body = response.json()
        data = body["data"]
        if body.get("errors") or (data is not None and not isinstance(data, list)):
            raise ValueError("Invalid Jaeger response")
        return data or []
    except (KeyError, TypeError, ValueError) as exc:
        raise TraceQueryUnavailable("Jaeger returned an invalid response") from exc


def _attributes(tags: list[dict[str, Any]]) -> dict[str, Any]:
    attributes = {tag["key"]: tag["value"] for tag in tags}
    # The backend emits these names. The public trace schema uses gov.* keys.
    for source, canonical in (
        ("action.id", "gov.action_id"),
        ("agent.id", "gov.agent_id"),
        ("http.request.method", "http.method"),
        ("http.response.status_code", "http.status_code"),
    ):
        if source in attributes:
            attributes[canonical] = attributes[source]
    return attributes


def _legacy_trace(trace: dict[str, Any]) -> dict[str, Any]:
    trace_id = trace["traceID"]
    _validate_trace_id(trace_id)
    spans = []
    for span in trace["spans"]:
        tags = _attributes(span.get("tags", []))
        otel_status = tags.get("otel.status_code")
        status = "UNSET"
        if tags.get("error") is True or otel_status in ("ERROR", "STATUS_CODE_ERROR", 2):
            status = "ERROR"
        elif otel_status in ("OK", "STATUS_CODE_OK", 1):
            status = "OK"
        parent = next((
            ref["spanID"] for ref in span.get("references", [])
            if ref["refType"] == "CHILD_OF" and ref["traceID"] == trace_id
        ), None)
        spans.append(_span(
            span["spanID"], parent, span["operationName"],
            trace["processes"][span["processID"]]["serviceName"],
            span["startTime"], span["duration"], status, tags,
        ))
    return _trace(trace_id, spans)


def _span(
    span_id: str, parent: str | None, name: str, service_name: str,
    start_us: int, duration_us: int | float, status: str, tags: dict[str, Any],
) -> dict[str, Any]:
    if not math.isfinite(duration_us) or duration_us < 0:
        raise ValueError("Invalid span duration")
    if not all(isinstance(value, str) and value.strip() for value in (span_id, name, service_name)):
        raise ValueError("Invalid span identity")
    return {
        "span_id": span_id, "parent_span_id": parent, "span_name": name,
        "service_name": service_name, "start_time": _timestamp(start_us),
        "duration_ms": duration_us / 1000, "status": status, "attributes": tags,
    }


def _timestamp(microseconds: int | float) -> str:
    return datetime.fromtimestamp(microseconds / 1_000_000, timezone.utc).isoformat()


def _trace(trace_id: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    spans.sort(key=lambda span: span["start_time"])
    start = datetime.fromisoformat(spans[0]["start_time"])
    duration_ms = max(
        (datetime.fromisoformat(span["start_time"]) - start).total_seconds() * 1000
        + span["duration_ms"]
        for span in spans
    )
    return {"trace_id": trace_id, "start_time": start.isoformat(),
            "duration_ms": duration_ms, "spans": spans}


def _otlp_tags(attributes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"key": item["key"], "value": next(iter(item["value"].values()), None)}
        for item in attributes
    ]


def _v3_trace(response: httpx.Response, trace_id: str) -> dict[str, Any]:
    spans = []
    # The streaming gateway sends one JSON envelope per line.
    for line in response.text.splitlines():
        if not line.strip():
            continue
        message = json.loads(line)
        if message.get("error"):
            if message["error"].get("code") == 5:  # gRPC NOT_FOUND
                raise TraceNotFound(trace_id)
            raise ValueError("Jaeger v3 trace query failed")
        for resource in message["result"]["resourceSpans"]:
            service = _attributes(_otlp_tags(resource["resource"]["attributes"]))["service.name"]
            for scope in resource["scopeSpans"]:
                for span in scope["spans"]:
                    start_ns = int(span["startTimeUnixNano"])
                    end_ns = int(span["endTimeUnixNano"])
                    code = span.get("status", {}).get("code")
                    status = {1: "OK", 2: "ERROR", "STATUS_CODE_OK": "OK",
                              "STATUS_CODE_ERROR": "ERROR"}.get(code, "UNSET")
                    spans.append(_span(
                        span["spanId"], span.get("parentSpanId") or None,
                        span["name"], service, start_ns // 1000, (end_ns - start_ns) / 1000,
                        status, _attributes(_otlp_tags(span.get("attributes", []))),
                    ))
    if not spans:
        raise TraceNotFound(trace_id)
    return _trace(trace_id, spans)


async def search_traces(
    start: datetime, end: datetime, limit: int, *,
    action_id: str | None = None, agent_id: str | None = None,
) -> list[dict[str, Any]]:
    url, timeout = _query_settings()
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    microsecond = timedelta(microseconds=1)
    params = {
        "service": get_settings().otel_service_name,
        "start": str((start - epoch) // microsecond),
        "end": str((end - epoch) // microsecond),
        "limit": str(limit),
    }
    if action_id is not None:
        params["tags"] = json.dumps({"action.id": action_id})
    elif agent_id is not None:
        params["tags"] = json.dumps({"agent.id": agent_id})
    async with httpx.AsyncClient(base_url=url, timeout=timeout) as client:
        response = await _get(client, "api/traces", params=params)
    try:
        return [_legacy_trace(trace) for trace in _trace_data(response)]
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError) as exc:
        raise TraceQueryUnavailable("Jaeger returned invalid trace data") from exc


async def fetch_trace(trace_id: str) -> dict[str, Any]:
    _validate_trace_id(trace_id)
    url, timeout = _query_settings()
    async with httpx.AsyncClient(base_url=url, timeout=timeout) as client:
        response = await _get(client, f"api/traces/{trace_id}")
        try:
            if response.status_code == 404:
                # Jaeger 2.24+ moved lookup to v3.
                response = await _get(client, f"api/v3/traces/{trace_id}")
                if response.status_code == 404:
                    raise TraceNotFound(trace_id)
                return _v3_trace(response, trace_id)
            traces = _trace_data(response)
            if not traces:
                raise TraceNotFound(trace_id)
            trace = _legacy_trace(traces[0])
            if trace["trace_id"] != trace_id:
                raise ValueError("Jaeger returned a different trace ID")
            return trace
        except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise TraceQueryUnavailable("Jaeger returned invalid trace data") from exc
