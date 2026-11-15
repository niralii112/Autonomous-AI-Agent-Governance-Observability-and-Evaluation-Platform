"""APR-01..05 (spec section 11.2).

approve, reject and cancel do NOT use require_roles: approval_service checks the role itself, so that a refused
attempt is written to the audit log (APPROVAL_DENIED_UNAUTHORIZED) before the 403 is returned (T-08).
The service commits its own transactions, so these routers do not commit.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import ApprovalStatus, SortOrder
from app.dependencies.auth import get_current_actor
from app.schemas import (
    ActorContext, ApprovalDecisionResponse, ApprovalRejectRequest, ApprovalResponse, ApprovalResponsePage,
    ApprovalReviewRequest,
)
from app.services import approval_query_service, approval_service

router = APIRouter(prefix="/approvals", tags=["APR"])


@router.get("", response_model=ApprovalResponsePage, operation_id="listApprovals", summary="List approvals",
            responses=errors(401, 403, 422))
async def list_approvals(
    approval_status: ApprovalStatus | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "expires_at"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponsePage:
    return await approval_query_service.list_approvals(
        session, approval_status=approval_status, agent_id=agent_id, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/{approval_id}", response_model=ApprovalResponse, operation_id="getApproval", summary="Get approval",
            responses=errors(401, 403, 404))
async def get_approval(approval_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                       session: AsyncSession = Depends(get_session)) -> ApprovalResponse:
    return await approval_query_service.get_approval(session, approval_id)


@router.post("/{approval_id}/approve", response_model=ApprovalDecisionResponse, operation_id="approveAction",
             summary="Approve a held action and run it", responses=errors(401, 403, 404, 409, 422, 503))
async def approve_action(approval_id: uuid.UUID, request: ApprovalReviewRequest | None = None,
                         actor: ActorContext = Depends(get_current_actor),
                         session: AsyncSession = Depends(get_session)) -> ApprovalDecisionResponse:
    return await approval_service.approve_action(session, approval_id, request or ApprovalReviewRequest(), actor)


@router.post("/{approval_id}/reject", response_model=ApprovalDecisionResponse, operation_id="rejectAction",
             summary="Reject a held action", responses=errors(401, 403, 404, 409, 422))
async def reject_action(approval_id: uuid.UUID, request: ApprovalRejectRequest,
                        actor: ActorContext = Depends(get_current_actor),
                        session: AsyncSession = Depends(get_session)) -> ApprovalDecisionResponse:
    return await approval_service.reject_action(session, approval_id, request, actor)


@router.post("/{approval_id}/cancel", response_model=ApprovalDecisionResponse, operation_id="cancelApproval",
             summary="Cancel a pending approval", responses=errors(401, 403, 404, 409))
async def cancel_approval(approval_id: uuid.UUID, actor: ActorContext = Depends(get_current_actor),
                          session: AsyncSession = Depends(get_session)) -> ApprovalDecisionResponse:
    return await approval_service.cancel_approval(session, approval_id, actor)
