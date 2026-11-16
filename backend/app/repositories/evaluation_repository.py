
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action
from app.models.agent import Agent
from app.models.approval_request import ApprovalRequest
from app.models.execution import Execution
from app.models.evaluation_result import EvaluationResult
from app.models.governance_decision import GovernanceDecisionRow
from app.models.risk_assessment import RiskAssessment


async def get_production_records(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    agent_id: uuid.UUID | None = None,
):
    action_query = select(Action).where(
        Action.created_at >= window_start,
        Action.created_at <= window_end,
    )
    if agent_id:
        action_query = action_query.where(Action.agent_id == agent_id)

    actions = list(
        (await session.execute(action_query)).scalars().all()
    )
    action_ids = [item.action_id for item in actions]

    if not action_ids:
        return {
            "actions": [],
            "decisions": [],
            "approvals": [],
            "executions": [],
            "risks": [],
        }

    decisions = list(
        (
            await session.execute(
                select(GovernanceDecisionRow).where(
                    GovernanceDecisionRow.action_id.in_(action_ids)
                )
            )
        ).scalars().all()
    )

    approvals = list(
        (
            await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.action_id.in_(action_ids)
                )
            )
        ).scalars().all()
    )

    executions = list(
        (
            await session.execute(
                select(Execution).where(
                    Execution.action_id.in_(action_ids)
                )
            )
        ).scalars().all()
    )

    risks = list(
        (
            await session.execute(
                select(RiskAssessment).where(
                    RiskAssessment.action_id.in_(action_ids)
                )
            )
        ).scalars().all()
    )

    return {
        "actions": actions,
        "decisions": decisions,
        "approvals": approvals,
        "executions": executions,
        "risks": risks,
    }


async def get_agent(
    session: AsyncSession,
    agent_id: uuid.UUID,
) -> Agent | None:
    return await session.get(Agent, agent_id)


async def count_active_agents(session: AsyncSession) -> int:
    query = select(func.count()).select_from(Agent).where(
        Agent.agent_status == "ACTIVE"
    )
    return int(await session.scalar(query) or 0)


async def save_evaluation(
    session: AsyncSession,
    *,
    evaluation_type: str,
    agent_id: uuid.UUID | None,
    window_start: datetime,
    window_end: datetime,
    dataset_id: str | None,
    sample_size: int,
    metrics: dict,
    started_at: datetime,
    completed_at: datetime,
    model_version: str | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> EvaluationResult:
    row = EvaluationResult(
        evaluation_type=evaluation_type,
        agent_id=agent_id,
        window_start=window_start,
        window_end=window_end,
        dataset_id=dataset_id,
        model_version=model_version,
        sample_size=sample_size,
        metrics=metrics,
        started_at=started_at,
        completed_at=completed_at,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_evaluation(
    session: AsyncSession,
    evaluation_id: uuid.UUID,
) -> EvaluationResult | None:
    return await session.get(EvaluationResult, evaluation_id)


async def list_evaluations(
    session: AsyncSession,
    *,
    evaluation_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
    sort_order: str = "desc",
):
    filters = []

    if evaluation_type:
        filters.append(EvaluationResult.evaluation_type == evaluation_type)

    if agent_id:
        filters.append(EvaluationResult.agent_id == agent_id)

    total_query = (
        select(func.count())
        .select_from(EvaluationResult)
        .where(*filters)
    )
    total = int(await session.scalar(total_query) or 0)

    ordering = (
        EvaluationResult.created_at.asc()
        if sort_order == "asc"
        else desc(EvaluationResult.created_at)
    )

    query = (
        select(EvaluationResult)
        .where(*filters)
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    rows = list((await session.execute(query)).scalars().all())
    return rows, total
