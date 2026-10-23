import uuid
from typing import Literal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool

SortField = Literal["created_at", "tool_name"]


async def get_by_id(session: AsyncSession, tool_id: uuid.UUID) -> Tool | None:
    return await session.get(Tool, tool_id)


async def get_by_name(session: AsyncSession, tool_name: str) -> Tool | None:
    return (await session.execute(select(Tool).where(Tool.tool_name == tool_name))).scalar_one_or_none()


async def get_by_action_type(session: AsyncSession, action_type: str) -> Tool | None:
    return (
        await session.execute(select(Tool).where(Tool.supported_action_type == action_type))
    ).scalar_one_or_none()


async def get_many(session: AsyncSession, tool_ids: list[uuid.UUID]) -> dict[uuid.UUID, Tool]:
    if not tool_ids:
        return {}
    rows = (await session.execute(select(Tool).where(Tool.tool_id.in_(tool_ids)))).scalars()
    return {t.tool_id: t for t in rows}


async def list_tools(
    session: AsyncSession, *, sensitivity: str | None, status: str | None,
    page: int, page_size: int, sort_by: SortField, descending: bool,
) -> tuple[list[Tool], int]:
    query, count = select(Tool), select(func.count()).select_from(Tool)
    if sensitivity is not None:
        query, count = query.where(Tool.tool_sensitivity == sensitivity), count.where(Tool.tool_sensitivity == sensitivity)
    if status is not None:
        query, count = query.where(Tool.tool_status == status), count.where(Tool.tool_status == status)
    column = {"created_at": Tool.created_at, "tool_name": Tool.tool_name}[sort_by]  # whitelist
    direction = desc if descending else asc
    query = query.order_by(direction(column), Tool.tool_id).offset((page - 1) * page_size).limit(page_size)
    rows = list((await session.execute(query)).scalars())
    return rows, (await session.execute(count)).scalar_one()
