"""Agent registry and agent-to-tool permissions (spec 12.1, AGT-01..06)."""

import math
import re
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ActorType, AgentCategory, AgentStatus, AuditEventName, AuditOutcome, ErrorCode, SortOrder, UserRole,
)
from app.core.exceptions import AppError, DuplicateResourceError, NotFoundError
from app.models.agent import Agent
from app.models.agent_tool_permission import AgentToolPermission
from app.repositories import agent_repository, permission_repository, tool_repository, user_repository
from app.schemas import (
    ActorContext, AgentCreateRequest, AgentResponse, AgentResponsePage, AgentUpdateRequest,
    AuditEventCreate, ToolPermissionListResponse, ToolPermissionResponse, ToolPermissionsUpdateRequest,
)
from app.services.audit_service import record_audit_event

AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,99}$")  # kebab-case (spec field registry)


def _require_admin(actor: ActorContext) -> None:
    if actor.role != UserRole.ADMIN:
        raise AppError(ErrorCode.AUTH_INSUFFICIENT_ROLE, "Your role is not allowed to do this.")


def _validation(field: str, message: str) -> AppError:
    return AppError(ErrorCode.VALIDATION_ERROR, "Request failed validation.", {field: message})


async def _audit(session, actor, event, agent_id, data) -> None:
    await record_audit_event(
        session,
        AuditEventCreate(
            event_name=event, actor_type=ActorType.USER, actor_user_id=actor.user_id, agent_id=agent_id,
            entity_type="agent", entity_id=agent_id, outcome=AuditOutcome.SUCCESS, event_data=data,
        ),
    )


async def register_agent(session: AsyncSession, request: AgentCreateRequest, actor: ActorContext) -> AgentResponse:
    _require_admin(actor)
    if not AGENT_NAME_PATTERN.match(request.agent_name):
        raise _validation("agent_name", "must be kebab-case: lowercase letters, digits and hyphens, starting with a letter")
    if await agent_repository.get_by_name(session, request.agent_name):
        raise DuplicateResourceError("An agent with this name already exists.", {"agent_name": "already exists"})
    if request.owner_user_id is not None and not await user_repository.get_by_id(session, request.owner_user_id):
        raise _validation("owner_user_id", "user not found")

    agent = Agent(
        agent_name=request.agent_name, agent_category=request.agent_category.value,
        description=request.description, trust_tier=request.trust_tier, owner_user_id=request.owner_user_id,
    )
    session.add(agent)
    try:
        await session.flush()
    except IntegrityError:
        raise DuplicateResourceError("An agent with this name already exists.") from None
    await session.refresh(agent)
    await _audit(session, actor, AuditEventName.AGENT_REGISTERED, agent.agent_id,
                 {"agent_name": agent.agent_name, "agent_category": agent.agent_category, "trust_tier": agent.trust_tier})
    return AgentResponse.model_validate(agent)


async def update_agent(
    session: AsyncSession, agent_id: uuid.UUID, request: AgentUpdateRequest, actor: ActorContext
) -> AgentResponse:
    _require_admin(actor)
    agent = await agent_repository.get_by_id(session, agent_id)
    if agent is None:
        raise NotFoundError("Agent not found.", error_code=ErrorCode.RESOURCE_NOT_FOUND)

    changed: list[str] = []
    data: dict[str, object] = {}
    if "description" in request.model_fields_set and request.description != agent.description:
        agent.description = request.description  # an explicit null clears it
        changed.append("description")
    if request.agent_status is not None and request.agent_status.value != agent.agent_status:
        data["status_from"], data["status_to"] = agent.agent_status, request.agent_status.value
        agent.agent_status = request.agent_status.value
        changed.append("agent_status")
    if request.trust_tier is not None and request.trust_tier != agent.trust_tier:
        data["trust_tier_from"], data["trust_tier_to"] = agent.trust_tier, request.trust_tier
        agent.trust_tier = request.trust_tier
        changed.append("trust_tier")

    if changed:
        await session.flush()
        await session.refresh(agent)
        await _audit(session, actor, AuditEventName.AGENT_UPDATED, agent.agent_id,
                     {"changed_fields": changed, **data})
    return AgentResponse.model_validate(agent)


async def get_agent(session: AsyncSession, agent_id: uuid.UUID) -> AgentResponse:
    agent = await agent_repository.get_by_id(session, agent_id)
    if agent is None:
        raise NotFoundError("Agent not found.")
    return AgentResponse.model_validate(agent)


async def list_agents(
    session: AsyncSession, *, category: AgentCategory | None, status: AgentStatus | None,
    page: int, page_size: int, sort_by: agent_repository.SortField, sort_order: SortOrder,
) -> AgentResponsePage:
    rows, total = await agent_repository.list_agents(
        session, category=category.value if category else None, status=status.value if status else None,
        page=page, page_size=page_size, sort_by=sort_by, descending=sort_order == SortOrder.desc,
    )
    return AgentResponsePage(
        items=[AgentResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size),
    )


async def _permission_list(session: AsyncSession, agent_id: uuid.UUID) -> ToolPermissionListResponse:
    pairs = await permission_repository.list_for_agent(session, agent_id)
    return ToolPermissionListResponse(
        agent_id=agent_id,
        permissions=[
            ToolPermissionResponse(
                permission_id=p.permission_id, agent_id=p.agent_id, tool_id=p.tool_id,
                tool_name=t.tool_name, is_allowed=p.is_allowed, created_at=p.created_at,
            )
            for p, t in pairs
        ],
    )


async def get_tool_permissions(session: AsyncSession, agent_id: uuid.UUID) -> ToolPermissionListResponse:
    if await agent_repository.get_by_id(session, agent_id) is None:
        raise NotFoundError("Agent not found.")
    return await _permission_list(session, agent_id)


async def set_tool_permissions(
    session: AsyncSession, agent_id: uuid.UUID, request: ToolPermissionsUpdateRequest, actor: ActorContext
) -> ToolPermissionListResponse:
    """REPLACES the agent's permission set with exactly the list in the request.
    A tool that is not in the list ends up with no permission row, which the decision
    engine treats as denied (rule D-04). Fail closed."""
    _require_admin(actor)
    if await agent_repository.get_by_id(session, agent_id) is None:
        raise NotFoundError("Agent not found.")

    wanted: dict[uuid.UUID, bool] = {}
    for item in request.permissions:
        if item.tool_id in wanted:
            raise _validation("permissions", f"tool_id {item.tool_id} appears more than once")
        wanted[item.tool_id] = item.is_allowed
    tools = await tool_repository.get_many(session, list(wanted))
    unknown = [str(t) for t in wanted if t not in tools]
    if unknown:
        raise _validation("permissions", f"unknown tool_id: {', '.join(unknown)}")

    existing = {p.tool_id: (p, t) for p, t in await permission_repository.list_for_agent(session, agent_id)}
    granted, denied, removed = [], [], []

    for tool_id, (perm, tool) in existing.items():
        if tool_id not in wanted:
            await session.delete(perm)
            removed.append(tool.tool_name)
    for tool_id, allowed in wanted.items():
        tool = tools[tool_id]
        if tool_id in existing:
            perm = existing[tool_id][0]
            if perm.is_allowed != allowed:
                perm.is_allowed, perm.granted_by_user_id = allowed, actor.user_id
                (granted if allowed else denied).append(tool.tool_name)
        else:
            session.add(AgentToolPermission(
                agent_id=agent_id, tool_id=tool_id, is_allowed=allowed, granted_by_user_id=actor.user_id))
            (granted if allowed else denied).append(tool.tool_name)

    await session.flush()
    if granted or denied or removed:
        await _audit(session, actor, AuditEventName.AGENT_UPDATED, agent_id, {
            "changed_fields": ["tool_permissions"],
            "granted": sorted(granted), "denied": sorted(denied), "removed": sorted(removed),
        })
    return await _permission_list(session, agent_id)
