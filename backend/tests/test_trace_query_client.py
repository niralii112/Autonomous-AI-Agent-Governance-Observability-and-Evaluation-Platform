"""Unit tests for the Student 3 Jaeger query boundary."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "observability"
    / "trace_query_client.py"
)

spec = importlib.util.spec_from_file_location(
    "student3_trace_query_client",
    MODULE_PATH,
)

assert spec is not None and spec.loader is not None

client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)

VALID_ID = "4bf92f3577b34da6a3ce929d0e0e4736"


class TestTraceQueryConfiguration(unittest.TestCase):

    def test_default_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            url, timeout = client._query_settings()

        self.assertEqual(url, "http://localhost:16686")
        self.assertEqual(timeout, 5.0)

    def test_custom_configuration(self):
        with patch.dict(
            os.environ,
            {
                "JAEGER_QUERY_URL": "http://jaeger:16686/",
                "TELEMETRY_QUERY_TIMEOUT_SECONDS": "8",
            },
        ):
            url, timeout = client._query_settings()

        self.assertEqual(url, "http://jaeger:16686")
        self.assertEqual(timeout, 8.0)

    def test_invalid_url_rejected(self):
        with patch.dict(
            os.environ,
            {"JAEGER_QUERY_URL": "not-a-url"},
        ):
            with self.assertRaises(client.TraceQueryUnavailable):
                client._query_settings()

    def test_invalid_timeout_rejected(self):
        with patch.dict(
            os.environ,
            {"TELEMETRY_QUERY_TIMEOUT_SECONDS": "invalid"},
        ):
            with self.assertRaises(client.TraceQueryUnavailable):
                client._query_settings()

    def test_zero_timeout_rejected(self):
        with patch.dict(
            os.environ,
            {"TELEMETRY_QUERY_TIMEOUT_SECONDS": "0"},
        ):
            with self.assertRaises(client.TraceQueryUnavailable):
                client._query_settings()


class TestTraceQueryBoundary(unittest.TestCase):

    def test_valid_trace_id(self):
        client._validate_trace_id(VALID_ID)

    def test_uppercase_trace_id_rejected(self):
        with self.assertRaises(ValueError):
            client._validate_trace_id("A" * 32)

    def test_uuid_rejected(self):
        with self.assertRaises(ValueError):
            client._validate_trace_id(
                "12345678-1234-1234-1234-123456789012"
            )

    def test_invalid_length_rejected(self):
        with self.assertRaises(ValueError):
            client._validate_trace_id("a" * 31)

    def test_query_fails_closed_without_verified_adapter(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(client.TraceQueryUnavailable):
                asyncio.run(client.fetch_trace(VALID_ID))

    def test_invalid_id_does_not_query_backend(self):
        with self.assertRaises(ValueError):
            asyncio.run(client.fetch_trace("invalid"))

    def test_fetch_trace_is_async(self):
        import inspect

        self.assertTrue(
            inspect.iscoroutinefunction(client.fetch_trace)
        )


if __name__ == "__main__":
    unittest.main()
