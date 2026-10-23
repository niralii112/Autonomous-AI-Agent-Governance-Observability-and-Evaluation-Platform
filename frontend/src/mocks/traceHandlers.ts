import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type TraceSummary = components["schemas"]["TraceSummary"];
type TraceSummaryPage = components["schemas"]["TraceSummaryPage"];
type TraceDetail = components["schemas"]["TraceDetailResponse"];
type TraceByAction = components["schemas"]["TraceByActionResponse"];
type TraceMetrics = components["schemas"]["TraceMetricsResponse"];
type Span = components["schemas"]["SpanDetail"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

const financeAgentId = "10000000-0000-4000-8000-000000000001";
const supportAgentId = "10000000-0000-4000-8000-000000000002";

const financeActionId = "40000000-0000-4000-8000-000000000001";
const supportActionId = "40000000-0000-4000-8000-000000000002";

const traceSummaries: TraceSummary[] = [
  {
    trace_id: "a1111111111111111111111111111111",
    root_span_name: "finance.propose_payment",
    service_name: "governance-api",
    start_time: "2026-10-22T09:10:00Z",
    duration_ms: 245,
    span_count: 3,
    error_count: 0,
    action_id: financeActionId,
    agent_id: financeAgentId,
  },
  {
    trace_id: "b2222222222222222222222222222222",
    root_span_name: "support.propose_refund",
    service_name: "governance-api",
    start_time: "2026-10-22T09:15:00Z",
    duration_ms: 430,
    span_count: 3,
    error_count: 1,
    action_id: supportActionId,
    agent_id: supportAgentId,
  },
];

const financeSpans: Span[] = [
  {
    span_id: "1111111111111111",
    parent_span_id: null,
    span_name: "finance.propose_payment",
    service_name: "governance-api",
    start_time: "2026-10-22T09:10:00Z",
    duration_ms: 245,
    status: "OK",
    attributes: {
      "gov.agent_id": financeAgentId,
      "gov.action_id": financeActionId,
    },
  },
  {
    span_id: "1111111111111112",
    parent_span_id: "1111111111111111",
    span_name: "policy.evaluate",
    service_name: "governance-api",
    start_time: "2026-10-22T09:10:00.020Z",
    duration_ms: 90,
    status: "OK",
    attributes: {},
  },
  {
    span_id: "1111111111111113",
    parent_span_id: "1111111111111111",
    span_name: "governance.decide",
    service_name: "governance-api",
    start_time: "2026-10-22T09:10:00.120Z",
    duration_ms: 75,
    status: "OK",
    attributes: {},
  },
];

const supportSpans: Span[] = [
  {
    span_id: "2222222222222221",
    parent_span_id: null,
    span_name: "support.propose_refund",
    service_name: "governance-api",
    start_time: "2026-10-22T09:15:00Z",
    duration_ms: 430,
    status: "ERROR",
    attributes: {
      "gov.agent_id": supportAgentId,
      "gov.action_id": supportActionId,
    },
  },
  {
    span_id: "2222222222222222",
    parent_span_id: "2222222222222221",
    span_name: "policy.evaluate",
    service_name: "governance-api",
    start_time: "2026-10-22T09:15:00.040Z",
    duration_ms: 110,
    status: "OK",
    attributes: {},
  },
  {
    span_id: "2222222222222223",
    parent_span_id: "2222222222222221",
    span_name: "risk.assess",
    service_name: "governance-api",
    start_time: "2026-10-22T09:15:00.170Z",
    duration_ms: 180,
    status: "ERROR",
    attributes: {},
  },
];

const traceDetails: TraceDetail[] = [
  {
    trace_id: traceSummaries[0].trace_id,
    start_time: traceSummaries[0].start_time,
    duration_ms: traceSummaries[0].duration_ms,
    span_count: financeSpans.length,
    error_count: 0,
    spans: financeSpans,
  },
  {
    trace_id: traceSummaries[1].trace_id,
    start_time: traceSummaries[1].start_time,
    duration_ms: traceSummaries[1].duration_ms,
    span_count: supportSpans.length,
    error_count: 1,
    spans: supportSpans,
  },
];

function traceNotFound(): Response {
  const error: ErrorResponse = {
    error_code: "TRACE_NOT_FOUND",
    error_message: "The requested trace was not found.",
    details: null,
    trace_id: null,
    timestamp: new Date().toISOString(),
  };

  return HttpResponse.json(error, { status: 404 });
}

export const traceHandlers = [
  http.get("*/api/v1/traces", ({ request }) => {
    const url = new URL(request.url);

    const agentId = url.searchParams.get("agent_id");
    const actionId = url.searchParams.get("action_id");
    const hasError = url.searchParams.get("has_error");

    const page = Math.max(
      1,
      Number(url.searchParams.get("page") || 1)
    );

    const pageSize = Math.max(
      1,
      Number(url.searchParams.get("page_size") || 25)
    );

    const filtered = traceSummaries.filter((trace) => {
      if (agentId && trace.agent_id !== agentId) return false;
      if (actionId && trace.action_id !== actionId) return false;

      if (hasError === "true" && trace.error_count === 0) {
        return false;
      }

      if (hasError === "false" && trace.error_count > 0) {
        return false;
      }

      return true;
    });

    const response: TraceSummaryPage = {
      items: filtered.slice(
        (page - 1) * pageSize,
        page * pageSize
      ),
      page,
      page_size: pageSize,
      total_items: filtered.length,
      total_pages: Math.ceil(filtered.length / pageSize),
    };

    return HttpResponse.json(response);
  }),

  http.get("*/api/v1/traces/by-action/:action_id", ({ params }) => {
    const actionId = String(params.action_id);

    const response: TraceByAction = {
      action_id: actionId,
      traces: traceSummaries.filter(
        (trace) => trace.action_id === actionId
      ),
    };

    return HttpResponse.json(response);
  }),

  http.get("*/api/v1/traces/metrics", ({ request }) => {
    const url = new URL(request.url);

    const bucketSeconds = Number(
      url.searchParams.get("bucket_seconds") || 60
    );

    const response: TraceMetrics = {
      window_start: "2026-10-22T09:00:00Z",
      window_end: "2026-10-22T10:00:00Z",
      bucket_seconds: bucketSeconds,
      buckets: [
        {
          bucket_start: "2026-10-22T09:10:00Z",
          request_count: 1,
          error_count: 0,
          p50_ms: 245,
          p95_ms: 245,
        },
        {
          bucket_start: "2026-10-22T09:15:00Z",
          request_count: 1,
          error_count: 1,
          p50_ms: 430,
          p95_ms: 430,
        },
      ],
    };

    return HttpResponse.json(response);
  }),

  http.get("*/api/v1/traces/:trace_id", ({ params }) => {
    const trace = traceDetails.find(
      (item) => item.trace_id === String(params.trace_id)
    );

    if (!trace) {
      return traceNotFound();
    }

    return HttpResponse.json(trace);
  }),
];
