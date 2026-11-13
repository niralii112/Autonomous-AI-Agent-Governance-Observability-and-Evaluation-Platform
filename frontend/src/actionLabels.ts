import type { components } from "./types/generated/api";

type ActionType = components["schemas"]["ActionType"];

const labels: Record<ActionType, string> = {
  FINANCE_GET_REPORT: "Retrieve a financial report",
  FINANCE_GENERATE_SUMMARY: "Summarize financial records",
  SUPPORT_GET_TICKET: "Retrieve a support ticket",
  SUPPORT_GENERATE_RESPONSE: "Draft a customer response",
  SUPPORT_ACCESS_CUSTOMER_INFO: "Access customer information",
  IT_GET_SERVER_STATUS: "Check server status",
  IT_ANALYZE_LOGS: "Analyze system logs",
  IT_RESTART_SERVER: "Restart a server",
  IT_CHANGE_PRIVILEGED_CONFIG: "Change restricted system settings",
  FINANCE_PROPOSE_PAYMENT: "Propose a payment",
  SUPPORT_PROPOSE_REFUND: "Propose a refund",
  FINANCE_ACCESS_SENSITIVE_RECORDS: "Access sensitive financial records",
};

export function readableLabel(value: string) {
  const words = value.replaceAll("_", " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function actionLabel(type: ActionType) {
  return labels[type] ?? readableLabel(type);
}

const outcomes: Record<string, string> = {
  ALLOW: "Allowed to proceed",
  HUMAN_REVIEW: "Approval required",
  BLOCK: "Blocked",
  SUCCEEDED: "Completed",
  FAILED: "Action failed",
};

export function outcomeLabel(status: string) {
  return outcomes[status] ?? readableLabel(status);
}
