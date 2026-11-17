import type { components } from "../types/generated/api";

type Schemas = components["schemas"];
type Submission = Schemas["ActionSubmissionResponse"];
type Summary = Schemas["ActionSummary"];
type Detail = Schemas["ActionDetailResponse"];

type MockRun = {
  scenarioKey: string;
  submission: Submission;
  summary: Summary;
};

const runs = new Map<string, MockRun>();

export function saveMockRun(scenarioKey: string, agentName: string, submission: Submission) {
  const { action, governance_decision: decision } = submission;
  const summary: Summary = {
    action_id: action.action_id,
    agent_id: action.agent_id,
    agent_name: agentName,
    action_type: action.action_type,
    requested_tool_name: action.requested_tool_name,
    policy_result: decision.policy_result,
    final_decision: decision.final_decision,
    risk_score: null,
    risk_level: null,
    approval_status: null,
    execution_status: null,
    trace_id: action.trace_id,
    created_at: action.created_at,
  };

  runs.set(action.action_id, { scenarioKey, submission, summary });
}

export function findMockRun(agentId: string, userId: string, idempotencyKey: string) {
  return Array.from(runs.values()).find(({ submission: { action } }) =>
    action.agent_id === agentId &&
    action.submitted_by_user_id === userId &&
    action.idempotency_key === idempotencyKey
  );
}

export function listMockRunSummaries(): Summary[] {
  return Array.from(runs.values(), (run) => run.summary).reverse();
}

export function getMockRunDetails(actionId: string): Detail | undefined {
  const submission = runs.get(actionId)?.submission;
  if (!submission) return undefined;

  return {
    action: submission.action,
    governance_decisions: [submission.governance_decision],
    risk_assessments: [],
    approvals: [],
    executions: [],
    trace_ids: [],
  };
}
