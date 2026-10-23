"""AGT-01..06 (spec section 11.2). AGT-07/08 (scenarios, runs) belong to Student 2."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import AgentCategory, AgentStatus, SortOrder, UserRole
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import (
    ActorContext, AgentCreateRequest, AgentResponse, AgentResponsePage, AgentUpdateRequest,
    ToolPermissionListResponse, ToolPermissionsUpdateRequest,
)
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["AGT"])
admin_only = require_roles(UserRole.ADMIN)


@router.post("", response_model=AgentResponse, status_code=201, operation_id="createAgent",
             summary="Register agent", responses=errors(401, 403, 409, 422))
async def create_agent(request: AgentCreateRequest, actor: ActorContext = Depends(admin_only),
                       session: AsyncSession = Depends(get_session)) -> AgentResponse:
    result = await agent_service.register_agent(session, request, actor)
    await session.commit()
    return result


@router.get("", response_model=AgentResponsePage, operation_id="listAgents",
            summary="List agents", responses=errors(401, 403))
async def list_agents(
    agent_category: AgentCategory | None = Query(None),
    agent_status: AgentStatus | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "agent_name"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> AgentResponsePage:
    return await agent_service.list_agents(
        session, category=agent_category, status=agent_status, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/{agent_id}", response_model=AgentResponse, operation_id="getAgent",
            summary="Get agent", responses=errors(401, 403, 404))
async def get_agent(agent_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                    session: AsyncSession = Depends(get_session)) -> AgentResponse:
    return await agent_service.get_agent(session, agent_id)


@router.patch("/{agent_id}", response_model=AgentResponse, operation_id="updateAgent",
              summary="Update agent", responses=errors(401, 403, 404, 422))
async def update_agent(agent_id: uuid.UUID, request: AgentUpdateRequest,
                       actor: ActorContext = Depends(admin_only),
                       session: AsyncSession = Depends(get_session)) -> AgentResponse:
    result = await agent_service.update_agent(session, agent_id, request, actor)
    await session.commit()
    return result


@router.put("/{agent_id}/tool-permissions", response_model=ToolPermissionListResponse,
            operation_id="setAgentToolPermissions", summary="Replace the agent's tool permissions",
            responses=errors(401, 403, 404, 422))
async def set_tool_permissions(agent_id: uuid.UUID, request: ToolPermissionsUpdateRequest,
                               actor: ActorContext = Depends(admin_only),
                               session: AsyncSession = Depends(get_session)) -> ToolPermissionListResponse:
    result = await agent_service.set_tool_permissions(session, agent_id, request, actor)
    await session.commit()
    return result


@router.get("/{agent_id}/tool-permissions", response_model=ToolPermissionListResponse,
            operation_id="getAgentToolPermissions", summary="Get the agent's tool permissions",
            responses=errors(401, 403, 404))
async def get_tool_permissions(agent_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                               session: AsyncSession = Depends(get_session)) -> ToolPermissionListResponse:
    return await agent_service.get_tool_permissions(session, agent_id)
