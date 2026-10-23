import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type Approval = components["schemas"]["ApprovalResponse"];
type ApprovalPage = components["schemas"]["ApprovalResponsePage"];
type ApprovalDecision = components["schemas"]["ApprovalDecisionResponse"];
type ApprovalReviewRequest = components["schemas"]["ApprovalReviewRequest"];
type ApprovalRejectRequest = components["schemas"]["ApprovalRejectRequest"];
type ErrorResponse = components["schemas"]["ErrorResponse"];
type ActionSummary = components["schemas"]["ActionSummary"];

const financeAgentId = "10000000-0000-4000-8000-000000000001";
const supportAgentId = "10000000-0000-4000-8000-000000000002";

const now = "2026-10-22T09:00:00Z";

function makeAction(
  actionId: string,
  agentId: string,
  agentName: string,
  actionType: ActionSummary["action_type"],
  toolName: string
): ActionSummary {
  return {
    action_id: actionId,
    agent_id: agentId,
    agent_name: agentName,
    action_type: actionType,
    requested_tool_name: toolName,
    policy_result: "HUMAN_REVIEW",
    final_decision: "HUMAN_REVIEW",
    risk_score: 0.65,
    risk_level: "MEDIUM",
    approval_status: "PENDING",
    execution_status: null,
    trace_id: null,
    created_at: now,
  };
}

const approvals: Approval[] = [
  {
    approval_id: "50000000-0000-4000-8000-000000000001",
    action_id: "40000000-0000-4000-8000-000000000001",
    governance_decision_id: "30000000-0000-4000-8000-000000000001",
    approval_status: "PENDING",
    requested_at: now,
    expires_at: "2026-12-31T23:59:59Z",
    reviewed_by_user_id: null,
    reviewed_at: null,
    review_comment: null,
    consumed_at: null,
    action_summary: makeAction(
      "40000000-0000-4000-8000-000000000001",
      financeAgentId,
      "Finance Agent",
      "FINANCE_PROPOSE_PAYMENT",
      "finance-payment-tool"
    ),
    created_at: now,
    updated_at: now,
  },
  {
    approval_id: "50000000-0000-4000-8000-000000000002",
    action_id: "40000000-0000-4000-8000-000000000002",
    governance_decision_id: "30000000-0000-4000-8000-000000000002",
    approval_status: "PENDING",
    requested_at: now,
    expires_at: "2026-12-31T23:59:59Z",
    reviewed_by_user_id: null,
    reviewed_at: null,
    review_comment: null,
    consumed_at: null,
    action_summary: makeAction(
      "40000000-0000-4000-8000-000000000002",
      supportAgentId,
      "Customer Support Agent",
      "SUPPORT_PROPOSE_REFUND",
      "support-refund-tool"
    ),
    created_at: now,
    updated_at: now,
  },
  {
    approval_id: "50000000-0000-4000-8000-000000000003",
    action_id: "40000000-0000-4000-8000-000000000003",
    governance_decision_id: "30000000-0000-4000-8000-000000000003",
    approval_status: "PENDING",
    requested_at: now,
    expires_at: "2026-12-31T23:59:59Z",
    reviewed_by_user_id: null,
    reviewed_at: null,
    review_comment: null,
    consumed_at: null,
    action_summary: makeAction(
      "40000000-0000-4000-8000-000000000003",
      financeAgentId,
      "Finance Agent",
      "FINANCE_ACCESS_SENSITIVE_RECORDS",
      "finance-records-tool"
    ),
    created_at: now,
    updated_at: now,
  },
];

function apiError(
  status: number,
  code: ErrorResponse["error_code"],
  message: string
) {
  const response: ErrorResponse = {
    error_code: code,
    error_message: message,
    details: null,
    trace_id: null,
    timestamp: new Date().toISOString(),
  };

  return HttpResponse.json(response, { status });
}

function findApproval(id: string) {
  return approvals.find((approval) => approval.approval_id === id);
}

function applyDecision(
  approval: Approval,
  status: "APPROVED" | "REJECTED",
  comment: string | null
) {
  const timestamp = new Date().toISOString();

  approval.approval_status = status;
  approval.review_comment = comment;
  approval.reviewed_at = timestamp;
  approval.updated_at = timestamp;
  approval.reviewed_by_user_id = "00000000-0000-4000-8000-000000000001";

  if (approval.action_summary) {
    approval.action_summary.approval_status = status;
  }

  const response: ApprovalDecision = {
    approval,
    execution: null,
  };

  return HttpResponse.json(response);
}

export const approvalHandlers = [
  http.get("*/api/v1/approvals", ({ request }) => {
    const url = new URL(request.url);

    const status = url.searchParams.get("approval_status");

    const page = Math.max(
      1,
      Number(url.searchParams.get("page") || 1)
    );

    const pageSize = Math.max(
      1,
      Number(url.searchParams.get("page_size") || 25)
    );

    const filtered = status
      ? approvals.filter((approval) => approval.approval_status === status)
      : approvals;

    const response: ApprovalPage = {
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

  http.post(
    "*/api/v1/approvals/:approval_id/approve",
    async ({ params, request }) => {
      const approval = findApproval(String(params.approval_id));

      if (!approval) {
        return apiError(
          404,
          "RESOURCE_NOT_FOUND",
          "Approval request not found."
        );
      }

      if (approval.approval_status !== "PENDING") {
        return apiError(
          409,
          "APPROVAL_NOT_PENDING",
          "Approval request is no longer pending."
        );
      }

      const body = (await request.json()) as ApprovalReviewRequest;

      return applyDecision(
        approval,
        "APPROVED",
        body.review_comment ?? null
      );
    }
  ),

  http.post(
    "*/api/v1/approvals/:approval_id/reject",
    async ({ params, request }) => {
      const approval = findApproval(String(params.approval_id));

      if (!approval) {
        return apiError(
          404,
          "RESOURCE_NOT_FOUND",
          "Approval request not found."
        );
      }

      if (approval.approval_status !== "PENDING") {
        return apiError(
          409,
          "APPROVAL_NOT_PENDING",
          "Approval request is no longer pending."
        );
      }

      const body = (await request.json()) as ApprovalRejectRequest;
      const comment = body.review_comment?.trim();

      if (!comment) {
        return apiError(
          422,
          "VALIDATION_ERROR",
          "A rejection reason is required."
        );
      }

      return applyDecision(approval, "REJECTED", comment);
    }
  ),
];

