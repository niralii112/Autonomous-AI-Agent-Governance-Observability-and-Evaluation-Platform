import uuid
from typing import Literal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

SortField = Literal["created_at", "username"]


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    return (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def list_users(
    session: AsyncSession,
    *,
    role: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
    sort_by: SortField,
    descending: bool,
) -> tuple[list[User], int]:
    """Returns (rows of this page, total rows matching the filters)."""
    query = select(User)
    count = select(func.count()).select_from(User)
    if role is not None:
        query, count = query.where(User.role == role), count.where(User.role == role)
    if is_active is not None:
        query, count = query.where(User.is_active == is_active), count.where(User.is_active == is_active)

    column = {"created_at": User.created_at, "username": User.username}[sort_by]  # whitelist
    direction = desc if descending else asc
    query = (
        query.order_by(direction(column), User.user_id)  # user_id makes paging stable
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await session.execute(query)).scalars())
    total = (await session.execute(count)).scalar_one()
    return rows, total
