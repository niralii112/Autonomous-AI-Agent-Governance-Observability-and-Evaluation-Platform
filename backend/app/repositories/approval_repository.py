import uuid
from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.approval_request import ApprovalRequest


async def get_by_id(session: AsyncSession, approval_id: uuid.UUID) -> ApprovalRequest | None:
    return await session.get(ApprovalRequest, approval_id)


async def get_locked(session: AsyncSession, approval_id: uuid.UUID) -> ApprovalRequest | None:
    # populate_existing: if this session already loaded the row, re-read its columns now that we hold the lock,
    # so a reviewer who waited for another reviewer never decides on a stale status.
    query = (select(ApprovalRequest).where(ApprovalRequest.approval_id == approval_id).with_for_update()
             .execution_options(populate_existing=True))
    return (await session.execute(query)).scalar_one_or_none()


async def for_decision(session: AsyncSession, decision_id: uuid.UUID) -> ApprovalRequest | None:
    query = select(ApprovalRequest).where(ApprovalRequest.governance_decision_id == decision_id)
    return (await session.execute(query)).scalar_one_or_none()


async def all_for_action(session: AsyncSession, action_id: uuid.UUID) -> list[ApprovalRequest]:
    query = select(ApprovalRequest).where(ApprovalRequest.action_id == action_id).order_by(ApprovalRequest.created_at)
    return list((await session.execute(query)).scalars())


async def list_page(
    session: AsyncSession, *, approval_status: str | None, agent_id: uuid.UUID | None, page: int, page_size: int,
    sort_by: str, descending: bool,
) -> tuple[list[ApprovalRequest], int]:
    """APR-01. One page of approvals plus the total. sort_by is checked against a whitelist."""
    query, count = select(ApprovalRequest), select(func.count()).select_from(ApprovalRequest)
    if agent_id is not None:  # the agent is on the action, not on the approval
        query = query.join(Action, Action.action_id == ApprovalRequest.action_id).where(Action.agent_id == agent_id)
        count = count.join(Action, Action.action_id == ApprovalRequest.action_id).where(Action.agent_id == agent_id)
    if approval_status is not None:
        query, count = (query.where(ApprovalRequest.approval_status == approval_status),
                        count.where(ApprovalRequest.approval_status == approval_status))
    column = {"created_at": ApprovalRequest.created_at, "expires_at": ApprovalRequest.expires_at}[sort_by]
    direction = desc if descending else asc
    query = (query.order_by(direction(column), ApprovalRequest.approval_id)
             .offset((page - 1) * page_size).limit(page_size))
    return list((await session.execute(query)).scalars()), (await session.execute(count)).scalar_one()


async def pending_past_expiry_locked(session: AsyncSession, now: datetime) -> list[ApprovalRequest]:
    """PENDING approvals whose time is up, row-locked. SKIP LOCKED: a reviewer who is deciding one right now
    keeps it, and the sweeper simply leaves that row for the next round."""
    query = (select(ApprovalRequest)
             .where(ApprovalRequest.approval_status == "PENDING", ApprovalRequest.expires_at <= now)
             .order_by(ApprovalRequest.expires_at).with_for_update(skip_locked=True))
    return list((await session.execute(query)).scalars())
