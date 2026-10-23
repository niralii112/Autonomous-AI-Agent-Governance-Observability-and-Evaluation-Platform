import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type Agent = components["schemas"]["AgentResponse"];
type AgentPage = components["schemas"]["AgentResponsePage"];
type Overview = components["schemas"]["OverviewMetricsResponse"];
type Performance = components["schemas"]["AgentPerformanceResponse"];
type ErrorResponse = components["schemas"]["ErrorResponse"];

const agents: Agent[] = [
  {
    agent_id: "10000000-0000-4000-8000-000000000001",
    agent_name: "Finance Agent",
    agent_category: "FINANCE",
    description: "Governed finance operations and reporting.",
    agent_status: "ACTIVE",
    trust_tier: 2,
    owner_user_id: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
  {
    agent_id: "10000000-0000-4000-8000-000000000002",
    agent_name: "Customer Support Agent",
    agent_category: "CUSTOMER_SUPPORT",
    description: "Governed customer support workflows.",
    agent_status: "ACTIVE",
    trust_tier: 2,
    owner_user_id: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
];

const overview: Overview = {
  window_start: "2026-10-21T09:00:00Z",
  window_end: "2026-10-22T09:00:00Z",
  total_actions: 24,
  allow_count: 15,
  human_review_count: 6,
  block_count: 3,
  pending_approvals: 2,
  running_executions: 1,
  failed_executions: 1,
  active_agents: 2,
  avg_risk_score: 0.34,
  actions_over_time: [],
  recent_actions: [],
};

function notFound(message: string) {
  const error: ErrorResponse = {
    error_code: "RESOURCE_NOT_FOUND",
    error_message: message,
    details: null,
    trace_id: null,
    timestamp: new Date().toISOString(),
  };

  return HttpResponse.json(error, { status: 404 });
}

export const platformHandlers = [
  http.get("*/api/v1/agents", ({ request }) => {
    const url = new URL(request.url);

    const page = Math.max(
      1,
      Number(url.searchParams.get("page") || 1)
    );

    const pageSize = Math.max(
      1,
      Number(url.searchParams.get("page_size") || 25)
    );

    const category = url.searchParams.get("agent_category");
    const status = url.searchParams.get("agent_status");

    const sortBy = url.searchParams.get("sort_by");
    const sortOrder = url.searchParams.get("sort_order") || "desc";

    const filtered = agents.filter(
      (agent) =>
        (!category || agent.agent_category === category) &&
        (!status || agent.agent_status === status)
    );

    if (sortBy === "agent_name" || sortBy === "created_at") {
      filtered.sort((a, b) => {
        const comparison =
          sortBy === "agent_name"
            ? a.agent_name.localeCompare(b.agent_name)
            : a.created_at.localeCompare(b.created_at);

        return sortOrder === "asc" ? comparison : -comparison;
      });
    }

    const response: AgentPage = {
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

  http.get("*/api/v1/agents/:agentId", ({ params }) => {
    const agent = agents.find(
      (item) => item.agent_id === params.agentId
    );

    if (!agent) {
      return notFound("Agent not found");
    }

    return HttpResponse.json(agent);
  }),

  http.get("*/api/v1/evaluations/overview", () => {
    return HttpResponse.json(overview);
  }),

  http.get(
    "*/api/v1/evaluations/agent-performance",
    ({ request }) => {
      const url = new URL(request.url);
      const agentId = url.searchParams.get("agent_id");

      const agent = agents.find(
        (item) => item.agent_id === agentId
      );

      if (!agent) {
        return notFound("Agent not found");
      }

      const response: Performance = {
        agent_id: agent.agent_id,
        agent_name: agent.agent_name,
        window_start: overview.window_start,
        window_end: overview.window_end,
        metrics: {
          total_actions: 12,
          allow_count: 8,
          human_review_count: 3,
          block_count: 1,
          executions_total: 8,
          succeeded_count: 7,
          failed_count: 1,
          approved_count: 2,
          rejected_count: 1,
          expired_count: 0,
          policy_violation_count: 1,
          task_completion_rate: 0.875,
          execution_success_rate: 0.875,
          blocked_action_rate: 0.0833,
          human_review_rate: 0.25,
          approval_rate: 0.6667,
          rejection_rate: 0.3333,
          policy_violation_rate: 0.0833,
          fallback_risk_rate: 0,
          avg_tool_latency_ms: 120,
          p95_tool_latency_ms: 210,
          agent_reliability_score: 0.91,
        },
      };

      return HttpResponse.json(response);
    }
  ),
];
