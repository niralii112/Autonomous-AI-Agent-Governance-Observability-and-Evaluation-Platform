import uuid
from typing import Literal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

SortField = Literal["created_at", "agent_name"]


async def get_by_id(session: AsyncSession, agent_id: uuid.UUID) -> Agent | None:
    return await session.get(Agent, agent_id)


async def get_by_name(session: AsyncSession, agent_name: str) -> Agent | None:
    return (await session.execute(select(Agent).where(Agent.agent_name == agent_name))).scalar_one_or_none()


async def list_agents(
    session: AsyncSession, *, category: str | None, status: str | None,
    page: int, page_size: int, sort_by: SortField, descending: bool,
) -> tuple[list[Agent], int]:
    query, count = select(Agent), select(func.count()).select_from(Agent)
    if category is not None:
        query, count = query.where(Agent.agent_category == category), count.where(Agent.agent_category == category)
    if status is not None:
        query, count = query.where(Agent.agent_status == status), count.where(Agent.agent_status == status)
    column = {"created_at": Agent.created_at, "agent_name": Agent.agent_name}[sort_by]  # whitelist
    direction = desc if descending else asc
    query = query.order_by(direction(column), Agent.agent_id).offset((page - 1) * page_size).limit(page_size)
    rows = list((await session.execute(query)).scalars())
    return rows, (await session.execute(count)).scalar_one()
