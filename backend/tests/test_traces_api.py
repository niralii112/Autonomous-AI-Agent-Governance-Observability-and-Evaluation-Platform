"""Exercise trace endpoints through FastAPI and an HTTP-level Jaeger mock."""

import json
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.traces import router
from app.core.enums import UserRole
from app.core.error_handlers import register_error_handlers
from app.dependencies.auth import get_current_actor
from app.observability import trace_query_client
from app.schemas import ActorContext


TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
OTHER_TRACE = "1" * 32
ACTION = "40000000-0000-4000-8000-000000000001"
AGENT = "10000000-0000-4000-8000-000000000001"
ROOT_SPAN = "0123456789abcdef"
SERVICE = "governance-backend"


def jaeger_trace(trace_id, *, duration_us=35_000, error=True):
    now = datetime.now(timezone.utc) - timedelta(minutes=3)
    start = int(now.timestamp() * 1_000_000)
    return {
        "traceID": trace_id,
        "processes": {"p1": {"serviceName": SERVICE}},
        "spans": [
            {
                "spanID": ROOT_SPAN, "processID": "p1", "operationName": "submit_action",
                "startTime": start, "duration": duration_us,
                "tags": [{"key": "agent.id", "value": AGENT}],
            },
            {
                "spanID": "2222222222222222", "processID": "p1", "operationName": "governance",
                "startTime": start + duration_us - 2000, "duration": 5000,
                "references": [{"refType": "CHILD_OF", "traceID": trace_id, "spanID": ROOT_SPAN}],
                "tags": [
                    {"key": "action.id", "value": ACTION if error else AGENT},
                    {"key": "error", "value": error},
                    {"key": "http.request.header.authorization", "value": "private"},
                ],
            },
        ],
    }


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        user_id=AGENT, username="demo", role=UserRole.OPERATOR,
    )
    async_client = httpx.AsyncClient
    monkeypatch.setattr(trace_query_client, "_query_settings", lambda: ("http://jaeger:16686", 2))
    monkeypatch.setattr(
        trace_query_client, "get_settings",
        lambda: SimpleNamespace(otel_service_name=SERVICE),
    )

    def with_jaeger(handler):
        monkeypatch.setattr(trace_query_client.httpx, "AsyncClient", lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs,
        ))
        return TestClient(app)

    return app, with_jaeger


def test_list_filters_sorting_and_pagination(api):
    def jaeger(request):
        assert request.url.path == "/api/traces"
        assert request.url.params["service"] == SERVICE
        assert json.loads(request.url.params["tags"]) == {"agent.id": AGENT}
        assert int(request.url.params["end"]) - int(request.url.params["start"]) == 900_000_000
        assert request.url.params["limit"] == "20"
        return httpx.Response(200, json={"data": [
            jaeger_trace(TRACE_ID),
            jaeger_trace(OTHER_TRACE, duration_us=5000, error=False),
        ]})

    client = api[1](jaeger)
    params = {
        "agent_id": AGENT, "limit": 20, "window_minutes": 15,
        "sort_by": "duration_ms", "sort_order": "asc", "page_size": 1,
    }
    result = client.get("/api/v1/traces", params=params)
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["total_pages"] == page["total_items"] == 2
    assert page["items"][0]["trace_id"] == OTHER_TRACE
    assert client.get("/api/v1/traces", params={**params, "page": 2}).json()["items"][0]["trace_id"] == TRACE_ID
    assert client.get("/api/v1/traces", params={**params, "has_error": True}).json()["total_items"] == 1


def test_action_lookup_uses_tag_even_when_only_child_has_it(api):
    def jaeger(request):
        assert json.loads(request.url.params["tags"]) == {"action.id": ACTION}
        return httpx.Response(200, json={"data": [
            jaeger_trace(TRACE_ID), jaeger_trace(OTHER_TRACE, error=False),
        ]})

    client = api[1](jaeger)
    response = client.get(f"/api/v1/traces/by-action/{ACTION}")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "action_id": ACTION,
        "traces": [{
            **response.json()["traces"][0], "trace_id": TRACE_ID, "action_id": ACTION,
            "agent_id": AGENT, "root_span_name": "submit_action", "span_count": 2, "error_count": 1,
        }],
    }


def test_metrics_and_detail_use_jaeger_span_timings(api):
    def jaeger(request):
        if request.url.path != "/api/traces":
            assert request.url.path == f"/api/traces/{TRACE_ID}"
        return httpx.Response(200, json={"data": [jaeger_trace(TRACE_ID)]})

    client = api[1](jaeger)
    detail = client.get(f"/api/v1/traces/{TRACE_ID}")
    assert detail.status_code == 200, detail.text
    trace = detail.json()
    assert trace["duration_ms"] == pytest.approx(38)
    assert trace["error_count"] == 1
    assert trace["spans"][1]["parent_span_id"] == ROOT_SPAN
    assert trace["spans"][1]["attributes"] == {"gov.action_id": ACTION}

    metrics = client.get("/api/v1/traces/metrics?window_minutes=10&bucket_seconds=600")
    assert metrics.status_code == 200, metrics.text
    bucket, = metrics.json()["buckets"]
    assert bucket["request_count"] == bucket["error_count"] == 1
    assert bucket["p50_ms"] == pytest.approx(38)
    assert bucket["p95_ms"] == pytest.approx(38)


def test_empty_search_and_missing_trace_are_distinct(api):
    client = api[1](lambda request: httpx.Response(
        200, json={"data": []},
    ) if request.url.path == "/api/traces" else httpx.Response(404))
    assert client.get("/api/v1/traces").json()["items"] == []
    assert client.get(f"/api/v1/traces/by-action/{ACTION}").json()["traces"] == []
    response = client.get(f"/api/v1/traces/{TRACE_ID}")
    assert response.status_code == 404
    assert response.json()["error_code"] == "TRACE_NOT_FOUND"


@pytest.mark.parametrize("suffix", ["", "/metrics", f"/by-action/{ACTION}", f"/{TRACE_ID}"])
def test_jaeger_failure_returns_canonical_503(api, suffix):
    def timeout(request):
        raise httpx.ReadTimeout("test timeout", request=request)

    response = api[1](timeout).get("/api/v1/traces" + suffix)
    assert response.status_code == 503
    assert response.json()["error_code"] == "TELEMETRY_UNAVAILABLE"
    assert response.json()["error_message"]


def test_invalid_queries_and_viewer_are_rejected_before_jaeger(api):
    app, with_jaeger = api

    def unexpected(request):
        pytest.fail(f"Unexpected Jaeger request: {request.url}")

    client = with_jaeger(unexpected)
    for suffix in ("?limit=201", "?page_size=101", "?agent_id=bad", "/not-a-trace", "/by-action/bad"):
        response = client.get("/api/v1/traces" + suffix)
        assert response.status_code == 422
        assert response.json()["error_code"] == "VALIDATION_ERROR"

    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        user_id=AGENT, username="viewer", role=UserRole.VIEWER,
    )
    assert client.get("/api/v1/traces").status_code == 403


def test_detail_falls_back_to_jaeger_v3(api):
    def jaeger(request):
        if request.url.path == f"/api/traces/{TRACE_ID}":
            return httpx.Response(404)
        assert request.url.path == f"/api/v3/traces/{TRACE_ID}"
        now = str(int(datetime.now(timezone.utc).timestamp() * 1_000_000_000))
        return httpx.Response(200, json={"result": {"resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": SERVICE}}]},
            "scopeSpans": [{"spans": [{
                "traceId": TRACE_ID, "spanId": ROOT_SPAN, "name": "submit_action",
                "startTimeUnixNano": now, "endTimeUnixNano": str(int(now) + 10_000_000),
                "status": {"code": "STATUS_CODE_OK"},
            }]}],
        }]}})

    response = api[1](jaeger).get(f"/api/v1/traces/{TRACE_ID}")
    assert response.status_code == 200, response.text
    assert response.json()["duration_ms"] == 10
    assert response.json()["spans"][0]["status"] == "OK"


def test_malformed_jaeger_data_returns_503(api):
    response = api[1](lambda _: httpx.Response(200, json={"data": [{"traceID": TRACE_ID}]})).get(
        "/api/v1/traces"
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "TELEMETRY_UNAVAILABLE"
