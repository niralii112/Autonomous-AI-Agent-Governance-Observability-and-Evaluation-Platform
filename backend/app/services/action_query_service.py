"""Read access to actions (ACT-02 list, ACT-03 detail). VIEWERs see the payload redacted."""

import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ActionType, ApprovalStatus, ExecutionStatus, GovernanceDecision, RiskLevel, SortOrder, UserRole,
)
from app.core.exceptions import NotFoundError
from app.repositories import (
    action_repository, approval_repository, execution_repository, risk_assessment_repository,
)
from app.repositories import governance_decision_repository as decision_repository
from app.schemas import (
    ActionDetailResponse, ActionSummaryPage, ActorContext, ExecutionResponse,
    GovernanceDecisionResponse, RiskAssessmentResponse,
)
from app.services.action_views import action_response, approval_response, summary_from_row


async def list_actions(
    session: AsyncSession, *, agent_id: uuid.UUID | None, action_type: ActionType | None,
    final_decision: GovernanceDecision | None, approval_status: ApprovalStatus | None,
    execution_status: ExecutionStatus | None, risk_level: RiskLevel | None, created_from: datetime | None,
    created_to: datetime | None, page: int, page_size: int, sort_by: action_repository.SortField, sort_order: SortOrder,
) -> ActionSummaryPage:
    rows, total = await action_repository.list_summaries(
        session, agent_id=agent_id, action_type=action_type.value if action_type else None,
        final_decision=final_decision.value if final_decision else None,
        approval_status=approval_status.value if approval_status else None,
        execution_status=execution_status.value if execution_status else None,
        risk_level=risk_level.value if risk_level else None, created_from=created_from, created_to=created_to,
        page=page, page_size=page_size, sort_by=sort_by, descending=sort_order == SortOrder.desc)
    items = [summary_from_row(row) for row in rows]
    return ActionSummaryPage(items=items, page=page, page_size=page_size, total_items=total,
                             total_pages=math.ceil(total / page_size))


async def get_action_detail(session: AsyncSession, action_id: uuid.UUID, actor: ActorContext) -> ActionDetailResponse:
    action = await action_repository.get_by_id(session, action_id)
    if action is None:
        raise NotFoundError("Action not found.")
    return ActionDetailResponse(
        action=action_response(action, redact=actor.role == UserRole.VIEWER),
        governance_decisions=[GovernanceDecisionResponse.model_validate(d)
                              for d in await decision_repository.all_for_action(session, action_id)],
        risk_assessments=[RiskAssessmentResponse.model_validate(r)
                          for r in await risk_assessment_repository.all_for_action(session, action_id)],
        approvals=[await approval_response(session, a) for a in await approval_repository.all_for_action(session, action_id)],
        executions=[ExecutionResponse.model_validate(e) for e in await execution_repository.all_for_action(session, action_id)],
        trace_ids=await action_repository.trace_ids_for(session, action))
