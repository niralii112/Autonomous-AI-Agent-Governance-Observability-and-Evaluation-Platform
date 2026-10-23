import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_tool_permission import AgentToolPermission
from app.models.tool import Tool


async def list_for_agent(session: AsyncSession, agent_id: uuid.UUID) -> list[tuple[AgentToolPermission, Tool]]:
    """All permission rows of one agent with their tool, ordered by tool name."""
    query = (
        select(AgentToolPermission, Tool)
        .join(Tool, Tool.tool_id == AgentToolPermission.tool_id)
        .where(AgentToolPermission.agent_id == agent_id)
        .order_by(Tool.tool_name)
    )
    return [(p, t) for p, t in (await session.execute(query)).all()]


async def get_for_agent_tool(
    session: AsyncSession, agent_id: uuid.UUID, tool_id: uuid.UUID
) -> AgentToolPermission | None:
    query = select(AgentToolPermission).where(
        AgentToolPermission.agent_id == agent_id, AgentToolPermission.tool_id == tool_id
    )
    return (await session.execute(query)).scalar_one_or_none()
