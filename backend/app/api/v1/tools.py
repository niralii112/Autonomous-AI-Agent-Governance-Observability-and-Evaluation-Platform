"""TLS-01..04 (spec section 11.2)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import SortOrder, ToolSensitivity, ToolStatus, UserRole
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import ActorContext, ToolCreateRequest, ToolResponse, ToolResponsePage, ToolUpdateRequest
from app.services import tool_service

router = APIRouter(prefix="/tools", tags=["TLS"])
admin_only = require_roles(UserRole.ADMIN)


@router.post("", response_model=ToolResponse, status_code=201, operation_id="createTool",
             summary="Register tool", responses=errors(401, 403, 409, 422))
async def create_tool(request: ToolCreateRequest, actor: ActorContext = Depends(admin_only),
                      session: AsyncSession = Depends(get_session)) -> ToolResponse:
    result = await tool_service.register_tool(session, request, actor)
    await session.commit()
    return result


@router.get("", response_model=ToolResponsePage, operation_id="listTools",
            summary="List tools", responses=errors(401, 403))
async def list_tools(
    tool_sensitivity: ToolSensitivity | None = Query(None),
    tool_status: ToolStatus | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "tool_name"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> ToolResponsePage:
    return await tool_service.list_tools(
        session, sensitivity=tool_sensitivity, status=tool_status, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/{tool_id}", response_model=ToolResponse, operation_id="getTool",
            summary="Get tool", responses=errors(401, 403, 404))
async def get_tool(tool_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                   session: AsyncSession = Depends(get_session)) -> ToolResponse:
    return await tool_service.get_tool(session, tool_id)


@router.patch("/{tool_id}", response_model=ToolResponse, operation_id="updateTool",
              summary="Update tool", responses=errors(401, 403, 404))
async def update_tool(tool_id: uuid.UUID, request: ToolUpdateRequest,
                      actor: ActorContext = Depends(admin_only),
                      session: AsyncSession = Depends(get_session)) -> ToolResponse:
    result = await tool_service.update_tool(session, tool_id, request, actor)
    await session.commit()
    return result
