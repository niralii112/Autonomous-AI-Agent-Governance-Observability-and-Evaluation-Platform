"""AGT-07 and AGT-08: list the scenarios of an agent and run one of them.

Running a scenario never executes anything by itself. The agent builds a
proposal, and the proposal goes through submit_action, where the policy, the
risk score, the human approval and the execution grant decide what happens.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.agents.registry import create_agent
from app.core.enums import AgentCategory
from app.schemas import (
    ActorContext,
    AgentRunRequest,
    AgentRunResponse,
    AgentScenarioListResponse,
)
from app.services import agent_service


async def _load_agent(session: AsyncSession, agent_id: uuid.UUID) -> BaseAgent:
    """Find the registered agent and build the matching agent class.

    A missing agent raises NotFoundError (RESOURCE_NOT_FOUND).
    """
    record = await agent_service.get_agent(session, agent_id)

    return create_agent(
        AgentCategory(record.agent_category),
        record.agent_id,
        record.agent_name,
    )


async def list_agent_scenarios(
    session: AsyncSession,
    agent_id: uuid.UUID,
) -> AgentScenarioListResponse:
    agent = await _load_agent(session, agent_id)

    return AgentScenarioListResponse(
        agent_id=agent.agent_id,
        scenarios=agent.list_scenarios(),
    )


async def run_agent_scenario(
    session: AsyncSession,
    agent_id: uuid.UUID,
    request: AgentRunRequest,
    actor: ActorContext,
) -> AgentRunResponse:
    agent = await _load_agent(session, agent_id)

    # An unknown scenario stops here with RESOURCE_NOT_FOUND.
    proposal = agent.propose_action(request.scenario_key, request.idempotency_key)

    submission = await agent.submit_proposal(session, proposal, actor)

    return AgentRunResponse(
        agent_id=agent.agent_id,
        scenario_key=request.scenario_key,
        submission=submission,
    )
