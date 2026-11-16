
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.enums import UserRole
from app.dependencies.auth import require_roles
from app.repositories import evaluation_repository as repository
from app.schemas.evaluation import (
    AgentPerformanceResponse,
    EvaluationResultResponse,
    EvaluationResultResponsePage,
    EvaluationRunRequest,
    OverviewMetricsResponse,
    ProductionMetrics,
)
from app.services.evaluation_service import (
    evaluate_agent_performance,
    evaluate_production_records,
)


router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluation"],
)

admin_only = require_roles(UserRole.ADMIN)


def _value(value):
    return getattr(value, "value", value)


def _evaluation_response(row) -> EvaluationResultResponse:
    """Convert database JSON metrics into the contract response."""

    return EvaluationResultResponse(
        evaluation_id=row.evaluation_id,
        evaluation_type=row.evaluation_type,
        agent_id=row.agent_id,
        window_start=row.window_start,
        window_end=row.window_end,
        dataset_id=row.dataset_id,
        model_version=row.model_version,
        sample_size=row.sample_size,
        production_metrics=(
            ProductionMetrics.model_validate(row.metrics)
            if row.evaluation_type == "PRODUCTION"
            else None
        ),
        labelled_metrics=None,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


@router.post(
    "/runs",
    response_model=EvaluationResultResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="runEvaluation",
    summary="Run and save an evaluation",
    dependencies=[Depends(admin_only)],
)
async def run_evaluation(
    request: EvaluationRunRequest,
    session: AsyncSession = Depends(get_session),
) -> EvaluationResultResponse:

    evaluation_type = str(_value(request.evaluation_type)).upper()

    if evaluation_type != "PRODUCTION":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Only PRODUCTION evaluation is currently connected to "
                "the production database. A labelled dataset provider "
                "must be configured for labelled evaluation."
            ),
        )

    started_at = datetime.now(timezone.utc)
    window_end = started_at
    window_start = window_end - timedelta(hours=request.window_hours)

    records = await repository.get_production_records(
        session,
        window_start,
        window_end,
        request.agent_id,
    )

    metrics = evaluate_production_records(records)

    completed_at = datetime.now(timezone.utc)

    row = await repository.save_evaluation(
        session,
        evaluation_type="PRODUCTION",
        agent_id=request.agent_id,
        window_start=window_start,
        window_end=window_end,
        dataset_id=None,
        sample_size=len(records["actions"]),
        metrics=metrics,
        started_at=started_at,
        completed_at=completed_at,
    )

    await session.commit()
    await session.refresh(row)

    return _evaluation_response(row)


@router.get(
    "",
    response_model=EvaluationResultResponsePage,
    operation_id="listEvaluations",
    summary="List saved evaluations",
)
async def list_evaluations(
    evaluation_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^created_at$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResultResponsePage:

    rows, total = await repository.list_evaluations(
        session,
        evaluation_type=evaluation_type,
        agent_id=agent_id,
        page=page,
        page_size=page_size,
        sort_order=sort_order,
    )

    return EvaluationResultResponsePage(
        items=[
            _evaluation_response(row)
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.get(
    "/agent-performance",
    response_model=AgentPerformanceResponse,
    operation_id="getAgentPerformance",
    summary="Get production performance for an agent",
)
async def get_agent_performance(
    agent_id: uuid.UUID,
    window_hours: int = Query(24, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
) -> AgentPerformanceResponse:

    agent = await repository.get_agent(session, agent_id)

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    result = await evaluate_agent_performance(
        session,
        agent_id,
        window_start,
        window_end,
    )

    return AgentPerformanceResponse.model_validate(result)


@router.get(
    "/overview",
    response_model=OverviewMetricsResponse,
    operation_id="getOverviewMetrics",
    summary="Get production overview metrics",
)
async def get_overview_metrics(
    window_hours: int = Query(24, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
) -> OverviewMetricsResponse:

    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    records = await repository.get_production_records(
        session,
        window_start,
        window_end,
    )

    metrics = evaluate_production_records(records)

    pending_approvals = sum(
        1
        for item in records["approvals"]
        if _value(item.approval_status) == "PENDING"
    )

    running_executions = sum(
        1
        for item in records["executions"]
        if _value(item.execution_status) == "RUNNING"
    )

    failed_executions = sum(
        1
        for item in records["executions"]
        if _value(item.execution_status) == "FAILED"
    )

    average_risk = (
        sum(float(item.risk_score) for item in records["risks"])
        / len(records["risks"])
        if records["risks"]
        else None
    )

    return OverviewMetricsResponse(
        window_start=window_start,
        window_end=window_end,
        total_actions=metrics["total_actions"],
        allow_count=metrics["allow_count"],
        human_review_count=metrics["human_review_count"],
        block_count=metrics["block_count"],
        pending_approvals=pending_approvals,
        running_executions=running_executions,
        failed_executions=failed_executions,
        active_agents=await repository.count_active_agents(session),
        avg_risk_score=average_risk,
        actions_over_time=[],
        recent_actions=[],
    )


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationResultResponse,
    operation_id="getEvaluation",
    summary="Get a saved evaluation",
)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> EvaluationResultResponse:

    row = await repository.get_evaluation(
        session,
        evaluation_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evaluation not found.",
        )

    return _evaluation_response(row)
