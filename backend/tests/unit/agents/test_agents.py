import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.base import AgentOutcome, BaseAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.registry import create_agent
from app.agents.scenarios import SCENARIO_SPECS
from app.agents.support_agent import CustomerSupportAgent
from app.core.enums import (
    AgentCategory,
    ApprovalStatus,
    ErrorCode,
    ExecutionStatus,
    GovernanceDecision,
    RiskLevel,
)
from app.core.exceptions import AppError, NotFoundError
from app.schemas.action import ActionSubmissionRequest

AGENT_FOLDER = Path(__file__).resolve().parents[3] / "app" / "agents"


def make_finance():
    return FinanceAgent(uuid.uuid4(), "finance-agent-01")


def make_support():
    return CustomerSupportAgent(uuid.uuid4(), "support-agent-01")


def agent_for(spec):
    if spec.agent_category == AgentCategory.FINANCE:
        return make_finance()
    return make_support()


# ---------- the two agents ----------


def test_agents_have_the_right_category():
    assert make_finance().agent_category == AgentCategory.FINANCE
    assert make_support().agent_category == AgentCategory.CUSTOMER_SUPPORT


def test_each_agent_lists_only_its_own_scenarios():
    finance = make_finance().list_scenarios()
    support = make_support().list_scenarios()

    assert len(finance) == 8
    assert len(support) == 5
    assert all(item.scenario_key.startswith("finance.") for item in finance)
    assert all(item.scenario_key.startswith("support.") for item in support)


def test_empty_agent_name_is_rejected():
    with pytest.raises(ValueError):
        FinanceAgent(uuid.uuid4(), "  ")


def test_agent_class_without_a_category_is_rejected():
    class NoCategoryAgent(BaseAgent):
        pass

    with pytest.raises(TypeError):
        NoCategoryAgent(uuid.uuid4(), "broken")


# ---------- proposals ----------


@pytest.mark.parametrize(
    "spec", SCENARIO_SPECS, ids=lambda spec: spec.scenario.scenario_key
)
def test_every_scenario_becomes_a_valid_proposal(spec):
    agent = agent_for(spec)

    proposal = agent.propose_action(spec.scenario.scenario_key)

    assert isinstance(proposal, ActionSubmissionRequest)
    assert proposal.agent_id == agent.agent_id
    assert proposal.tool_name == spec.scenario.tool_name
    assert proposal.action_type == spec.scenario.action_type
    assert proposal.action_payload == spec.scenario.action_payload


def test_each_proposal_gets_a_new_idempotency_key():
    agent = make_finance()

    first = agent.propose_action("finance.report.get")
    second = agent.propose_action("finance.report.get")

    assert first.idempotency_key != second.idempotency_key


def test_a_given_idempotency_key_is_used():
    agent = make_finance()

    proposal = agent.propose_action("finance.report.get", "my-key-1")

    assert proposal.idempotency_key == "my-key-1"


def test_changing_a_proposal_does_not_change_the_scenario():
    agent = make_finance()

    proposal = agent.propose_action("finance.payment.small")
    proposal.action_payload["amount"] = 999999.0

    again = agent.propose_action("finance.payment.small")
    assert again.action_payload["amount"] == 450.0


def test_unknown_scenario_is_not_found():
    with pytest.raises(NotFoundError) as exc_info:
        make_finance().propose_action("finance.does.not.exist")

    assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND


def test_an_agent_cannot_run_the_other_agents_scenario():
    with pytest.raises(NotFoundError):
        make_finance().propose_action("support.ticket.get")

    with pytest.raises(NotFoundError):
        make_support().propose_action("finance.report.get")


# ---------- agents never run tools ----------


def test_agent_code_never_imports_the_tools():
    for path in AGENT_FOLDER.glob("*.py"):
        assert "app.tools" not in path.read_text(), path.name


def test_agent_has_no_way_to_execute_a_tool():
    agent = make_finance()

    assert not hasattr(agent, "execute")
    assert not hasattr(agent, "invoke")


# ---------- talking to governance ----------


@pytest.mark.asyncio
async def test_discover_tools_returns_only_allowed_tools(monkeypatch):
    from app.services import agent_service

    agent = make_finance()

    async def fake_permissions(session, agent_id):
        assert agent_id == agent.agent_id
        return SimpleNamespace(
            permissions=[
                SimpleNamespace(tool_name="payment_processor_sim", is_allowed=True),
                SimpleNamespace(tool_name="ticket_reader", is_allowed=False),
                SimpleNamespace(tool_name="finance_report_reader", is_allowed=True),
            ]
        )

    monkeypatch.setattr(agent_service, "get_tool_permissions", fake_permissions)

    tools = await agent.discover_tools(object())

    assert tools == ["finance_report_reader", "payment_processor_sim"]


@pytest.mark.asyncio
async def test_submit_proposal_goes_through_submit_action(monkeypatch):
    from app.services import action_service

    calls = []

    async def fake_submit(session, request, actor):
        calls.append((session, request, actor))
        return "governance-answer"

    monkeypatch.setattr(action_service, "submit_action", fake_submit)
    agent = make_finance()
    proposal = agent.propose_action("finance.report.get")

    answer = await agent.submit_proposal("the-session", proposal, "the-actor")

    assert answer == "governance-answer"
    assert calls == [("the-session", proposal, "the-actor")]


@pytest.mark.asyncio
async def test_agent_cannot_submit_a_proposal_of_another_agent(monkeypatch):
    from app.services import action_service

    calls = []

    async def fake_submit(session, request, actor):
        calls.append(request)

    monkeypatch.setattr(action_service, "submit_action", fake_submit)
    proposal = make_support().propose_action("support.ticket.get")

    with pytest.raises(AppError) as exc_info:
        await make_finance().submit_proposal("session", proposal, "actor")

    assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    assert calls == []


def make_response(*, risk=None, approval=None, execution=None, duplicate=False):
    return SimpleNamespace(
        action=SimpleNamespace(action_id=uuid.uuid4()),
        governance_decision=SimpleNamespace(final_decision=GovernanceDecision.HUMAN_REVIEW),
        risk_assessment=SimpleNamespace(risk_level=risk) if risk else None,
        approval=SimpleNamespace(approval_status=approval) if approval else None,
        execution=SimpleNamespace(execution_status=execution) if execution else None,
        duplicate=duplicate,
    )


def test_handle_result_summarises_a_full_response():
    response = make_response(
        risk=RiskLevel.HIGH,
        approval=ApprovalStatus.APPROVED,
        execution=ExecutionStatus.SUCCEEDED,
    )

    outcome = make_finance().handle_result(response)

    assert isinstance(outcome, AgentOutcome)
    assert outcome.action_id == response.action.action_id
    assert outcome.final_decision == GovernanceDecision.HUMAN_REVIEW
    assert outcome.risk_level == RiskLevel.HIGH
    assert outcome.approval_status == ApprovalStatus.APPROVED
    assert outcome.execution_status == ExecutionStatus.SUCCEEDED
    assert outcome.duplicate is False


def test_handle_result_accepts_missing_parts():
    outcome = make_finance().handle_result(make_response(duplicate=True))

    assert outcome.risk_level is None
    assert outcome.approval_status is None
    assert outcome.execution_status is None
    assert outcome.duplicate is True


# ---------- registry ----------


def test_registry_builds_the_right_agent():
    finance = create_agent(AgentCategory.FINANCE, uuid.uuid4(), "finance-agent-01")
    support = create_agent(AgentCategory.CUSTOMER_SUPPORT, uuid.uuid4(), "support-agent-01")

    assert isinstance(finance, FinanceAgent)
    assert isinstance(support, CustomerSupportAgent)


def test_registry_rejects_a_category_we_do_not_support():
    with pytest.raises(AppError) as exc_info:
        create_agent(AgentCategory.IT_OPERATIONS, uuid.uuid4(), "it-agent")

    assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
