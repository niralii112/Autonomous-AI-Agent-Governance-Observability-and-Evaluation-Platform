"""The 13 fixed scenarios our two agents can run (spec section 15.1, IT scenarios left out).

Each scenario is a ready-made action request, so a demo or a test always sends
exactly the same payload. The extra fields in ScenarioSpec are only used by
the model acceptance check and by tests; the API shows just `scenario`.
"""

from dataclasses import dataclass

from app.core.enums import (
    ActionType,
    AgentCategory,
    GovernanceDecision,
    RiskLevel,
    ToolSensitivity,
)
from app.schemas.agent_run import AgentScenario


@dataclass(frozen=True)
class ScenarioSpec:
    agent_category: AgentCategory
    tool_sensitivity: ToolSensitivity
    scenario: AgentScenario
    heuristic_risk_level: RiskLevel
    # Risk levels the ML model may give and still be accepted.
    acceptance_levels: tuple[RiskLevel, ...]
    # Decision when the rule-based heuristic is used instead of the ML model.
    decision_with_heuristic: GovernanceDecision


SCENARIO_SPECS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.READ_ONLY,
        scenario=AgentScenario(
            scenario_key="finance.report.get",
            action_type=ActionType.FINANCE_GET_REPORT,
            tool_name="finance_report_reader",
            description="Retrieve quarterly report",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'report_id': 'rpt-2026-q3', 'period': '2026-Q3'},
        ),
        heuristic_risk_level=RiskLevel.LOW,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM),
        decision_with_heuristic=GovernanceDecision.ALLOW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.READ_ONLY,
        scenario=AgentScenario(
            scenario_key="finance.report.restricted",
            action_type=ActionType.FINANCE_GET_REPORT,
            tool_name="finance_report_reader",
            description="Retrieve a restricted report (policy block, low risk)",
            expected_decision=GovernanceDecision.BLOCK,
            action_payload={'report_id': 'rpt-restricted-001', 'period': '2026-Q3'},
        ),
        heuristic_risk_level=RiskLevel.LOW,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM),
        decision_with_heuristic=GovernanceDecision.BLOCK,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.READ_ONLY,
        scenario=AgentScenario(
            scenario_key="finance.summary.generate",
            action_type=ActionType.FINANCE_GENERATE_SUMMARY,
            tool_name="finance_summary_generator",
            description="Generate financial summary",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'report_id': 'rpt-2026-q3', 'period': '2026-Q3'},
        ),
        heuristic_risk_level=RiskLevel.LOW,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM),
        decision_with_heuristic=GovernanceDecision.ALLOW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="finance.payment.small",
            action_type=ActionType.FINANCE_PROPOSE_PAYMENT,
            tool_name="payment_processor_sim",
            description="Pay 450 USD to a normal payee",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'payee_id': 'payee-0001',
                     'amount': 450.0,
                     'currency': 'USD',
                     'reference': 'INV-3321'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="finance.payment.review",
            action_type=ActionType.FINANCE_PROPOSE_PAYMENT,
            tool_name="payment_processor_sim",
            description="Pay 25000 USD (needs review, HIGH risk)",
            expected_decision=GovernanceDecision.HUMAN_REVIEW,
            action_payload={'payee_id': 'payee-0002',
                     'amount': 25000.0,
                     'currency': 'USD',
                     'reference': 'INV-3390'},
        ),
        heuristic_risk_level=RiskLevel.HIGH,
        acceptance_levels=(RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="finance.payment.over_limit",
            action_type=ActionType.FINANCE_PROPOSE_PAYMENT,
            tool_name="payment_processor_sim",
            description="Pay 60000 USD (mandatory block)",
            expected_decision=GovernanceDecision.BLOCK,
            action_payload={'payee_id': 'payee-0003',
                     'amount': 60000.0,
                     'currency': 'USD',
                     'reference': 'INV-3400'},
        ),
        heuristic_risk_level=RiskLevel.HIGH,
        acceptance_levels=(RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL),
        decision_with_heuristic=GovernanceDecision.BLOCK,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="finance.payment.blocked_payee",
            action_type=ActionType.FINANCE_PROPOSE_PAYMENT,
            tool_name="payment_processor_sim",
            description="Pay 10 USD to a denylisted payee",
            expected_decision=GovernanceDecision.BLOCK,
            action_payload={'payee_id': 'payee-blocked-001',
                     'amount': 10.0,
                     'currency': 'USD',
                     'reference': 'INV-3401'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.BLOCK,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.FINANCE,
        tool_sensitivity=ToolSensitivity.SENSITIVE_READ,
        scenario=AgentScenario(
            scenario_key="finance.records.bank_accounts",
            action_type=ActionType.FINANCE_ACCESS_SENSITIVE_RECORDS,
            tool_name="finance_records_vault",
            description="Request bank account records",
            expected_decision=GovernanceDecision.HUMAN_REVIEW,
            action_payload={'record_set': 'bank_accounts',
                     'record_count': 250,
                     'justification': 'Quarterly reconciliation'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.CUSTOMER_SUPPORT,
        tool_sensitivity=ToolSensitivity.READ_ONLY,
        scenario=AgentScenario(
            scenario_key="support.ticket.get",
            action_type=ActionType.SUPPORT_GET_TICKET,
            tool_name="ticket_reader",
            description="Retrieve ticket",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'ticket_id': 'tkt-1001'},
        ),
        heuristic_risk_level=RiskLevel.LOW,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM),
        decision_with_heuristic=GovernanceDecision.ALLOW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.CUSTOMER_SUPPORT,
        tool_sensitivity=ToolSensitivity.READ_ONLY,
        scenario=AgentScenario(
            scenario_key="support.response.generate",
            action_type=ActionType.SUPPORT_GENERATE_RESPONSE,
            tool_name="support_response_generator",
            description="Draft a support reply",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'ticket_id': 'tkt-1001', 'tone': 'FRIENDLY'},
        ),
        heuristic_risk_level=RiskLevel.LOW,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM),
        decision_with_heuristic=GovernanceDecision.ALLOW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.CUSTOMER_SUPPORT,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="support.refund.small",
            action_type=ActionType.SUPPORT_PROPOSE_REFUND,
            tool_name="refund_processor_sim",
            description="Refund 45 USD",
            expected_decision=GovernanceDecision.ALLOW,
            action_payload={'ticket_id': 'tkt-1001',
                     'customer_id': 'cus-501',
                     'amount': 45.0,
                     'currency': 'USD',
                     'reason': 'Late delivery'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.CUSTOMER_SUPPORT,
        tool_sensitivity=ToolSensitivity.WRITE,
        scenario=AgentScenario(
            scenario_key="support.refund.review",
            action_type=ActionType.SUPPORT_PROPOSE_REFUND,
            tool_name="refund_processor_sim",
            description="Refund 350 USD",
            expected_decision=GovernanceDecision.HUMAN_REVIEW,
            action_payload={'ticket_id': 'tkt-1002',
                     'customer_id': 'cus-502',
                     'amount': 350.0,
                     'currency': 'USD',
                     'reason': 'Defective product'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
    ScenarioSpec(
        agent_category=AgentCategory.CUSTOMER_SUPPORT,
        tool_sensitivity=ToolSensitivity.SENSITIVE_READ,
        scenario=AgentScenario(
            scenario_key="support.customer_info.request",
            action_type=ActionType.SUPPORT_ACCESS_CUSTOMER_INFO,
            tool_name="customer_info_accessor",
            description="Request customer contact data",
            expected_decision=GovernanceDecision.HUMAN_REVIEW,
            action_payload={'customer_id': 'cus-503',
                     'fields': ['email', 'phone'],
                     'justification': 'Verify identity for refund'},
        ),
        heuristic_risk_level=RiskLevel.MEDIUM,
        acceptance_levels=(RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH),
        decision_with_heuristic=GovernanceDecision.HUMAN_REVIEW,
    ),
)


def get_scenario_spec(
    agent_category: AgentCategory,
    scenario_key: str,
) -> ScenarioSpec | None:
    """Find one scenario of an agent category, or None when the key is unknown."""
    for spec in SCENARIO_SPECS:
        if spec.agent_category == agent_category and spec.scenario.scenario_key == scenario_key:
            return spec

    return None


def scenarios_for_category(agent_category: AgentCategory) -> list[AgentScenario]:
    """All scenarios of an agent category, in the fixed order of the catalogue."""
    return [
        spec.scenario
        for spec in SCENARIO_SPECS
        if spec.agent_category == agent_category
    ]
