import uuid
from datetime import datetime

from sqlalchemy import asc, desc, func, select
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


async def list_page(
    session: AsyncSession, *, action_id: uuid.UUID | None, agent_id: uuid.UUID | None, execution_status: str | None,
    created_from: datetime | None, created_to: datetime | None, page: int, page_size: int, sort_by: str,
    descending: bool,
) -> tuple[list[Execution], int]:
    """EXE-01. One page of executions plus the total. sort_by is checked against a whitelist."""
    query, count = select(Execution), select(func.count()).select_from(Execution)
    if agent_id is not None:  # the agent is on the action, not on the execution
        query = query.join(Action, Action.action_id == Execution.action_id).where(Action.agent_id == agent_id)
        count = count.join(Action, Action.action_id == Execution.action_id).where(Action.agent_id == agent_id)
    conditions = []
    if action_id is not None:
        conditions.append(Execution.action_id == action_id)
    if execution_status is not None:
        conditions.append(Execution.execution_status == execution_status)
    if created_from is not None:
        conditions.append(Execution.created_at >= created_from)
    if created_to is not None:
        conditions.append(Execution.created_at <= created_to)
    for condition in conditions:  # only the filters that were supplied
        query, count = query.where(condition), count.where(condition)
    column = {"created_at": Execution.created_at, "latency_ms": Execution.latency_ms}[sort_by]
    ordering = desc(column).nulls_last() if descending else asc(column).nulls_last()
    query = query.order_by(ordering, Execution.execution_id).offset((page - 1) * page_size).limit(page_size)
    return list((await session.execute(query)).scalars()), (await session.execute(count)).scalar_one()


async def stale_running_locked(session: AsyncSession, started_before: datetime) -> list[Execution]:
    """RUNNING executions that started before `started_before`, row-locked (SKIP LOCKED)."""
    query = (select(Execution)
             .where(Execution.execution_status == "RUNNING", Execution.started_at <= started_before)
             .order_by(Execution.started_at).with_for_update(skip_locked=True))
    return list((await session.execute(query)).scalars())
