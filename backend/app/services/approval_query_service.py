"""Read access to approvals (APR-01 list, APR-02 get). Approving, rejecting and cancelling are in approval_service."""

import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApprovalStatus, SortOrder
from app.core.exceptions import NotFoundError
from app.repositories import approval_repository
from app.schemas import ApprovalResponse, ApprovalResponsePage
from app.services.action_views import approval_response


async def get_approval(session: AsyncSession, approval_id: uuid.UUID) -> ApprovalResponse:
    approval = await approval_repository.get_by_id(session, approval_id)
    if approval is None:
        raise NotFoundError("Approval not found.")
    return await approval_response(session, approval)


async def list_approvals(
    session: AsyncSession, *, approval_status: ApprovalStatus | None, agent_id: uuid.UUID | None, page: int,
    page_size: int, sort_by: str, sort_order: SortOrder,
) -> ApprovalResponsePage:
    rows, total = await approval_repository.list_page(
        session, approval_status=approval_status.value if approval_status else None, agent_id=agent_id,
        page=page, page_size=page_size, sort_by=sort_by, descending=sort_order == SortOrder.desc)
    return ApprovalResponsePage(
        items=[await approval_response(session, row) for row in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size))
