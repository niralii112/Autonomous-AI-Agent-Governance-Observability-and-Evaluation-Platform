"""ACT-01..03 (spec section 11.2). ACT-04 (retry) comes with the approval flow."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import (
    ActionType, ApprovalStatus, ExecutionStatus, GovernanceDecision, RiskLevel, SortOrder, UserRole,
)
from app.dependencies.auth import get_current_actor, require_roles
from app.schemas import (
    ActionDetailResponse, ActionSubmissionRequest, ActionSubmissionResponse, ActionSummaryPage, ActorContext,
)
from app.services import action_query_service, action_service

router = APIRouter(prefix="/actions", tags=["ACT"])
admin_or_operator = require_roles(UserRole.ADMIN, UserRole.OPERATOR)


@router.post("", response_model=ActionSubmissionResponse, operation_id="submitAction",
             summary="Submit an agent action for governance", responses=errors(401, 403, 404, 409, 422, 503))
async def submit_action(request: ActionSubmissionRequest, actor: ActorContext = Depends(admin_or_operator),
                        session: AsyncSession = Depends(get_session)) -> ActionSubmissionResponse:
    # submit_action commits its own transactions (spec: three of them), so the router does not commit.
    return await action_service.submit_action(session, request, actor)


@router.get("", response_model=ActionSummaryPage, operation_id="listActions", summary="List actions",
            responses=errors(401, 403))
async def list_actions(
    agent_id: uuid.UUID | None = Query(None),
    action_type: ActionType | None = Query(None),
    final_decision: GovernanceDecision | None = Query(None),
    approval_status: ApprovalStatus | None = Query(None),
    execution_status: ExecutionStatus | None = Query(None),
    risk_level: RiskLevel | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "risk_score"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> ActionSummaryPage:
    return await action_query_service.list_actions(
        session, agent_id=agent_id, action_type=action_type, final_decision=final_decision,
        approval_status=approval_status, execution_status=execution_status, risk_level=risk_level,
        created_from=created_from, created_to=created_to, page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order)


@router.get("/{action_id}", response_model=ActionDetailResponse, operation_id="getAction",
            summary="Get an action with its decisions, risk, approvals and executions", responses=errors(401, 403, 404))
async def get_action(action_id: uuid.UUID, actor: ActorContext = Depends(get_current_actor),
                     session: AsyncSession = Depends(get_session)) -> ActionDetailResponse:
    return await action_query_service.get_action_detail(session, action_id, actor)
