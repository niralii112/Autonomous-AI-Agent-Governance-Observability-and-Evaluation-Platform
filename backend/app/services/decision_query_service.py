"""Read access to stored governance decisions (DEC-01, DEC-02). Decisions are WRITTEN by submit_action."""

import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GovernanceDecision, PolicyResult, SortOrder
from app.core.exceptions import NotFoundError
from app.repositories import governance_decision_repository as repo
from app.schemas import GovernanceDecisionResponse, GovernanceDecisionResponsePage


async def get_decision(session: AsyncSession, decision_id: uuid.UUID) -> GovernanceDecisionResponse:
    row = await repo.get_by_id(session, decision_id)
    if row is None:
        raise NotFoundError("Governance decision not found.")
    return GovernanceDecisionResponse.model_validate(row)


async def list_decisions(
    session: AsyncSession, *, action_id: uuid.UUID | None, final_decision: GovernanceDecision | None,
    policy_result: PolicyResult | None, created_from: datetime | None, created_to: datetime | None,
    page: int, page_size: int, sort_order: SortOrder,
) -> GovernanceDecisionResponsePage:
    rows, total = await repo.list_decisions(
        session, action_id=action_id, final_decision=final_decision.value if final_decision else None,
        policy_result=policy_result.value if policy_result else None, created_from=created_from,
        created_to=created_to, page=page, page_size=page_size, descending=sort_order == SortOrder.desc)
    return GovernanceDecisionResponsePage(
        items=[GovernanceDecisionResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size))
