import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
