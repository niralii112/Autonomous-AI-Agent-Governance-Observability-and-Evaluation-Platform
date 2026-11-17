import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";
import { getMockUser } from "./handlers";
import { findMockRun, saveMockRun } from "./mockActions";
import { agents } from "./platformHandlers";
import { scenariosByCategory } from "./scenarioFixtures";

type Schemas = components["schemas"];

function scenarioError(status: number, errorCode: Schemas["ErrorCode"], message: string) {
  return HttpResponse.json<Schemas["ErrorResponse"]>({
    error_code: errorCode,
    error_message: message,
    details: null,
    trace_id: null,
    timestamp: new Date().toISOString(),
  }, { status });
}

function authorize(request: Request) {
  const user = getMockUser(request);
  if (!user) {
    const code = request.headers.has("Authorization") ? "AUTH_TOKEN_INVALID" : "AUTH_MISSING_CREDENTIALS";
    return scenarioError(401, code, "A valid demo account is required.");
  }
  if (user.role !== "ADMIN" && user.role !== "OPERATOR") {
    return scenarioError(403, "AUTH_INSUFFICIENT_ROLE", "Only admins and operators can use demo scenarios.");
  }
  return user;
}

function isRunRequest(body: unknown): body is Schemas["AgentRunRequest"] {
  if (typeof body !== "object" || body === null || !("scenario_key" in body)) return false;
  if (typeof body.scenario_key !== "string" || !body.scenario_key.trim()) return false;
  return !("idempotency_key" in body) || body.idempotency_key == null ||
    (typeof body.idempotency_key === "string" && body.idempotency_key.trim().length > 0);
}

export const scenarioHandlers = [
  http.get<{ agentId: string }, never, Schemas["AgentScenarioListResponse"] | Schemas["ErrorResponse"]>("*/api/v1/agents/:agentId/scenarios", ({ request, params }) => {
    const user = authorize(request);
    if (user instanceof Response) return user;

    const agent = agents.find((item) => item.agent_id === params.agentId);
    if (!agent) return scenarioError(404, "RESOURCE_NOT_FOUND", "Agent not found.");

    return HttpResponse.json<Schemas["AgentScenarioListResponse"]>({
      agent_id: agent.agent_id,
      scenarios: scenariosByCategory[agent.agent_category] ?? [],
    });
  }),

  http.post<{ agentId: string }, Schemas["AgentRunRequest"], Schemas["AgentRunResponse"] | Schemas["ErrorResponse"]>("*/api/v1/agents/:agentId/runs", async ({ request, params }) => {
    const user = authorize(request);
    if (user instanceof Response) return user;

    const agent = agents.find((item) => item.agent_id === params.agentId);
    if (!agent) return scenarioError(404, "RESOURCE_NOT_FOUND", "Agent not found.");

    const body: unknown = await request.json().catch(() => null);
    if (!isRunRequest(body)) return scenarioError(422, "VALIDATION_ERROR", "Choose a valid scenario.");

    const scenario = scenariosByCategory[agent.agent_category]?.find((item) => item.scenario_key === body.scenario_key);
    if (!scenario) return scenarioError(404, "RESOURCE_NOT_FOUND", "Scenario not found for this agent.");

    const { scenario_key, expected_decision, action_payload } = scenario;
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(action_payload)));
    const payloadHash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
    const idempotencyKey = body.idempotency_key ?? crypto.randomUUID();
    const existing = body.idempotency_key ? findMockRun(agent.agent_id, user.user_id, idempotencyKey) : undefined;
    if (existing) {
      if (existing.scenarioKey !== scenario_key) {
        return scenarioError(422, "VALIDATION_ERROR", "This run key is already in use for another scenario.");
      }
      return HttpResponse.json<Schemas["AgentRunResponse"]>({
        agent_id: agent.agent_id,
        scenario_key,
        submission: { ...existing.submission, duplicate: true },
      });
    }

    const actionId = crypto.randomUUID();
    const now = new Date().toISOString();
    const submission: Schemas["ActionSubmissionResponse"] = {
      action: {
        action_id: actionId,
        agent_id: agent.agent_id,
        tool_id: null,
        requested_tool_name: scenario.tool_name,
        action_type: scenario.action_type,
        action_payload,
        payload_redacted: false,
        payload_hash: payloadHash,
        idempotency_key: idempotencyKey,
        submitted_by_user_id: user.user_id,
        trace_id: null,
        created_at: now,
      },
      policy_evaluation: {
        policy_result: expected_decision,
        matched_policies: [],
        winning_policy_id: null,
        conflict_detected: false,
        evaluated_policy_count: 0,
        policy_snapshot_hash: "mock-scenario",
        error_code: null,
        latency_ms: 0,
      },
      governance_decision: {
        governance_decision_id: crypto.randomUUID(),
        action_id: actionId,
        decision_sequence: 1,
        policy_result: expected_decision,
        final_decision: expected_decision,
        decision_reason_code: "MOCK_SCENARIO",
        decision_rule_id: "mock-scenario",
        risk_assessment_id: null,
        matched_policy_ids: [],
        policy_snapshot_hash: "mock-scenario",
        payload_hash: payloadHash,
        decided_at: now,
        created_at: now,
      },
      risk_assessment: null,
      approval: null,
      execution: null,
      duplicate: false,
    };

    saveMockRun(scenario_key, agent.agent_name, submission);
    return HttpResponse.json<Schemas["AgentRunResponse"]>({
      agent_id: agent.agent_id,
      scenario_key,
      submission,
    });
  }),
];
