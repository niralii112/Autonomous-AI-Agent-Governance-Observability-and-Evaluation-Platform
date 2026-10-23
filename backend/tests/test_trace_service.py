"""Unit tests for Student 3's backend-independent trace helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "services"
    / "trace_service.py"
)

spec = importlib.util.spec_from_file_location(
    "student3_trace_service",
    MODULE_PATH,
)
assert spec is not None and spec.loader is not None

trace_service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace_service)


class TestTraceIdValidation(unittest.TestCase):

    def test_valid_lowercase_trace_id(self):
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        self.assertTrue(trace_service._is_valid_trace_id(trace_id))

    def test_uppercase_rejected(self):
        self.assertFalse(
            trace_service._is_valid_trace_id("A" * 32)
        )

    def test_wrong_length_rejected(self):
        self.assertFalse(
            trace_service._is_valid_trace_id("a" * 31)
        )

    def test_non_hex_rejected(self):
        self.assertFalse(
            trace_service._is_valid_trace_id("z" * 32)
        )

    def test_uuid_with_hyphens_rejected(self):
        self.assertFalse(
            trace_service._is_valid_trace_id(
                "12345678-1234-1234-1234-123456789012"
            )
        )

    def test_non_string_rejected(self):
        self.assertFalse(
            trace_service._is_valid_trace_id(None)
        )


class TestAttributePrivacy(unittest.TestCase):

    def test_allowed_governance_attributes(self):
        attributes = {
            "gov.action_id": "action-1",
            "gov.risk_score": 0.8,
            "gov.error_code": "TEST_ERROR",
        }

        self.assertEqual(
            trace_service._filter_span_attributes(attributes),
            attributes,
        )

    def test_unknown_governance_attribute_removed(self):
        result = trace_service._filter_span_attributes(
            {
                "gov.action_id": "action-1",
                "gov.secret_value": "private",
            }
        )

        self.assertEqual(
            result,
            {"gov.action_id": "action-1"},
        )

    def test_http_attributes_allowed(self):
        result = trace_service._filter_span_attributes(
            {
                "http.method": "GET",
                "http.status_code": 200,
            }
        )

        self.assertEqual(len(result), 2)

    def test_sensitive_attributes_removed(self):
        result = trace_service._filter_span_attributes(
            {
                "gov.action_id": "action-1",
                "action_payload": {"password": "secret"},
                "authorization": "Bearer secret",
                "review_comment": "private review",
                "db.statement": "SELECT secret FROM users",
                "JWT_SECRET_KEY": "secret",
            }
        )

        self.assertEqual(
            result,
            {"gov.action_id": "action-1"},
        )

    def test_input_not_modified(self):
        original = {
            "gov.action_id": "action-1",
            "secret": "hidden",
        }

        trace_service._filter_span_attributes(original)

        self.assertIn("secret", original)


class TestSpanProcessing(unittest.TestCase):

    def test_spans_sorted_chronologically(self):
        spans = [
            {
                "span_id": "later",
                "start_time": "2026-10-22T09:15:00Z",
                "attributes": {},
            },
            {
                "span_id": "earlier",
                "start_time": "2026-10-22T09:10:00Z",
                "attributes": {},
            },
        ]

        result = trace_service._sanitize_and_sort_spans(spans)

        self.assertEqual(
            [span["span_id"] for span in result],
            ["earlier", "later"],
        )

    def test_timezone_offsets_sorted_correctly(self):
        spans = [
            {
                "span_id": "later",
                "start_time": "2026-10-22T15:00:00+05:30",
                "attributes": {},
            },
            {
                "span_id": "earlier",
                "start_time": "2026-10-22T09:00:00Z",
                "attributes": {},
            },
        ]

        result = trace_service._sanitize_and_sort_spans(spans)

        self.assertEqual(
            [span["span_id"] for span in result],
            ["earlier", "later"],
        )

    def test_sensitive_span_attributes_removed(self):
        spans = [
            {
                "span_id": "span-1",
                "start_time": "2026-10-22T09:10:00Z",
                "attributes": {
                    "gov.agent_id": "agent-1",
                    "action_payload": "private",
                    "gov.password": "private",
                },
            }
        ]

        result = trace_service._sanitize_and_sort_spans(spans)

        self.assertEqual(
            result[0]["attributes"],
            {"gov.agent_id": "agent-1"},
        )

    def test_original_span_not_modified(self):
        original = {
            "span_id": "span-1",
            "start_time": "2026-10-22T09:10:00Z",
            "attributes": {"secret": "hidden"},
        }

        trace_service._sanitize_and_sort_spans([original])

        self.assertIn("secret", original["attributes"])

    def test_missing_attributes_become_empty(self):
        span = {
            "span_id": "span-1",
            "start_time": "2026-10-22T09:10:00Z",
        }

        result = trace_service._sanitize_and_sort_spans([span])

        self.assertEqual(result[0]["attributes"], {})

    def test_invalid_timestamp_rejected(self):
        span = {
            "span_id": "span-1",
            "start_time": "not-a-timestamp",
            "attributes": {},
        }

        with self.assertRaises(ValueError):
            trace_service._sanitize_and_sort_spans([span])

    def test_timezone_required(self):
        span = {
            "span_id": "span-1",
            "start_time": "2026-10-22T09:10:00",
            "attributes": {},
        }

        with self.assertRaises(ValueError):
            trace_service._sanitize_and_sort_spans([span])


if __name__ == "__main__":
    unittest.main()


class TestTraceDetailMapping(unittest.TestCase):

    def setUp(self):
        self.trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        self.spans = [
            {
                "span_id": "bbbbbbbbbbbbbbbb",
                "parent_span_id": "aaaaaaaaaaaaaaaa",
                "span_name": "policy.evaluate",
                "service_name": "governance-backend",
                "start_time": "2026-10-22T09:10:01Z",
                "duration_ms": 90,
                "status": "ERROR",
                "attributes": {
                    "gov.action_id": "action-1",
                    "secret": "must-not-leak",
                },
            },
            {
                "span_id": "aaaaaaaaaaaaaaaa",
                "parent_span_id": None,
                "span_name": "action.submit",
                "service_name": "governance-backend",
                "start_time": "2026-10-22T09:10:00Z",
                "duration_ms": 245,
                "status": "OK",
                "attributes": {"gov.agent_id": "agent-1"},
            },
        ]

    def build(self, spans=None):
        return trace_service._build_trace_detail(
            self.trace_id,
            "2026-10-22T09:10:00Z",
            245,
            self.spans if spans is None else spans,
        )

    def test_exact_response_fields(self):
        result = self.build()
        self.assertEqual(
            set(result),
            {
                "trace_id",
                "start_time",
                "duration_ms",
                "span_count",
                "error_count",
                "spans",
            },
        )

    def test_span_and_error_counts(self):
        result = self.build()
        self.assertEqual(result["span_count"], 2)
        self.assertEqual(result["error_count"], 1)

    def test_spans_are_chronologically_sorted(self):
        result = self.build()
        self.assertEqual(
            [span["span_name"] for span in result["spans"]],
            ["action.submit", "policy.evaluate"],
        )

    def test_sensitive_attributes_removed(self):
        result = self.build()
        attributes = result["spans"][1]["attributes"]
        self.assertEqual(
            attributes,
            {"gov.action_id": "action-1"},
        )

    def test_original_spans_unchanged(self):
        self.build()
        self.assertIn("secret", self.spans[0]["attributes"])

    def test_invalid_trace_id_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_detail(
                "invalid",
                "2026-10-22T09:10:00Z",
                245,
                self.spans,
            )

    def test_empty_trace_rejected(self):
        with self.assertRaises(ValueError):
            self.build([])

    def test_invalid_span_status_rejected(self):
        spans = [dict(self.spans[0])]
        spans[0]["status"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            self.build(spans)

    def test_extra_span_fields_rejected(self):
        spans = [dict(self.spans[0])]
        spans[0]["secret_extra_field"] = "private"
        with self.assertRaises(ValueError):
            self.build(spans)

    def test_negative_duration_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_detail(
                self.trace_id,
                "2026-10-22T09:10:00Z",
                -1,
                self.spans,
            )

    def test_missing_required_span_field_rejected(self):
        spans = [dict(self.spans[0])]
        del spans[0]["service_name"]
        with self.assertRaises(ValueError):
            self.build(spans)


class TestTraceMetrics(unittest.TestCase):

    def test_empty_percentile(self):
        self.assertIsNone(trace_service._percentile([], 50))

    def test_single_value_percentile(self):
        self.assertEqual(
            trace_service._percentile([100], 95),
            100,
        )

    def test_median(self):
        self.assertEqual(
            trace_service._percentile([10, 20, 30], 50),
            20,
        )

    def test_interpolated_p95(self):
        self.assertAlmostEqual(
            trace_service._percentile([100, 200], 95),
            195,
        )

    def test_invalid_percentile(self):
        with self.assertRaises(ValueError):
            trace_service._percentile([100], 101)

    def test_empty_bucket(self):
        result = trace_service._build_trace_metrics_bucket(
            "2026-10-22T09:00:00Z",
            [],
            0,
        )

        self.assertEqual(result["request_count"], 0)
        self.assertEqual(result["error_count"], 0)
        self.assertIsNone(result["p50_ms"])
        self.assertIsNone(result["p95_ms"])

    def test_bucket_counts(self):
        result = trace_service._build_trace_metrics_bucket(
            "2026-10-22T09:00:00Z",
            [100, 200, 300],
            1,
        )

        self.assertEqual(result["request_count"], 3)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["p50_ms"], 200)

    def test_invalid_error_count(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_bucket(
                "2026-10-22T09:00:00Z",
                [100],
                2,
            )

    def test_negative_duration(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_bucket(
                "2026-10-22T09:00:00Z",
                [-10],
                0,
            )


class TestTracePagination(unittest.TestCase):

    def test_empty_page(self):
        result = trace_service._paginate_trace_summaries([])

        self.assertEqual(result["items"], [])
        self.assertEqual(result["total_items"], 0)
        self.assertEqual(result["total_pages"], 0)

    def test_first_page(self):
        result = trace_service._paginate_trace_summaries(
            [{"trace_id": str(i)} for i in range(30)],
            page=1,
            page_size=25,
        )

        self.assertEqual(len(result["items"]), 25)
        self.assertEqual(result["total_pages"], 2)

    def test_second_page(self):
        result = trace_service._paginate_trace_summaries(
            [{"trace_id": str(i)} for i in range(30)],
            page=2,
            page_size=25,
        )

        self.assertEqual(len(result["items"]), 5)

    def test_out_of_range_page(self):
        result = trace_service._paginate_trace_summaries(
            [{"trace_id": "sample"}],
            page=10,
            page_size=25,
        )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["total_items"], 1)

    def test_invalid_page(self):
        with self.assertRaises(ValueError):
            trace_service._paginate_trace_summaries(
                [],
                page=0,
            )

    def test_invalid_page_size(self):
        with self.assertRaises(ValueError):
            trace_service._paginate_trace_summaries(
                [],
                page_size=101,
            )


class TestHttpAttributeSecurity(unittest.TestCase):

    def test_approved_http_attributes_preserved(self):
        attributes = {
            "http.method": "GET",
            "http.status_code": 200,
        }

        self.assertEqual(
            trace_service._filter_span_attributes(attributes),
            attributes,
        )

    def test_authorization_header_removed(self):
        result = trace_service._filter_span_attributes({
            "http.method": "POST",
            "http.request.header.authorization": "Bearer secret",
        })

        self.assertEqual(result, {"http.method": "POST"})

    def test_cookie_headers_removed(self):
        result = trace_service._filter_span_attributes({
            "http.request.header.cookie": "session=private",
            "http.response.header.set_cookie": "token=private",
        })

        self.assertEqual(result, {})

    def test_unknown_http_attribute_removed(self):
        result = trace_service._filter_span_attributes({
            "http.method": "GET",
            "http.request.body": "confidential payload",
            "http.url": "https://example.com/?token=secret",
        })

        self.assertEqual(result, {"http.method": "GET"})

    def test_governance_attributes_still_allowed(self):
        result = trace_service._filter_span_attributes({
            "gov.action_id": "action-1",
            "gov.risk_score": 0.75,
            "http.status_code": 200,
            "gov.secret_value": "private",
        })

        self.assertEqual(result, {
            "gov.action_id": "action-1",
            "gov.risk_score": 0.75,
            "http.status_code": 200,
        })

    def test_trace_detail_does_not_leak_headers(self):
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

        spans = [{
            "span_id": "aaaaaaaaaaaaaaaa",
            "parent_span_id": None,
            "span_name": "http.request",
            "service_name": "governance-backend",
            "start_time": "2026-10-22T09:10:00Z",
            "duration_ms": 100,
            "status": "OK",
            "attributes": {
                "http.method": "GET",
                "http.request.header.authorization": "Bearer secret",
                "http.request.header.cookie": "session=private",
            },
        }]

        result = trace_service._build_trace_detail(
            trace_id,
            "2026-10-22T09:10:00Z",
            100,
            spans,
        )

        self.assertEqual(
            result["spans"][0]["attributes"],
            {"http.method": "GET"},
        )


class TestCanonicalTraceService(unittest.IsolatedAsyncioTestCase):

    async def test_invalid_trace_id_rejected(self):
        with self.assertRaises(ValueError):
            await trace_service.get_trace_details("invalid")

    async def test_canonical_service_is_async(self):
        import inspect

        self.assertTrue(
            inspect.iscoroutinefunction(
                trace_service.get_trace_details
            )
        )


class TestUuidValidation(unittest.TestCase):

    def test_valid_uuid_lowercase(self):
        self.assertTrue(
            trace_service._is_valid_uuid("10000000-0000-4000-8000-000000000001")
        )

    def test_valid_uuid_uppercase(self):
        self.assertTrue(
            trace_service._is_valid_uuid("A0000000-0000-4000-8000-000000000001")
        )

    def test_invalid_characters(self):
        self.assertFalse(
            trace_service._is_valid_uuid("10000000-0000-4000-8000-00000000000g")
        )

    def test_wrong_length(self):
        self.assertFalse(
            trace_service._is_valid_uuid("10000000-0000-4000-8000-00000000000")
        )
        self.assertFalse(
            trace_service._is_valid_uuid("10000000-0000-4000-8000-0000000000001")
        )

    def test_wrong_hyphens(self):
        self.assertFalse(
            trace_service._is_valid_uuid("10000000000040008000000000000001")
        )

    def test_non_string(self):
        self.assertFalse(trace_service._is_valid_uuid(None))
        self.assertFalse(trace_service._is_valid_uuid(12345))
        self.assertFalse(trace_service._is_valid_uuid(["10000000-0000-4000-8000-000000000001"]))


class TestTraceSummaryConstruction(unittest.TestCase):

    def setUp(self):
        self.trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        self.action_id = "40000000-0000-4000-8000-000000000001"
        self.agent_id = "10000000-0000-4000-8000-000000000001"
        self.start_time = "2026-10-22T09:10:00Z"

    def test_valid_trace_summary(self):
        summary = trace_service._build_trace_summary(
            trace_id=self.trace_id,
            root_span_name="finance.propose_payment",
            service_name="governance-api",
            start_time=self.start_time,
            duration_ms=250.5,
            span_count=4,
            error_count=1,
            action_id=self.action_id,
            agent_id=self.agent_id,
        )
        self.assertEqual(summary["trace_id"], self.trace_id)
        self.assertEqual(summary["root_span_name"], "finance.propose_payment")
        self.assertEqual(summary["service_name"], "governance-api")
        self.assertEqual(summary["start_time"], self.start_time)
        self.assertEqual(summary["duration_ms"], 250.5)
        self.assertEqual(summary["span_count"], 4)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["action_id"], self.action_id)
        self.assertEqual(summary["agent_id"], self.agent_id)

    def test_trace_summary_with_null_ids(self):
        summary = trace_service._build_trace_summary(
            trace_id=self.trace_id,
            root_span_name="system.health_check",
            service_name="governance-api",
            start_time=self.start_time,
            duration_ms=50,
            span_count=1,
            error_count=0,
            action_id=None,
            agent_id=None,
        )
        self.assertIsNone(summary["action_id"])
        self.assertIsNone(summary["agent_id"])

    def test_exact_trace_summary_keys(self):
        summary = trace_service._build_trace_summary(
            trace_id=self.trace_id,
            root_span_name="action.process",
            service_name="governance-api",
            start_time=self.start_time,
            duration_ms=100,
            span_count=2,
            error_count=0,
        )
        expected_keys = {
            "trace_id",
            "root_span_name",
            "service_name",
            "start_time",
            "duration_ms",
            "span_count",
            "error_count",
            "action_id",
            "agent_id",
        }
        self.assertEqual(set(summary.keys()), expected_keys)

    def test_int_duration_converted_to_float(self):
        summary = trace_service._build_trace_summary(
            trace_id=self.trace_id,
            root_span_name="action.process",
            service_name="governance-api",
            start_time=self.start_time,
            duration_ms=120,
            span_count=2,
            error_count=0,
        )
        self.assertIsInstance(summary["duration_ms"], float)
        self.assertEqual(summary["duration_ms"], 120.0)

    def test_invalid_trace_id_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id="short_id",
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=1,
                error_count=0,
            )

    def test_empty_root_span_name_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="   ",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=1,
                error_count=0,
            )

    def test_empty_service_name_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="",
                start_time=self.start_time,
                duration_ms=100,
                span_count=1,
                error_count=0,
            )

    def test_invalid_start_time_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time="invalid-time",
                duration_ms=100,
                span_count=1,
                error_count=0,
            )

    def test_invalid_duration_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=-10,
                span_count=1,
                error_count=0,
            )
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=True,  # boolean must be rejected
                span_count=1,
                error_count=0,
            )

    def test_invalid_span_count_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=0,
                error_count=0,
            )

    def test_invalid_error_count_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=2,
                error_count=3,  # error_count > span_count
            )
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=2,
                error_count=-1,
            )

    def test_invalid_uuid_fields_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=1,
                error_count=0,
                action_id="not-a-uuid",
            )
        with self.assertRaises(ValueError):
            trace_service._build_trace_summary(
                trace_id=self.trace_id,
                root_span_name="action",
                service_name="srv",
                start_time=self.start_time,
                duration_ms=100,
                span_count=1,
                error_count=0,
                agent_id="not-a-uuid",
            )


class TestTraceSummaryFilteringAndSorting(unittest.TestCase):

    def setUp(self):
        self.agent1 = "10000000-0000-4000-8000-000000000001"
        self.agent2 = "10000000-0000-4000-8000-000000000002"
        self.action1 = "40000000-0000-4000-8000-000000000001"
        self.action2 = "40000000-0000-4000-8000-000000000002"

        self.summaries = [
            trace_service._build_trace_summary(
                trace_id="a1111111111111111111111111111111",
                root_span_name="finance.payment",
                service_name="governance-api",
                start_time="2026-10-22T09:10:00Z",
                duration_ms=200,
                span_count=3,
                error_count=0,
                action_id=self.action1,
                agent_id=self.agent1,
            ),
            trace_service._build_trace_summary(
                trace_id="b2222222222222222222222222222222",
                root_span_name="support.refund",
                service_name="governance-api",
                start_time="2026-10-22T09:15:00Z",
                duration_ms=450,
                span_count=4,
                error_count=1,
                action_id=self.action2,
                agent_id=self.agent2,
            ),
            trace_service._build_trace_summary(
                trace_id="c3333333333333333333333333333333",
                root_span_name="finance.audit",
                service_name="governance-api",
                start_time="2026-10-22T09:20:00Z",
                duration_ms=100,
                span_count=2,
                error_count=0,
                action_id=self.action1,
                agent_id=self.agent1,
            ),
        ]

    def test_filter_by_agent_id(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            agent_id=self.agent2,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["agent_id"], self.agent2)

    def test_filter_by_action_id(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            action_id=self.action1,
        )
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r["action_id"], self.action1)

    def test_filter_by_has_error_true(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            has_error=True,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["error_count"], 1)

    def test_filter_by_has_error_false(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            has_error=False,
        )
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertEqual(r["error_count"], 0)

    def test_filter_by_window_minutes(self):
        # Now anchor at 09:20:00Z. 8 minutes window covers 09:15:00 and 09:20:00, but not 09:10:00
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            window_minutes=8,
            now="2026-10-22T09:20:00Z",
        )
        self.assertEqual(len(result), 2)
        trace_ids = [r["trace_id"] for r in result]
        self.assertIn("b2222222222222222222222222222222", trace_ids)
        self.assertIn("c3333333333333333333333333333333", trace_ids)
        self.assertNotIn("a1111111111111111111111111111111", trace_ids)

    def test_sort_by_start_time_desc(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            sort_by="start_time",
            sort_order="desc",
        )
        times = [r["start_time"] for r in result]
        self.assertEqual(
            times,
            [
                "2026-10-22T09:20:00Z",
                "2026-10-22T09:15:00Z",
                "2026-10-22T09:10:00Z",
            ],
        )

    def test_sort_by_start_time_asc(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            sort_by="start_time",
            sort_order="asc",
        )
        times = [r["start_time"] for r in result]
        self.assertEqual(
            times,
            [
                "2026-10-22T09:10:00Z",
                "2026-10-22T09:15:00Z",
                "2026-10-22T09:20:00Z",
            ],
        )

    def test_sort_by_duration_desc(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            sort_by="duration_ms",
            sort_order="desc",
        )
        durations = [r["duration_ms"] for r in result]
        self.assertEqual(durations, [450.0, 200.0, 100.0])

    def test_sort_by_duration_asc(self):
        result = trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            sort_by="duration_ms",
            sort_order="asc",
        )
        durations = [r["duration_ms"] for r in result]
        self.assertEqual(durations, [100.0, 200.0, 450.0])

    def test_invalid_filter_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries("not-a-list")

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, agent_id="invalid")

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, action_id="invalid")

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, has_error="not-a-bool")

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, window_minutes=0)

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, window_minutes=1500)

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, sort_by="invalid")

        with self.assertRaises(ValueError):
            trace_service._filter_and_sort_trace_summaries(self.summaries, sort_order="invalid")

    def test_empty_summaries_list(self):
        result = trace_service._filter_and_sort_trace_summaries([])
        self.assertEqual(result, [])

    def test_input_list_immutability(self):
        original = list(self.summaries)
        trace_service._filter_and_sort_trace_summaries(
            self.summaries,
            sort_by="duration_ms",
            sort_order="asc",
        )
        self.assertEqual(self.summaries, original)


class TestTraceByActionResponse(unittest.TestCase):

    def setUp(self):
        self.action_id = "40000000-0000-4000-8000-000000000001"
        self.other_action = "40000000-0000-4000-8000-000000000002"

        self.summaries = [
            trace_service._build_trace_summary(
                trace_id="a1111111111111111111111111111111",
                root_span_name="action.step1",
                service_name="governance-api",
                start_time="2026-10-22T09:10:00Z",
                duration_ms=100,
                span_count=2,
                error_count=0,
                action_id=self.action_id,
            ),
            trace_service._build_trace_summary(
                trace_id="b2222222222222222222222222222222",
                root_span_name="other.step",
                service_name="governance-api",
                start_time="2026-10-22T09:15:00Z",
                duration_ms=150,
                span_count=2,
                error_count=0,
                action_id=self.other_action,
            ),
        ]

    def test_valid_action_traces_mapped(self):
        response = trace_service._build_trace_by_action_response(
            self.action_id,
            self.summaries,
        )
        self.assertEqual(response["action_id"], self.action_id)
        self.assertEqual(len(response["traces"]), 1)
        self.assertEqual(response["traces"][0]["trace_id"], "a1111111111111111111111111111111")

    def test_invalid_action_id_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_by_action_response("invalid", self.summaries)

    def test_empty_traces_for_unmatched_action(self):
        unmatched = "50000000-0000-4000-8000-000000000000"
        response = trace_service._build_trace_by_action_response(
            unmatched,
            self.summaries,
        )
        self.assertEqual(response["action_id"], unmatched)
        self.assertEqual(response["traces"], [])


class TestTraceMetricsResponse(unittest.TestCase):

    def setUp(self):
        self.window_start = "2026-10-22T09:00:00Z"
        self.window_end = "2026-10-22T10:00:00Z"
        self.bucket = {
            "bucket_start": "2026-10-22T09:00:00Z",
            "request_count": 5,
            "error_count": 1,
            "p50_ms": 120.0,
            "p95_ms": 250.0,
        }

    def test_valid_trace_metrics_response(self):
        response = trace_service._build_trace_metrics_response(
            window_start=self.window_start,
            window_end=self.window_end,
            bucket_seconds=60,
            buckets=[self.bucket],
        )
        self.assertEqual(response["window_start"], self.window_start)
        self.assertEqual(response["window_end"], self.window_end)
        self.assertEqual(response["bucket_seconds"], 60)
        self.assertEqual(len(response["buckets"]), 1)
        self.assertEqual(response["buckets"][0]["request_count"], 5)

    def test_window_start_after_window_end_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_response(
                window_start="2026-10-22T11:00:00Z",
                window_end="2026-10-22T10:00:00Z",
                bucket_seconds=60,
                buckets=[],
            )

    def test_invalid_bucket_seconds_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_response(
                window_start=self.window_start,
                window_end=self.window_end,
                bucket_seconds=0,
                buckets=[],
            )
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_response(
                window_start=self.window_start,
                window_end=self.window_end,
                bucket_seconds=100000,
                buckets=[],
            )
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_response(
                window_start=self.window_start,
                window_end=self.window_end,
                bucket_seconds=True,
                buckets=[],
            )

    def test_bucket_missing_keys_rejected(self):
        with self.assertRaises(ValueError):
            trace_service._build_trace_metrics_response(
                window_start=self.window_start,
                window_end=self.window_end,
                bucket_seconds=60,
                buckets=[{"bucket_start": "2026-10-22T09:00:00Z"}],
            )

    def test_generate_trace_metrics_derivation(self):
        summaries = [
            trace_service._build_trace_summary(
                trace_id="a1111111111111111111111111111111",
                root_span_name="test.op1",
                service_name="api",
                start_time="2026-10-22T09:00:15Z",
                duration_ms=100,
                span_count=2,
                error_count=0,
            ),
            trace_service._build_trace_summary(
                trace_id="b2222222222222222222222222222222",
                root_span_name="test.op2",
                service_name="api",
                start_time="2026-10-22T09:00:45Z",
                duration_ms=200,
                span_count=2,
                error_count=1,
            ),
            trace_service._build_trace_summary(
                trace_id="c3333333333333333333333333333333",
                root_span_name="test.op3",
                service_name="api",
                start_time="2026-10-22T09:01:10Z",
                duration_ms=300,
                span_count=2,
                error_count=0,
            ),
        ]

        metrics = trace_service._generate_trace_metrics(
            summaries=summaries,
            window_start="2026-10-22T09:00:00Z",
            window_end="2026-10-22T09:02:00Z",
            bucket_seconds=60,
        )

        self.assertEqual(metrics["bucket_seconds"], 60)
        self.assertEqual(len(metrics["buckets"]), 2)

        bucket1 = metrics["buckets"][0]
        self.assertEqual(bucket1["request_count"], 2)
        self.assertEqual(bucket1["error_count"], 1)
        self.assertEqual(bucket1["p50_ms"], 150.0)

        bucket2 = metrics["buckets"][1]
        self.assertEqual(bucket2["request_count"], 1)
        self.assertEqual(bucket2["error_count"], 0)
        self.assertEqual(bucket2["p50_ms"], 300.0)
        self.assertEqual(bucket2["p95_ms"], 300.0)

    def test_generate_trace_metrics_empty_summaries(self):
        metrics = trace_service._generate_trace_metrics(
            summaries=[],
            window_start="2026-10-22T09:00:00Z",
            window_end="2026-10-22T09:02:00Z",
            bucket_seconds=60,
        )
        self.assertEqual(len(metrics["buckets"]), 2)
        for b in metrics["buckets"]:
            self.assertEqual(b["request_count"], 0)
            self.assertEqual(b["error_count"], 0)
            self.assertIsNone(b["p50_ms"])
            self.assertIsNone(b["p95_ms"])
