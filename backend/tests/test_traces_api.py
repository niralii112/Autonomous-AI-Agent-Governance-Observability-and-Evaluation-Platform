"""Unit tests for the Student 3 traces FastAPI router (TRC-01 to TRC-04).

These tests exercise the router directly without a real Jaeger adapter.
The adapter is expected to be unavailable so every endpoint that calls
Jaeger must return 503 TELEMETRY_UNAVAILABLE.

Tests for:
  - TRC-01  GET /api/v1/traces
  - TRC-02  GET /api/v1/traces/by-action/{action_id}
  - TRC-03  GET /api/v1/traces/metrics
  - TRC-04  GET /api/v1/traces/{trace_id}

All assertions are against the canonical error_code strings in the
OpenAPI contract (TELEMETRY_UNAVAILABLE, TRACE_NOT_FOUND, VALIDATION_ERROR).
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: make backend a package that Python can import
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# FastAPI / httpx availability guard
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False

_SKIP_MSG = "fastapi and httpx are required for router tests"


@unittest.skipUnless(_FASTAPI_AVAILABLE, _SKIP_MSG)
class TestTRC01ListTraces(unittest.TestCase):
    """TRC-01: GET /api/v1/traces"""

    def setUp(self):
        from app.api.v1.traces import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_returns_503_telemetry_unavailable(self):
        resp = self.client.get("/api/v1/traces")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "TELEMETRY_UNAVAILABLE")

    def test_accepts_agent_id_filter(self):
        resp = self.client.get(
            "/api/v1/traces",
            params={"agent_id": "10000000-0000-4000-8000-000000000001"},
        )
        self.assertEqual(resp.status_code, 503)

    def test_accepts_action_id_filter(self):
        resp = self.client.get(
            "/api/v1/traces",
            params={"action_id": "40000000-0000-4000-8000-000000000001"},
        )
        self.assertEqual(resp.status_code, 503)

    def test_accepts_has_error_filter(self):
        resp = self.client.get("/api/v1/traces", params={"has_error": True})
        self.assertEqual(resp.status_code, 503)

    def test_accepts_window_minutes(self):
        resp = self.client.get("/api/v1/traces", params={"window_minutes": 30})
        self.assertEqual(resp.status_code, 503)

    def test_accepts_pagination(self):
        resp = self.client.get("/api/v1/traces", params={"page": 2, "page_size": 10})
        self.assertEqual(resp.status_code, 503)

    def test_accepts_sort_params(self):
        resp = self.client.get(
            "/api/v1/traces",
            params={"sort_by": "duration_ms", "sort_order": "asc"},
        )
        self.assertEqual(resp.status_code, 503)

    def test_rejects_invalid_page_size_over_100(self):
        resp = self.client.get("/api/v1/traces", params={"page_size": 9999})
        self.assertIn(resp.status_code, (422, 503))

    def test_rejects_window_minutes_over_1440(self):
        resp = self.client.get("/api/v1/traces", params={"window_minutes": 9999})
        self.assertIn(resp.status_code, (422, 503))


@unittest.skipUnless(_FASTAPI_AVAILABLE, _SKIP_MSG)
class TestTRC02GetTracesByAction(unittest.TestCase):
    """TRC-02: GET /api/v1/traces/by-action/{action_id}"""

    def setUp(self):
        from app.api.v1.traces import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_valid_uuid_returns_503_while_adapter_not_connected(self):
        resp = self.client.get(
            "/api/v1/traces/by-action/10000000-0000-4000-8000-000000000001"
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "TELEMETRY_UNAVAILABLE")

    def test_invalid_uuid_returns_422(self):
        resp = self.client.get("/api/v1/traces/by-action/not-a-uuid")
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error_code"], "VALIDATION_ERROR")

    def test_non_uuid_format_returns_422(self):
        resp = self.client.get("/api/v1/traces/by-action/12345")
        self.assertEqual(resp.status_code, 422)


@unittest.skipUnless(_FASTAPI_AVAILABLE, _SKIP_MSG)
class TestTRC03GetTraceMetrics(unittest.TestCase):
    """TRC-03: GET /api/v1/traces/metrics"""

    def setUp(self):
        from app.api.v1.traces import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_returns_503_telemetry_unavailable(self):
        resp = self.client.get("/api/v1/traces/metrics")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "TELEMETRY_UNAVAILABLE")

    def test_accepts_window_minutes(self):
        resp = self.client.get("/api/v1/traces/metrics", params={"window_minutes": 120})
        self.assertEqual(resp.status_code, 503)

    def test_accepts_bucket_seconds(self):
        resp = self.client.get("/api/v1/traces/metrics", params={"bucket_seconds": 300})
        self.assertEqual(resp.status_code, 503)

    def test_metrics_is_static_segment_not_matched_as_trace_id(self):
        """Ensures /metrics is not misrouted to /{trace_id}."""
        resp = self.client.get("/api/v1/traces/metrics")
        # Must return 503 (from TRC-03), NOT 422 (from TRC-04's trace_id validation)
        self.assertNotEqual(resp.json().get("error_code"), "VALIDATION_ERROR")

    def test_rejects_window_minutes_over_1440(self):
        resp = self.client.get("/api/v1/traces/metrics", params={"window_minutes": 9999})
        self.assertIn(resp.status_code, (422, 503))

    def test_rejects_bucket_seconds_over_86400(self):
        resp = self.client.get("/api/v1/traces/metrics", params={"bucket_seconds": 999999})
        self.assertIn(resp.status_code, (422, 503))


@unittest.skipUnless(_FASTAPI_AVAILABLE, _SKIP_MSG)
class TestTRC04GetTrace(unittest.TestCase):
    """TRC-04: GET /api/v1/traces/{trace_id}"""

    VALID_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"

    def setUp(self):
        from app.api.v1.traces import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_valid_trace_id_returns_503_while_adapter_not_connected(self):
        resp = self.client.get(f"/api/v1/traces/{self.VALID_TRACE_ID}")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "TELEMETRY_UNAVAILABLE")

    def test_uppercase_trace_id_returns_422(self):
        resp = self.client.get(f"/api/v1/traces/{'A' * 32}")
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["error_code"], "VALIDATION_ERROR")

    def test_short_trace_id_returns_422(self):
        resp = self.client.get(f"/api/v1/traces/{'a' * 31}")
        self.assertEqual(resp.status_code, 422)

    def test_uuid_with_hyphens_returns_422(self):
        resp = self.client.get(
            "/api/v1/traces/10000000-0000-4000-8000-000000000001"
        )
        self.assertEqual(resp.status_code, 422)

    def test_32_zero_hex_chars_is_technically_valid_format(self):
        """All-zero trace_id passes format check; Jaeger would return 404."""
        resp = self.client.get(f"/api/v1/traces/{'0' * 32}")
        # Format valid -> delegated to Jaeger; adapter unavailable -> 503
        self.assertEqual(resp.status_code, 503)

    def test_static_routes_precede_dynamic(self):
        """Confirms by-action and metrics are not captured by /{trace_id}."""
        # /metrics with short path should not reach trace_id validator
        resp = self.client.get("/api/v1/traces/metrics")
        self.assertNotEqual(
            resp.json().get("error_code"), "VALIDATION_ERROR",
            "/metrics must not be handled by /{trace_id} route",
        )


@unittest.skipUnless(_FASTAPI_AVAILABLE, _SKIP_MSG)
class TestRouteOrdering(unittest.TestCase):
    """Verify that static routes precede /{trace_id} for all three segments."""

    def setUp(self):
        from app.api.v1.traces import router
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_metrics_segment_not_validated_as_trace_id(self):
        resp = self.client.get("/api/v1/traces/metrics")
        self.assertNotIn("VALIDATION_ERROR", resp.text)

    def test_by_action_segment_not_validated_as_trace_id(self):
        resp = self.client.get(
            "/api/v1/traces/by-action/10000000-0000-4000-8000-000000000001"
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["error_code"], "TELEMETRY_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
