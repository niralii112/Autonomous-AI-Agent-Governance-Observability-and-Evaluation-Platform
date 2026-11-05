import uuid
from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance_decision import GovernanceDecisionRow as Decision


async def get_by_id(session: AsyncSession, decision_id: uuid.UUID) -> Decision | None:
    return await session.get(Decision, decision_id)


async def list_decisions(
    session: AsyncSession, *, action_id: uuid.UUID | None, final_decision: str | None, policy_result: str | None,
    created_from: datetime | None, created_to: datetime | None, page: int, page_size: int, descending: bool,
) -> tuple[list[Decision], int]:
    query, count = select(Decision), select(func.count()).select_from(Decision)
    conditions = []
    if action_id is not None:
        conditions.append(Decision.action_id == action_id)
    if final_decision is not None:
        conditions.append(Decision.final_decision == final_decision)
    if policy_result is not None:
        conditions.append(Decision.policy_result == policy_result)
    if created_from is not None:
        conditions.append(Decision.created_at >= created_from)
    if created_to is not None:
        conditions.append(Decision.created_at <= created_to)
    for condition in conditions:  # only filters that were actually supplied
        query, count = query.where(condition), count.where(condition)
    direction = desc if descending else asc  # sort_by is always created_at (the contract allows nothing else)
    query = (query.order_by(direction(Decision.created_at), Decision.governance_decision_id)
             .offset((page - 1) * page_size).limit(page_size))
    rows = list((await session.execute(query)).scalars())
    return rows, (await session.execute(count)).scalar_one()


async def latest_for_action(session: AsyncSession, action_id: uuid.UUID) -> Decision | None:
    query = (select(Decision).where(Decision.action_id == action_id)
             .order_by(Decision.decision_sequence.desc()).limit(1))
    return (await session.execute(query)).scalar_one_or_none()


async def all_for_action(session: AsyncSession, action_id: uuid.UUID) -> list[Decision]:
    query = select(Decision).where(Decision.action_id == action_id).order_by(Decision.decision_sequence)
    return list((await session.execute(query)).scalars())


async def count_blocked_since(session: AsyncSession, agent_id: uuid.UUID, since: datetime,
                              exclude_action_id: uuid.UUID | None = None) -> int:
    """BLOCK decisions on this agent's actions since `since` (risk feature recent_blocked_count_24h)."""
    from app.models.action import Action

    query = (select(func.count()).select_from(Decision).join(Action, Action.action_id == Decision.action_id)
             .where(Action.agent_id == agent_id, Decision.final_decision == "BLOCK", Decision.created_at >= since))
    if exclude_action_id is not None:
        query = query.where(Decision.action_id != exclude_action_id)
    return (await session.execute(query)).scalar_one()
