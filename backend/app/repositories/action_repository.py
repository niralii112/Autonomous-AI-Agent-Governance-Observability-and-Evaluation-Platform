import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.action import Action
from app.models.agent import Agent
from app.models.approval_request import ApprovalRequest
from app.models.execution import Execution
from app.models.governance_decision import GovernanceDecisionRow
from app.models.risk_assessment import RiskAssessment

SortField = Literal["created_at", "risk_score"]


async def get_by_id(session: AsyncSession, action_id: uuid.UUID) -> Action | None:
    return await session.get(Action, action_id)


async def get_by_agent_and_key(session: AsyncSession, agent_id: uuid.UUID, key: str) -> Action | None:
    query = select(Action).where(Action.agent_id == agent_id, Action.idempotency_key == key)
    return (await session.execute(query)).scalar_one_or_none()


async def list_summaries(
    session: AsyncSession, *, action_id: uuid.UUID | None = None, agent_id: uuid.UUID | None, action_type: str | None, final_decision: str | None,
    approval_status: str | None, execution_status: str | None, risk_level: str | None,
    created_from: datetime | None, created_to: datetime | None, page: int, page_size: int,
    sort_by: SortField, descending: bool,
) -> tuple[list, int]:
    """One row per action with the LATEST decision, approval and execution and the risk assessment
    the latest decision used. Returns (rows, total)."""
    dec = (select(GovernanceDecisionRow).distinct(GovernanceDecisionRow.action_id)
           .order_by(GovernanceDecisionRow.action_id, GovernanceDecisionRow.decision_sequence.desc()).subquery())
    apr = (select(ApprovalRequest).distinct(ApprovalRequest.action_id)
           .order_by(ApprovalRequest.action_id, ApprovalRequest.created_at.desc()).subquery())
    exe = (select(Execution).distinct(Execution.action_id)
           .order_by(Execution.action_id, Execution.attempt_number.desc()).subquery())
    risk = aliased(RiskAssessment)

    base = (
        select(Action, Agent.agent_name, dec.c.policy_result, dec.c.final_decision, risk.risk_score, risk.risk_level,
               apr.c.approval_status, exe.c.execution_status)
        .join(Agent, Agent.agent_id == Action.agent_id)
        .outerjoin(dec, dec.c.action_id == Action.action_id)
        .outerjoin(risk, risk.risk_assessment_id == dec.c.risk_assessment_id)
        .outerjoin(apr, apr.c.action_id == Action.action_id)
        .outerjoin(exe, exe.c.action_id == Action.action_id)
    )
    conditions = []
    if action_id is not None:
        conditions.append(Action.action_id == action_id)
    if agent_id is not None:
        conditions.append(Action.agent_id == agent_id)
    if action_type is not None:
        conditions.append(Action.action_type == action_type)
    if final_decision is not None:
        conditions.append(dec.c.final_decision == final_decision)
    if approval_status is not None:
        conditions.append(apr.c.approval_status == approval_status)
    if execution_status is not None:
        conditions.append(exe.c.execution_status == execution_status)
    if risk_level is not None:
        conditions.append(risk.risk_level == risk_level)
    if created_from is not None:
        conditions.append(Action.created_at >= created_from)
    if created_to is not None:
        conditions.append(Action.created_at <= created_to)
    for condition in conditions:  # only the filters that were supplied
        base = base.where(condition)

    total = (await session.execute(select(func.count()).select_from(base.order_by(None).subquery()))).scalar_one()
    column = {"created_at": Action.created_at, "risk_score": risk.risk_score}[sort_by]  # whitelist
    ordering = (desc(column).nulls_last() if descending else asc(column).nulls_last())
    rows = (await session.execute(
        base.order_by(ordering, Action.action_id).offset((page - 1) * page_size).limit(page_size))).all()
    return rows, total


async def trace_ids_for(session: AsyncSession, action: Action) -> list[str]:
    found = {action.trace_id} if action.trace_id else set()
    rows = (await session.execute(select(Execution.trace_id).where(Execution.action_id == action.action_id))).scalars()
    found |= {t for t in rows if t}
    return sorted(found)
