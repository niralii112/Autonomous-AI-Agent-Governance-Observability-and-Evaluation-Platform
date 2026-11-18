"""Configuration and input validation for the Jaeger query client."""

import asyncio
from types import SimpleNamespace

import pytest

from app.observability import trace_query_client as client


@pytest.mark.parametrize(("url", "timeout", "expected"), [
    ("http://localhost:16686", 5, ("http://localhost:16686", 5)),
    ("http://jaeger:16686/", 8, ("http://jaeger:16686", 8)),
    ("not-a-url", 5, None),
    ("http://jaeger:bogus", 5, None),
    ("http://jaeger:16686", 0, None),
])
def test_query_configuration(monkeypatch, url, timeout, expected):
    monkeypatch.setattr(client, "get_settings", lambda: SimpleNamespace(
        jaeger_query_url=url, telemetry_query_timeout_seconds=timeout,
    ))
    if expected is None:
        with pytest.raises(client.TraceQueryUnavailable):
            client._query_settings()
    else:
        assert client._query_settings() == expected


@pytest.mark.parametrize("trace_id", ["invalid", "A" * 32, "a" * 31])
def test_invalid_id_is_rejected_before_query(trace_id):
    with pytest.raises(ValueError):
        asyncio.run(client.fetch_trace(trace_id))
