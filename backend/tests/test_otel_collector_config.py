"""Static contract checks for the Student 3 Collector configuration.

These tests use Python's standard library. They do not replace
validation against the pinned OpenTelemetry Collector binary.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "observability" / "otel-collector.yaml"


class TestCollectorConfiguration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.content = CONFIG.read_text(encoding="utf-8")

    def test_otlp_receivers(self):
        self.assertIn("endpoint: 0.0.0.0:4317", self.content)
        self.assertIn("endpoint: 0.0.0.0:4318", self.content)

    def test_memory_limiter(self):
        self.assertIn("memory_limiter:", self.content)
        self.assertIn("check_interval: 1s", self.content)
        self.assertIn("limit_mib: 256", self.content)
        self.assertIn("spike_limit_mib: 64", self.content)

    def test_batch_processor(self):
        self.assertIn("batch:", self.content)
        self.assertIn("timeout: 2s", self.content)
        self.assertIn("send_batch_size: 512", self.content)

    def test_jaeger_exporter(self):
        self.assertIn("otlp/jaeger:", self.content)
        self.assertIn("endpoint: jaeger:4317", self.content)
        self.assertIn("retry_on_failure:", self.content)
        self.assertIn("sending_queue:", self.content)

    def test_trace_pipeline(self):
        self.assertIn("pipelines:", self.content)
        self.assertIn("traces:", self.content)
        self.assertIn("receivers:", self.content)
        self.assertIn("processors:", self.content)
        self.assertIn("exporters:", self.content)

    def test_no_sensitive_data_export_configuration(self):
        self.assertNotIn("action_payload", self.content)
        self.assertNotIn("JWT_SECRET_KEY", self.content)
        self.assertNotIn("POSTGRES_PASSWORD", self.content)


if __name__ == "__main__":
    unittest.main()
