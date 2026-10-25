import uuid
from typing import Literal

from sqlalchemy import asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy

SortField = Literal["created_at", "priority", "policy_key"]


async def get_by_id(session: AsyncSession, policy_id: uuid.UUID) -> Policy | None:
    return await session.get(Policy, policy_id)


async def key_exists(session: AsyncSession, policy_key: str) -> bool:
    query = select(func.count()).select_from(Policy).where(Policy.policy_key == policy_key)
    return (await session.execute(query)).scalar_one() > 0


async def lock_versions(session: AsyncSession, policy_key: str) -> list[Policy]:
    """All versions of one policy, newest first, after taking a lock on that policy_key.

    The advisory lock makes concurrent "create next version" requests for the same policy
    wait for each other. It is released at the end of the transaction. Row locks alone are
    not enough: a waiting request would not see the version the first request just inserted.
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": policy_key})
    query = (select(Policy).where(Policy.policy_key == policy_key)
             .order_by(Policy.version.desc()).with_for_update())
    return list((await session.execute(query)).scalars())


async def get_active_for_key(session: AsyncSession, policy_key: str) -> Policy | None:
    query = select(Policy).where(Policy.policy_key == policy_key, Policy.is_active.is_(True))
    return (await session.execute(query)).scalar_one_or_none()


async def list_active_ordered(session: AsyncSession) -> list[Policy]:
    """Active policies ordered by priority then policy_key (what the policy engine reads)."""
    query = select(Policy).where(Policy.is_active.is_(True)).order_by(Policy.priority, Policy.policy_key)
    return list((await session.execute(query)).scalars())


async def list_policies(
    session: AsyncSession, *, effect: str | None, is_active: bool | None, policy_key: str | None,
    page: int, page_size: int, sort_by: SortField, descending: bool,
) -> tuple[list[Policy], int]:
    query, count = select(Policy), select(func.count()).select_from(Policy)
    for column, value in ((Policy.effect, effect), (Policy.is_active, is_active), (Policy.policy_key, policy_key)):
        if value is not None:
            query, count = query.where(column == value), count.where(column == value)
    column = {"created_at": Policy.created_at, "priority": Policy.priority, "policy_key": Policy.policy_key}[sort_by]
    direction = desc if descending else asc
    query = (query.order_by(direction(column), Policy.policy_key, Policy.version.desc(), Policy.policy_id)
             .offset((page - 1) * page_size).limit(page_size))
    rows = list((await session.execute(query)).scalars())
    return rows, (await session.execute(count)).scalar_one()
