import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type Policy = components["schemas"]["PolicyResponse"];
type PolicyPage = components["schemas"]["PolicyResponsePage"];
type Decision = components["schemas"]["GovernanceDecisionResponse"];
type DecisionPage = components["schemas"]["GovernanceDecisionResponsePage"];

const policies: Policy[] = [
  {
    policy_id: "20000000-0000-4000-8000-000000000001",
    policy_key: "finance-sensitive-review",
    version: 1,
    name: "Finance Sensitive Action Review",
    description: "Require human review for sensitive finance operations.",
    effect: "HUMAN_REVIEW",
    priority: 100,
    is_mandatory: false,
    is_active: true,
    conditions: {
      all: [],
      any: [],
    },
    scope_agent_id: null,
    scope_agent_category: "FINANCE",
    scope_action_type: "FINANCE_PROPOSE_PAYMENT",
    supersedes_policy_id: null,
    created_by_user_id: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
  {
    policy_id: "20000000-0000-4000-8000-000000000002",
    policy_key: "support-refund-review",
    version: 1,
    name: "Support Refund Review",
    description: "Require human review for proposed customer refunds.",
    effect: "HUMAN_REVIEW",
    priority: 90,
    is_mandatory: false,
    is_active: true,
    conditions: {
      all: [],
      any: [],
    },
    scope_agent_id: null,
    scope_agent_category: "CUSTOMER_SUPPORT",
    scope_action_type: "SUPPORT_PROPOSE_REFUND",
    supersedes_policy_id: null,
    created_by_user_id: null,
    created_at: "2026-10-01T09:00:00Z",
    updated_at: "2026-10-01T09:00:00Z",
  },
];

const decisions: Decision[] = [
  {
    governance_decision_id: "30000000-0000-4000-8000-000000000001",
    action_id: "40000000-0000-4000-8000-000000000001",
    decision_sequence: 1,
    policy_result: "HUMAN_REVIEW",
    final_decision: "HUMAN_REVIEW",
    decision_reason_code: "POLICY_REVIEW_REQUIRED",
    decision_rule_id: "finance-sensitive-review",
    risk_assessment_id: null,
    matched_policy_ids: [policies[0].policy_id],
    policy_snapshot_hash: "demo-policy-snapshot-001",
    payload_hash: "demo-payload-001",
    decided_at: "2026-10-22T09:00:00Z",
    created_at: "2026-10-22T09:00:00Z",
  },
  {
    governance_decision_id: "30000000-0000-4000-8000-000000000002",
    action_id: "40000000-0000-4000-8000-000000000002",
    decision_sequence: 1,
    policy_result: "ALLOW",
    final_decision: "ALLOW",
    decision_reason_code: "POLICY_ALLOW",
    decision_rule_id: "default-allow",
    risk_assessment_id: null,
    matched_policy_ids: [],
    policy_snapshot_hash: "demo-policy-snapshot-002",
    payload_hash: "demo-payload-002",
    decided_at: "2026-10-22T09:05:00Z",
    created_at: "2026-10-22T09:05:00Z",
  },
];

export const governanceHandlers = [
  http.get("*/api/v1/policies", ({ request }) => {
    const url = new URL(request.url);

    const page = Math.max(
      1,
      Number(url.searchParams.get("page") || 1)
    );

    const pageSize = Math.max(
      1,
      Number(url.searchParams.get("page_size") || 25)
    );

    const response: PolicyPage = {
      items: policies.slice(
        (page - 1) * pageSize,
        page * pageSize
      ),
      page,
      page_size: pageSize,
      total_items: policies.length,
      total_pages: Math.ceil(policies.length / pageSize),
    };

    return HttpResponse.json(response);
  }),

  http.get("*/api/v1/governance-decisions", ({ request }) => {
    const url = new URL(request.url);

    const page = Math.max(
      1,
      Number(url.searchParams.get("page") || 1)
    );

    const pageSize = Math.max(
      1,
      Number(url.searchParams.get("page_size") || 25)
    );

    const response: DecisionPage = {
      items: decisions.slice(
        (page - 1) * pageSize,
        page * pageSize
      ),
      page,
      page_size: pageSize,
      total_items: decisions.length,
      total_pages: Math.ceil(decisions.length / pageSize),
    };

    return HttpResponse.json(response);
  }),
];
