import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.enums import AgentCategory, ErrorCode, UserRole
from app.core.exceptions import AppError, NotFoundError
from app.schemas import ActorContext, AgentRunRequest, AgentRunResponse
from app.services import action_service, agent_run_service, agent_service

EXAMPLES = Path(__file__).resolve().parents[4] / "contracts" / "examples"
RUN_EXAMPLE = AgentRunResponse.model_validate(
    json.loads((EXAMPLES / "AGT-08.response.json").read_text())
)

ACTOR = ActorContext(user_id=uuid.uuid4(), username="operator", role=UserRole.OPERATOR)


def agent_record(category=AgentCategory.FINANCE, name="finance-agent-01"):
    return SimpleNamespace(
        agent_id=uuid.uuid4(),
        agent_name=name,
        agent_category=category,
    )


@pytest.fixture
def submitted(monkeypatch):
    """Replaces submit_action with a fake that records what it receives."""
    calls = []

    async def fake_submit(session, request, actor):
        calls.append((request, actor))
        return RUN_EXAMPLE.submission

    monkeypatch.setattr(action_service, "submit_action", fake_submit)
    return calls


def use_agent(monkeypatch, record):
    async def fake_get_agent(session, agent_id):
        return record

    monkeypatch.setattr(agent_service, "get_agent", fake_get_agent)


@pytest.mark.asyncio
async def test_lists_the_scenarios_of_a_finance_agent(monkeypatch):
    record = agent_record()
    use_agent(monkeypatch, record)

    response = await agent_run_service.list_agent_scenarios(object(), record.agent_id)

    assert response.agent_id == record.agent_id
    assert len(response.scenarios) == 8


@pytest.mark.asyncio
async def test_lists_the_scenarios_of_a_support_agent(monkeypatch):
    record = agent_record(AgentCategory.CUSTOMER_SUPPORT, "support-agent-01")
    use_agent(monkeypatch, record)

    response = await agent_run_service.list_agent_scenarios(object(), record.agent_id)

    assert len(response.scenarios) == 5


@pytest.mark.asyncio
async def test_unknown_agent_is_not_found(monkeypatch):
    async def missing(session, agent_id):
        raise NotFoundError("Agent not found.")

    monkeypatch.setattr(agent_service, "get_agent", missing)

    with pytest.raises(NotFoundError):
        await agent_run_service.list_agent_scenarios(object(), uuid.uuid4())


@pytest.mark.asyncio
async def test_run_sends_the_scenario_through_submit_action(monkeypatch, submitted):
    record = agent_record()
    use_agent(monkeypatch, record)
    request = AgentRunRequest(scenario_key="finance.payment.small", idempotency_key="run-1")

    response = await agent_run_service.run_agent_scenario(
        object(), record.agent_id, request, ACTOR
    )

    assert len(submitted) == 1
    sent, actor = submitted[0]
    assert actor == ACTOR
    assert sent.agent_id == record.agent_id
    assert sent.tool_name == "payment_processor_sim"
    assert sent.action_type.value == "FINANCE_PROPOSE_PAYMENT"
    assert sent.action_payload["amount"] == 450.0
    assert sent.idempotency_key == "run-1"
    assert response.agent_id == record.agent_id
    assert response.scenario_key == "finance.payment.small"
    assert response.submission == RUN_EXAMPLE.submission


@pytest.mark.asyncio
async def test_run_makes_an_idempotency_key_when_none_is_given(monkeypatch, submitted):
    record = agent_record()
    use_agent(monkeypatch, record)

    await agent_run_service.run_agent_scenario(
        object(), record.agent_id, AgentRunRequest(scenario_key="finance.report.get"), ACTOR
    )

    assert submitted[0][0].idempotency_key


@pytest.mark.asyncio
async def test_unknown_scenario_is_not_submitted(monkeypatch, submitted):
    record = agent_record()
    use_agent(monkeypatch, record)

    with pytest.raises(NotFoundError):
        await agent_run_service.run_agent_scenario(
            object(), record.agent_id, AgentRunRequest(scenario_key="finance.nope"), ACTOR
        )

    assert submitted == []


@pytest.mark.asyncio
async def test_an_agent_cannot_run_another_agents_scenario(monkeypatch, submitted):
    record = agent_record(AgentCategory.CUSTOMER_SUPPORT, "support-agent-01")
    use_agent(monkeypatch, record)

    with pytest.raises(NotFoundError):
        await agent_run_service.run_agent_scenario(
            object(), record.agent_id, AgentRunRequest(scenario_key="finance.report.get"), ACTOR
        )

    assert submitted == []


@pytest.mark.asyncio
async def test_a_category_we_do_not_support_is_rejected(monkeypatch, submitted):
    record = agent_record(AgentCategory.IT_OPERATIONS, "it-agent-01")
    use_agent(monkeypatch, record)

    with pytest.raises(AppError) as exc_info:
        await agent_run_service.run_agent_scenario(
            object(), record.agent_id, AgentRunRequest(scenario_key="it.status.get"), ACTOR
        )

    assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    assert submitted == []
