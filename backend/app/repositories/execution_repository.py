import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.execution import Execution


async def get_by_id(session: AsyncSession, execution_id: uuid.UUID) -> Execution | None:
    return await session.get(Execution, execution_id)


async def get_locked(session: AsyncSession, execution_id: uuid.UUID) -> Execution | None:
    """The execution row with a row lock (SELECT ... FOR UPDATE)."""
    query = select(Execution).where(Execution.execution_id == execution_id).with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def latest_for_action(session: AsyncSession, action_id: uuid.UUID) -> Execution | None:
    query = (select(Execution).where(Execution.action_id == action_id)
             .order_by(Execution.attempt_number.desc()).limit(1))
    return (await session.execute(query)).scalar_one_or_none()


async def all_for_action(session: AsyncSession, action_id: uuid.UUID) -> list[Execution]:
    query = select(Execution).where(Execution.action_id == action_id).order_by(Execution.attempt_number)
    return list((await session.execute(query)).scalars())


async def count_failed_since(session: AsyncSession, agent_id: uuid.UUID, since: datetime,
                             exclude_action_id: uuid.UUID | None = None) -> int:
    """FAILED executions of this agent's actions since `since` (risk feature recent_failed_count_24h)."""
    query = (select(func.count()).select_from(Execution).join(Action, Action.action_id == Execution.action_id)
             .where(Action.agent_id == agent_id, Execution.execution_status == "FAILED", Execution.created_at >= since))
    if exclude_action_id is not None:
        query = query.where(Execution.action_id != exclude_action_id)
    return (await session.execute(query)).scalar_one()
