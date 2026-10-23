import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type Action = components["schemas"]["ActionResponse"];
type ActionSummary = components["schemas"]["ActionSummary"];
type ActionSummaryPage = components["schemas"]["ActionSummaryPage"];
type Tool = components["schemas"]["ToolResponse"];
type ToolPage = components["schemas"]["ToolResponsePage"];
type Evaluation = components["schemas"]["EvaluationResultResponse"];
type EvaluationPage = components["schemas"]["EvaluationResultResponsePage"];
type RiskSummary = components["schemas"]["RiskSummaryResponse"];
type RiskAssessment = components["schemas"]["RiskAssessmentResponse"];
type RiskAssessmentPage = components["schemas"]["RiskAssessmentResponsePage"];
type ModelVersion = components["schemas"]["ModelVersionResponse"];
type ModelVersionPage = components["schemas"]["ModelVersionResponsePage"];
type AuditEvent = components["schemas"]["AuditEventResponse"];
type AuditEventPage = components["schemas"]["AuditEventResponsePage"];
type SystemHealth = components["schemas"]["HealthResponse"];
type SystemInfo = components["schemas"]["SystemInfoResponse"];

const financeAgentId = "10000000-0000-4000-8000-000000000001";
const supportAgentId = "10000000-0000-4000-8000-000000000002";
const action1Id = "40000000-0000-4000-8000-000000000001";
const action2Id = "40000000-0000-4000-8000-000000000002";

const mockActionResponses: Action[] = [
  {
    action_id: action1Id,
    agent_id: financeAgentId,
    tool_id: "50000000-0000-4000-8000-000000000001",
    requested_tool_name: "payment_gateway_transfer",
    action_type: "FINANCE_PROPOSE_PAYMENT",
    action_payload: { recipient: "Vendor Corp", amount: 15400.0, currency: "USD", invoice_ref: "INV-2026-9912" },
    payload_redacted: false,
    payload_hash: "sha256-abc",
    idempotency_key: "idem-fin-001",
    submitted_by_user_id: null,
    trace_id: "trace-fin-001",
    created_at: "2026-10-22T09:10:00Z",
  },
  {
    action_id: action2Id,
    agent_id: supportAgentId,
    tool_id: "50000000-0000-4000-8000-000000000002",
    requested_tool_name: "customer_refund_service",
    action_type: "SUPPORT_PROPOSE_REFUND",
    action_payload: { customer_id: "CUST-8491", refund_amount: 850.0, reason: "Damaged shipping container" },
    payload_redacted: false,
    payload_hash: "sha256-def",
    idempotency_key: "idem-sup-002",
    submitted_by_user_id: null,
    trace_id: "trace-sup-002",
    created_at: "2026-10-22T09:15:00Z",
  },
];

const mockActionSummaries: ActionSummary[] = [
  {
    action_id: action1Id,
    agent_id: financeAgentId,
    agent_name: "Finance Agent",
    action_type: "FINANCE_PROPOSE_PAYMENT",
    requested_tool_name: "payment_gateway_transfer",
    policy_result: "ALLOW",
    final_decision: "ALLOW",
    risk_score: 0.28,
    risk_level: "LOW",
    approval_status: null,
    execution_status: "SUCCEEDED",
    trace_id: "trace-fin-001",
    created_at: "2026-10-22T09:10:00Z",
  },
  {
    action_id: action2Id,
    agent_id: supportAgentId,
    agent_name: "Support Agent",
    action_type: "SUPPORT_PROPOSE_REFUND",
    requested_tool_name: "customer_refund_service",
    policy_result: "HUMAN_REVIEW",
    final_decision: "HUMAN_REVIEW",
    risk_score: 0.64,
    risk_level: "HIGH",
    approval_status: "PENDING",
    execution_status: null,
    trace_id: "trace-sup-002",
    created_at: "2026-10-22T09:15:00Z",
  },
];

const mockTools: Tool[] = [
  {
    tool_id: "50000000-0000-4000-8000-000000000001",
    tool_name: "payment_gateway_transfer",
    description: "Initiates financial wire or ACH disbursements to registered vendors.",
    tool_sensitivity: "PRIVILEGED",
    supported_action_type: "FINANCE_PROPOSE_PAYMENT",
    tool_status: "ACTIVE",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    tool_id: "50000000-0000-4000-8000-000000000002",
    tool_name: "customer_refund_service",
    description: "Processes customer refund vouchers up to authorized tier threshold.",
    tool_sensitivity: "WRITE",
    supported_action_type: "SUPPORT_PROPOSE_REFUND",
    tool_status: "ACTIVE",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
];

const mockEvaluations: Evaluation[] = [
  {
    evaluation_id: "60000000-0000-4000-8000-000000000001",
    evaluation_type: "PRODUCTION_RECORDS",
    agent_id: financeAgentId,
    window_start: "2026-10-21T00:00:00Z",
    window_end: "2026-10-22T00:00:00Z",
    dataset_id: null,
    model_version: "heuristic-v1.4",
    sample_size: 150,
    production_metrics: {
      total_actions: 150,
      allow_count: 120,
      block_count: 10,
      human_review_count: 20,
      executions_total: 130,
      succeeded_count: 118,
      failed_count: 2,
      approved_count: 14,
      rejected_count: 4,
      expired_count: 2,
      policy_violation_count: 6,
      task_completion_rate: 0.91,
      execution_success_rate: 0.97,
      blocked_action_rate: 0.07,
      human_review_rate: 0.13,
      approval_rate: 0.7,
      rejection_rate: 0.2,
      policy_violation_rate: 0.04,
      fallback_risk_rate: 0.0,
      avg_tool_latency_ms: 14.5,
      p95_tool_latency_ms: 22.1,
      agent_reliability_score: 0.92,
    },
    labelled_metrics: null,
    started_at: "2026-10-22T08:00:00Z",
    completed_at: "2026-10-22T08:05:00Z",
    created_by_user_id: null,
    created_at: "2026-10-22T08:05:00Z",
  },
  {
    evaluation_id: "60000000-0000-4000-8000-000000000002",
    evaluation_type: "LABELLED_DATASET",
    agent_id: supportAgentId,
    window_start: null,
    window_end: null,
    dataset_id: "support-golden-dataset-v2",
    model_version: "benchmark-v2",
    sample_size: 200,
    production_metrics: null,
    labelled_metrics: {
      dataset_id: "support-golden-dataset-v2",
      dataset_size: 200,
      positive_rate: 0.55,
      threshold_used: 0.5,
      accuracy: 0.94,
      precision: 0.91,
      recall: 0.96,
      f1_score: 0.934,
      roc_auc: 0.97,
      confusion_matrix: { true_positive: 110, false_positive: 11, false_negative: 5, true_negative: 74 },
      per_agent_category: [],
    },
    started_at: "2026-10-22T08:30:00Z",
    completed_at: "2026-10-22T08:34:00Z",
    created_by_user_id: null,
    created_at: "2026-10-22T08:34:00Z",
  },
];

const mockRiskSummary: RiskSummary = {
  window_start: "2026-10-21T00:00:00Z",
  window_end: "2026-10-22T00:00:00Z",
  total_assessments: 28,
  by_risk_level: [
    { risk_level: "LOW", count: 18 },
    { risk_level: "MEDIUM", count: 7 },
    { risk_level: "HIGH", count: 2 },
    { risk_level: "CRITICAL", count: 1 },
  ],
  by_risk_source: [
    { risk_source: "HEURISTIC_FALLBACK", count: 20 },
    { risk_source: "ML_MODEL", count: 8 },
  ],
  score_buckets: [
    { bucket_start: 0, bucket_end: 0.25, count: 18 },
    { bucket_start: 0.25, bucket_end: 0.5, count: 7 },
    { bucket_start: 0.5, bucket_end: 0.75, count: 2 },
    { bucket_start: 0.75, bucket_end: 1.0, count: 1 },
  ],
  avg_latency_ms: 12.4,
  fallback_rate: 0.0,
};

const mockRiskAssessments: RiskAssessment[] = [
  {
    risk_assessment_id: "70000000-0000-4000-8000-000000000001",
    action_id: action1Id,
    risk_score: 0.28,
    risk_level: "LOW",
    confidence_score: 0.95,
    risk_source: "HEURISTIC_FALLBACK",
    model_version: "heuristic-v1.4",
    reason_codes: ["RULE_ALLOW_STANDARD_AMOUNT"],
    features: { amount: 15400.0 },
    latency_ms: 8.5,
    created_at: "2026-10-22T09:10:00Z",
  },
  {
    risk_assessment_id: "70000000-0000-4000-8000-000000000002",
    action_id: action2Id,
    risk_score: 0.64,
    risk_level: "HIGH",
    confidence_score: 0.88,
    risk_source: "ML_MODEL",
    model_version: "risk-ml-v2.1",
    reason_codes: ["HIGH_REFUND_FREQUENCY"],
    features: { refund_amount: 850.0 },
    latency_ms: 14.2,
    created_at: "2026-10-22T09:15:00Z",
  },
];

const mockRiskModels: ModelVersion[] = [
  {
    model_version_id: "80000000-0000-4000-8000-000000000001",
    model_version: "1.4.0",
    model_kind: "HEURISTIC_FALLBACK",
    algorithm: "Deterministic Rules",
    feature_schema_version: "1.0",
    artifact_path: "/models/heuristic-v1.4.json",
    artifact_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    training_dataset_hash: null,
    metrics: null,
    trained_at: null,
    is_active: true,
    created_at: "2026-10-01T00:00:00Z",
  },
  {
    model_version_id: "80000000-0000-4000-8000-000000000002",
    model_version: "2.1.0",
    model_kind: "ML_MODEL",
    algorithm: "XGBoost Classifier",
    feature_schema_version: "2.0",
    artifact_path: "/models/risk-xgboost-v2.1.bin",
    artifact_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    training_dataset_hash: "abc123dataset",
    metrics: { f1: 0.91, roc_auc: 0.95 },
    trained_at: "2026-09-15T00:00:00Z",
    is_active: true,
    created_at: "2026-10-10T00:00:00Z",
  },
];

const mockAuditEvents: AuditEvent[] = [
  {
    audit_event_id: "90000000-0000-4000-8000-000000000001",
    event_name: "AUTH_LOGIN_SUCCEEDED",
    actor_type: "USER",
    actor_user_id: "00000000-0000-4000-8000-000000000001",
    agent_id: null,
    action_id: null,
    entity_type: "USER_SESSION",
    entity_id: "00000000-0000-4000-8000-000000000001",
    trace_id: null,
    outcome: "SUCCESS",
    event_data: { ip: "127.0.0.1", user_agent: "GovernanceConsole/1.0" },
    created_at: "2026-10-22T08:50:00Z",
  },
  {
    audit_event_id: "90000000-0000-4000-8000-000000000002",
    event_name: "POLICY_EVALUATED",
    actor_type: "SYSTEM",
    actor_user_id: null,
    agent_id: supportAgentId,
    action_id: action2Id,
    entity_type: "ACTION",
    entity_id: action2Id,
    trace_id: "trace-sup-002",
    outcome: "SUCCESS",
    event_data: { policy_key: "support-refund-review", risk_score: 0.64 },
    created_at: "2026-10-22T09:15:01Z",
  },
];

export const extendedHandlers = [
  // Actions - list (returns ActionSummaryPage)
  http.get("*/api/v1/actions", () => {
    const page: ActionSummaryPage = {
      items: mockActionSummaries,
      page: 1,
      page_size: 25,
      total_items: mockActionSummaries.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  // Actions - detail
  http.get("*/api/v1/actions/:actionId", ({ params }) => {
    const found = mockActionResponses.find((a) => a.action_id === params.actionId);
    if (!found) return HttpResponse.json({ detail: "Action not found." }, { status: 404 });
    return HttpResponse.json({
      action: found,
      governance_decisions: [],
      risk_assessments: mockRiskAssessments.filter((r) => r.action_id === found.action_id),
      approvals: [],
      executions: [],
      trace_ids: found.trace_id ? [found.trace_id] : [],
    });
  }),

  // Tools
  http.get("*/api/v1/tools", () => {
    const page: ToolPage = {
      items: mockTools,
      page: 1,
      page_size: 25,
      total_items: mockTools.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  // Evaluations
  http.get("*/api/v1/evaluations", () => {
    const page: EvaluationPage = {
      items: mockEvaluations,
      page: 1,
      page_size: 25,
      total_items: mockEvaluations.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  http.post("*/api/v1/evaluations/run", () => {
    const newEval: Evaluation = {
      evaluation_id: "60000000-0000-4000-8000-000000000099",
      evaluation_type: "PRODUCTION_RECORDS",
      agent_id: null,
      window_start: new Date(Date.now() - 86400000).toISOString(),
      window_end: new Date().toISOString(),
      dataset_id: null,
      model_version: "heuristic-v1.4",
      sample_size: 0,
      production_metrics: null,
      labelled_metrics: null,
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      created_by_user_id: null,
      created_at: new Date().toISOString(),
    };
    return HttpResponse.json(newEval, { status: 201 });
  }),

  // Risk summary
  http.get("*/api/v1/risk/summary", () => {
    return HttpResponse.json(mockRiskSummary);
  }),

  // Risk assessments
  http.get("*/api/v1/risk/assessments", () => {
    const page: RiskAssessmentPage = {
      items: mockRiskAssessments,
      page: 1,
      page_size: 25,
      total_items: mockRiskAssessments.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  // Risk models
  http.get("*/api/v1/risk/models", () => {
    const page: ModelVersionPage = {
      items: mockRiskModels,
      page: 1,
      page_size: 25,
      total_items: mockRiskModels.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  // Audit
  http.get("*/api/v1/audit-events", () => {
    const page: AuditEventPage = {
      items: mockAuditEvents,
      page: 1,
      page_size: 25,
      total_items: mockAuditEvents.length,
      total_pages: 1,
    };
    return HttpResponse.json(page);
  }),

  // System
  http.get("*/api/v1/system/health", () => {
    const health: SystemHealth = {
      status: "OK",
      version: "1.0.0",
      checked_at: new Date().toISOString(),
      components: [
        { component_name: "PostgreSQL Database", status: "OK", latency_ms: 1.1, detail: "Connected" },
        { component_name: "OpenTelemetry Collector", status: "OK", latency_ms: 0.8, detail: "Receiving on 4317/4318" },
        { component_name: "Jaeger Telemetry Service", status: "OK", latency_ms: 2.3, detail: "Port 16686 ready" },
      ],
    };
    return HttpResponse.json(health);
  }),

  http.get("*/api/v1/system/info", () => {
    const info: SystemInfo = {
      app_version: "1.0.0",
      contract_version: "1.0.0",
      api_version: "v1",
      environment: "development",
      active_model_version: "heuristic-v1.4",
      active_risk_source: "HEURISTIC_FALLBACK",
      approval_ttl_seconds: 3600,
      risk_threshold_medium: 0.3,
      risk_threshold_high: 0.7,
      risk_threshold_critical: 0.9,
    };
    return HttpResponse.json(info);
  }),
];
