"""Tool registry (spec 12.2, TLS-01..04). Metadata only: the tool CODE is Student 2's."""

import math
import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ActorType, AuditEventName, AuditOutcome, ErrorCode, SortOrder, ToolSensitivity, ToolStatus, UserRole,
)
from app.core.exceptions import AppError, DuplicateResourceError, NotFoundError
from app.models.tool import Tool
from app.repositories import tool_repository
from app.schemas import (
    ActorContext, AuditEventCreate, ToolCreateRequest, ToolResponse, ToolResponsePage, ToolUpdateRequest,
)
from app.services.audit_service import record_audit_event

TOOL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,99}$")  # snake_case (spec field registry)


def _require_admin(actor: ActorContext) -> None:
    if actor.role != UserRole.ADMIN:
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")


async def _audit(session, actor, event, tool_id, data) -> None:
    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=event, actor_type=ActorType.USER, actor_user_id=actor.user_id,
            entity_type="tool", entity_id=tool_id, outcome=AuditOutcome.SUCCESS, event_data=data,
        ),
    )


async def register_tool(session: AsyncSession, request: ToolCreateRequest, actor: ActorContext) -> ToolResponse:
    _require_admin(actor)
    if not TOOL_NAME_PATTERN.match(request.tool_name):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Request failed validation.",
                       {"tool_name": "must be snake_case: lowercase letters, digits and underscores, starting with a letter"})
    if await tool_repository.get_by_name(session, request.tool_name):
        raise DuplicateResourceError("A tool with this name already exists.", {"tool_name": "already exists"})
    # one tool per action type: governance must know exactly which tool runs an action
    if await tool_repository.get_by_action_type(session, request.supported_action_type.value):
        raise DuplicateResourceError("Another tool already supports this action type.",
                                     {"supported_action_type": "already supported by another tool"})

    tool = Tool(
        tool_name=request.tool_name, description=request.description,
        tool_sensitivity=request.tool_sensitivity.value,
        supported_action_type=request.supported_action_type.value,
    )
    session.add(tool)
    try:
        await session.flush()
    except IntegrityError:
        raise DuplicateResourceError("A tool with these unique values already exists.") from None
    await session.refresh(tool)
    await _audit(session, actor, AuditEventName.TOOL_REGISTERED, tool.tool_id, {
        "tool_name": tool.tool_name, "tool_sensitivity": tool.tool_sensitivity,
        "supported_action_type": tool.supported_action_type})
    return ToolResponse.model_validate(tool)


async def update_tool(
    session: AsyncSession, tool_id: uuid.UUID, request: ToolUpdateRequest, actor: ActorContext
) -> ToolResponse:
    """Only description and status can change; sensitivity and action type are fixed at registration."""
    _require_admin(actor)
    tool = await tool_repository.get_by_id(session, tool_id)
    if tool is None:
        raise NotFoundError("Tool not found.")

    changed: list[str] = []
    data: dict[str, object] = {}
    if "description" in request.model_fields_set and request.description != tool.description:
        tool.description = request.description
        changed.append("description")
    if request.tool_status is not None and request.tool_status.value != tool.tool_status:
        data["status_from"], data["status_to"] = tool.tool_status, request.tool_status.value
        tool.tool_status = request.tool_status.value
        changed.append("tool_status")
    if changed:
        await session.flush()
        await session.refresh(tool)
        await _audit(session, actor, AuditEventName.TOOL_UPDATED, tool.tool_id, {"changed_fields": changed, **data})
    return ToolResponse.model_validate(tool)


async def get_tool(session: AsyncSession, tool_id: uuid.UUID) -> ToolResponse:
    tool = await tool_repository.get_by_id(session, tool_id)
    if tool is None:
        raise NotFoundError("Tool not found.")
    return ToolResponse.model_validate(tool)


async def list_tools(
    session: AsyncSession, *, sensitivity: ToolSensitivity | None, status: ToolStatus | None,
    page: int, page_size: int, sort_by: tool_repository.SortField, sort_order: SortOrder,
) -> ToolResponsePage:
    rows, total = await tool_repository.list_tools(
        session, sensitivity=sensitivity.value if sensitivity else None, status=status.value if status else None,
        page=page, page_size=page_size, sort_by=sort_by, descending=sort_order == SortOrder.desc,
    )
    return ToolResponsePage(
        items=[ToolResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size),
    )
