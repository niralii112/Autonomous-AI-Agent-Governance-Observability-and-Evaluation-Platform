import type { components } from "../types/generated/api";

type Schemas = components["schemas"];

// Sample outcomes from the ML_MODEL column of contracts/examples/scenarios/scenario-catalog.json.
export const scenariosByCategory: Partial<Record<Schemas["AgentCategory"], Schemas["AgentScenario"][]>> = {
  "FINANCE": [
    {
      "scenario_key": "finance.report.get",
      "action_type": "FINANCE_GET_REPORT",
      "tool_name": "finance_report_reader",
      "description": "Retrieve quarterly report",
      "expected_decision": "ALLOW",
      "action_payload": {
        "report_id": "rpt-2026-q3",
        "period": "2026-Q3"
      }
    },
    {
      "scenario_key": "finance.report.restricted",
      "action_type": "FINANCE_GET_REPORT",
      "tool_name": "finance_report_reader",
      "description": "Retrieve a restricted report (policy block, low risk)",
      "expected_decision": "BLOCK",
      "action_payload": {
        "report_id": "rpt-restricted-001",
        "period": "2026-Q3"
      }
    },
    {
      "scenario_key": "finance.summary.generate",
      "action_type": "FINANCE_GENERATE_SUMMARY",
      "tool_name": "finance_summary_generator",
      "description": "Generate financial summary",
      "expected_decision": "ALLOW",
      "action_payload": {
        "report_id": "rpt-2026-q3",
        "period": "2026-Q3"
      }
    },
    {
      "scenario_key": "finance.payment.small",
      "action_type": "FINANCE_PROPOSE_PAYMENT",
      "tool_name": "payment_processor_sim",
      "description": "Pay 450 USD to a normal payee",
      "expected_decision": "ALLOW",
      "action_payload": {
        "payee_id": "payee-0001",
        "amount": 450,
        "currency": "USD",
        "reference": "INV-3321"
      }
    },
    {
      "scenario_key": "finance.payment.review",
      "action_type": "FINANCE_PROPOSE_PAYMENT",
      "tool_name": "payment_processor_sim",
      "description": "Pay 25000 USD (needs review, HIGH risk)",
      "expected_decision": "HUMAN_REVIEW",
      "action_payload": {
        "payee_id": "payee-0002",
        "amount": 25000,
        "currency": "USD",
        "reference": "INV-3390"
      }
    },
    {
      "scenario_key": "finance.payment.over_limit",
      "action_type": "FINANCE_PROPOSE_PAYMENT",
      "tool_name": "payment_processor_sim",
      "description": "Pay 60000 USD (mandatory block)",
      "expected_decision": "BLOCK",
      "action_payload": {
        "payee_id": "payee-0003",
        "amount": 60000,
        "currency": "USD",
        "reference": "INV-3400"
      }
    },
    {
      "scenario_key": "finance.payment.blocked_payee",
      "action_type": "FINANCE_PROPOSE_PAYMENT",
      "tool_name": "payment_processor_sim",
      "description": "Pay 10 USD to a denylisted payee",
      "expected_decision": "BLOCK",
      "action_payload": {
        "payee_id": "payee-blocked-001",
        "amount": 10,
        "currency": "USD",
        "reference": "INV-3401"
      }
    },
    {
      "scenario_key": "finance.records.bank_accounts",
      "action_type": "FINANCE_ACCESS_SENSITIVE_RECORDS",
      "tool_name": "finance_records_vault",
      "description": "Request bank account records",
      "expected_decision": "HUMAN_REVIEW",
      "action_payload": {
        "record_set": "bank_accounts",
        "record_count": 250,
        "justification": "Quarterly reconciliation"
      }
    }
  ],
  "CUSTOMER_SUPPORT": [
    {
      "scenario_key": "support.ticket.get",
      "action_type": "SUPPORT_GET_TICKET",
      "tool_name": "ticket_reader",
      "description": "Retrieve ticket",
      "expected_decision": "ALLOW",
      "action_payload": {
        "ticket_id": "tkt-1001"
      }
    },
    {
      "scenario_key": "support.response.generate",
      "action_type": "SUPPORT_GENERATE_RESPONSE",
      "tool_name": "support_response_generator",
      "description": "Draft a support reply",
      "expected_decision": "ALLOW",
      "action_payload": {
        "ticket_id": "tkt-1001",
        "tone": "FRIENDLY"
      }
    },
    {
      "scenario_key": "support.refund.small",
      "action_type": "SUPPORT_PROPOSE_REFUND",
      "tool_name": "refund_processor_sim",
      "description": "Refund 45 USD",
      "expected_decision": "ALLOW",
      "action_payload": {
        "ticket_id": "tkt-1001",
        "customer_id": "cus-501",
        "amount": 45,
        "currency": "USD",
        "reason": "Late delivery"
      }
    },
    {
      "scenario_key": "support.refund.review",
      "action_type": "SUPPORT_PROPOSE_REFUND",
      "tool_name": "refund_processor_sim",
      "description": "Refund 350 USD",
      "expected_decision": "HUMAN_REVIEW",
      "action_payload": {
        "ticket_id": "tkt-1002",
        "customer_id": "cus-502",
        "amount": 350,
        "currency": "USD",
        "reason": "Defective product"
      }
    },
    {
      "scenario_key": "support.customer_info.request",
      "action_type": "SUPPORT_ACCESS_CUSTOMER_INFO",
      "tool_name": "customer_info_accessor",
      "description": "Request customer contact data",
      "expected_decision": "HUMAN_REVIEW",
      "action_payload": {
        "customer_id": "cus-503",
        "fields": [
          "email",
          "phone"
        ],
        "justification": "Verify identity for refund"
      }
    }
  ]
};
