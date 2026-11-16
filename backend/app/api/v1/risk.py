
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.enums import RiskLevel, RiskSource, UserRole
from app.dependencies.auth import require_roles
from app.repositories import risk_assessment_repository as repository
from app.schemas.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskAssessmentResponsePage,
    RiskLevelCount,
    RiskSourceCount,
    RiskSummaryResponse,
    ScoreBucket,
)
from app.services.risk_service import assess_risk


router = APIRouter(
    prefix="/risk-assessments",
    tags=["Risk Assessment"],
)

admin_or_operator = require_roles(UserRole.ADMIN, UserRole.OPERATOR)


@router.post(
    "/dry-run",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    operation_id="assessRiskDryRun",
    summary="Assess risk without persisting or executing an action",
    dependencies=[Depends(admin_or_operator)],
)
async def dry_run_risk(
    request: RiskAssessmentRequest,
) -> RiskAssessmentResponse:
    try:
        result = await assess_risk(request)
        return RiskAssessmentResponse.model_validate(result)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment failed.",
        ) from exc


@router.get(
    "",
    response_model=RiskAssessmentResponsePage,
    operation_id="listRiskAssessments",
    summary="List risk assessments",
)
async def list_risk_assessments(
    risk_level: str | None = None,
    risk_source: str | None = None,
    action_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(created_at|risk_score)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
) -> RiskAssessmentResponsePage:
    if created_from and created_to and created_from > created_to:
        raise HTTPException(
            status_code=422,
            detail="created_from must not be later than created_to.",
        )

    rows, total = await repository.list_assessments(
        session,
        risk_level=risk_level,
        risk_source=risk_source,
        action_id=action_id,
        created_from=created_from,
        created_to=created_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = math.ceil(total / page_size) if total else 0

    return RiskAssessmentResponsePage(
        items=[
            RiskAssessmentResponse.model_validate(row)
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
    )


@router.get(
    "/summary",
    response_model=RiskSummaryResponse,
    operation_id="getRiskSummary",
    summary="Aggregates for risk monitoring charts",
)
async def get_risk_summary(
    window_hours: int = Query(24, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
) -> RiskSummaryResponse:
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    rows = await repository.get_summary_rows(
        session,
        window_start=window_start,
        window_end=window_end,
    )

    total = len(rows)

    level_counts = {level: 0 for level in RiskLevel}
    source_counts = {source: 0 for source in RiskSource}

    score_bucket_counts = [0, 0, 0, 0, 0]
    latency_values: list[float] = []
    fallback_count = 0

    for row in rows:
        level = RiskLevel(row.risk_level)
        source = RiskSource(row.risk_source)

        level_counts[level] += 1
        source_counts[source] += 1

        if source == RiskSource.HEURISTIC_FALLBACK:
            fallback_count += 1

        score = float(row.risk_score)
        bucket_index = min(int(score * 5), 4)
        score_bucket_counts[bucket_index] += 1

        if row.latency_ms is not None:
            latency_values.append(float(row.latency_ms))

    return RiskSummaryResponse(
        window_start=window_start,
        window_end=window_end,
        total_assessments=total,
        by_risk_level=[
            RiskLevelCount(
                risk_level=level,
                count=count,
            )
            for level, count in level_counts.items()
        ],
        by_risk_source=[
            RiskSourceCount(
                risk_source=source,
                count=count,
            )
            for source, count in source_counts.items()
        ],
        score_buckets=[
            ScoreBucket(
                bucket_start=index * 0.2,
                bucket_end=(index + 1) * 0.2,
                count=count,
            )
            for index, count in enumerate(score_bucket_counts)
        ],
        avg_latency_ms=(
            sum(latency_values) / len(latency_values)
            if latency_values
            else None
        ),
        fallback_rate=(
            fallback_count / total
            if total
            else None
        ),
    )


@router.get(
    "/{risk_assessment_id}",
    response_model=RiskAssessmentResponse,
    operation_id="getRiskAssessment",
    summary="Get a risk assessment",
)
async def get_risk_assessment(
    risk_assessment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RiskAssessmentResponse:
    row = await repository.get_by_id(session, risk_assessment_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk assessment not found.",
        )

    return RiskAssessmentResponse.model_validate(row)
