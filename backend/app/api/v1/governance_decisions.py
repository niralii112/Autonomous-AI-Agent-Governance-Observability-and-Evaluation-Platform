"""DEC-01 and DEC-02 (spec section 11.2). Read-only: decisions are created by submit_action."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import GovernanceDecision, PolicyResult, SortOrder
from app.dependencies.auth import get_current_actor
from app.schemas import ActorContext, GovernanceDecisionResponse, GovernanceDecisionResponsePage
from app.services import decision_query_service

router = APIRouter(prefix="/governance-decisions", tags=["DEC"])


@router.get("", response_model=GovernanceDecisionResponsePage, operation_id="listGovernanceDecisions",
            summary="List governance decisions", responses=errors(401, 403, 422))
async def list_governance_decisions(
    action_id: uuid.UUID | None = Query(None),
    final_decision: GovernanceDecision | None = Query(None),
    policy_result: PolicyResult | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> GovernanceDecisionResponsePage:
    return await decision_query_service.list_decisions(
        session, action_id=action_id, final_decision=final_decision, policy_result=policy_result,
        created_from=created_from, created_to=created_to, page=page, page_size=page_size, sort_order=sort_order)


@router.get("/{governance_decision_id}", response_model=GovernanceDecisionResponse,
            operation_id="getGovernanceDecision", summary="Get governance decision", responses=errors(401, 403, 404))
async def get_governance_decision(governance_decision_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                                  session: AsyncSession = Depends(get_session)) -> GovernanceDecisionResponse:
    return await decision_query_service.get_decision(session, governance_decision_id)
