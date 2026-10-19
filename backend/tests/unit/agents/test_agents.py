
import pytest

from app.agents.base import AgentRunOutcome, BaseAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.support_agent import SupportAgent


def test_finance_agent_initializes():
    agent = FinanceAgent()

    assert agent.agent_name == "Finance Agent"
    assert agent.agent_category == "FINANCE"
    assert "FINANCE_PROPOSE_PAYMENT" in agent.list_scenarios()


def test_support_agent_initializes():
    agent = SupportAgent()

    assert agent.agent_name == "Support Agent"
    assert agent.agent_category == "SUPPORT"
    assert "SUPPORT_PROPOSE_REFUND" in agent.list_scenarios()


@pytest.mark.parametrize(
    "agent,scenario",
    [
        (
            FinanceAgent(),
            {
                "scenario_key": "FINANCE_PROPOSE_PAYMENT",
                "action_type": "FINANCE_PROPOSE_PAYMENT",
                "tool_name": "payment_proposal",
                "action_payload": {"amount": 100, "currency": "USD"},
            },
        ),
        (
            SupportAgent(),
            {
                "scenario_key": "SUPPORT_PROPOSE_REFUND",
                "action_type": "SUPPORT_PROPOSE_REFUND",
                "tool_name": "refund_proposal",
                "action_payload": {"amount": 50, "currency": "USD"},
            },
        ),
    ],
)
def test_agents_create_proposals_without_executing_tools(agent, scenario):
    proposal = agent.propose_action(scenario)

    assert proposal["agent_id"] == agent.agent_id
    assert proposal["agent_category"] == agent.agent_category
    assert proposal["scenario_key"] == scenario["scenario_key"]
    assert proposal["action_payload"] == scenario["action_payload"]
    assert proposal["idempotency_key"]


def test_each_proposal_gets_a_unique_idempotency_key():
    agent = FinanceAgent()
    scenario = {
        "scenario_key": "FINANCE_PROPOSE_PAYMENT",
        "action_type": "FINANCE_PROPOSE_PAYMENT",
        "tool_name": "payment_proposal",
        "action_payload": {"amount": 100, "currency": "USD"},
    }

    first = agent.propose_action(scenario)
    second = agent.propose_action(scenario)

    assert first["idempotency_key"] != second["idempotency_key"]


@pytest.mark.parametrize(
    "scenario",
    [
        {},
        {"scenario_key": "test"},
        {
            "scenario_key": "test",
            "action_type": "test",
            "tool_name": "test",
            "action_payload": [],
        },
    ],
)
def test_finance_agent_rejects_invalid_scenarios(scenario):
    agent = FinanceAgent()

    with pytest.raises((ValueError, TypeError)):
        agent.propose_action(scenario)


def test_base_agent_proposal_validation():
    class ExampleAgent(BaseAgent):
        def propose_action(self, scenario):
            return scenario

    agent = ExampleAgent("example-1", "Example Agent", "TEST")

    with pytest.raises(ValueError):
        agent.submit_proposal({"agent_id": "example-1"})

    proposal = {
        "agent_id": "example-1",
        "tool_name": "example_tool",
        "action_type": "EXAMPLE_ACTION",
        "action_payload": {},
        "idempotency_key": "test-key",
    }

    result = agent.submit_proposal(proposal)

    assert result["status"] == "READY_FOR_GOVERNANCE"
    assert result["proposal"] == proposal


def test_base_agent_normalizes_governance_result():
    class ExampleAgent(BaseAgent):
        def propose_action(self, scenario):
            return scenario

    agent = ExampleAgent("example-1", "Example Agent", "TEST")
    result = agent.handle_result({"status": "APPROVED"})

    assert result["agent_id"] == "example-1"
    assert result["agent_category"] == "TEST"
    assert result["result"]["status"] == "APPROVED"


def test_agent_run_outcome_defaults():
    outcome = AgentRunOutcome(scenario_key="example", status="READY")

    assert outcome.proposed_actions == []
    assert outcome.results == []
    assert outcome.error_message is None
