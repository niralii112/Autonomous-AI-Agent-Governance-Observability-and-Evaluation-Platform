"""AGT-07 and AGT-08 (spec section 11.2): the scenarios of an agent and running one."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import UserRole
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import (
    ActorContext,
    AgentRunRequest,
    AgentRunResponse,
    AgentScenarioListResponse,
)
from app.services import agent_run_service

router = APIRouter(prefix="/agents", tags=["AGT"])
admin_or_operator = require_roles(UserRole.ADMIN, UserRole.OPERATOR)


@router.get(
    "/{agent_id}/scenarios",
    response_model=AgentScenarioListResponse,
    operation_id="listAgentScenarios",
    summary="List deterministic scenarios of an agent",
    responses=errors(401, 403, 404),
)
async def list_agent_scenarios(
    agent_id: uuid.UUID,
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> AgentScenarioListResponse:
    return await agent_run_service.list_agent_scenarios(session, agent_id)


@router.post(
    "/{agent_id}/runs",
    response_model=AgentRunResponse,
    operation_id="runAgentScenario",
    summary="Run a scenario through governance",
    responses=errors(401, 403, 404, 422, 503),
)
async def run_agent_scenario(
    agent_id: uuid.UUID,
    request: AgentRunRequest,
    actor: ActorContext = Depends(admin_or_operator),
    session: AsyncSession = Depends(get_session),
) -> AgentRunResponse:
    # submit_action commits its own transactions, so the router does not commit.
    return await agent_run_service.run_agent_scenario(session, agent_id, request, actor)
