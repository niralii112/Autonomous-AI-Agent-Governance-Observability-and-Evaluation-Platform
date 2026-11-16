
from __future__ import annotations

import math
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_version import ModelVersion
from app.models.risk_assessment import RiskAssessment
from app.schemas import RiskAssessmentResponse


async def get_by_id(
    session: AsyncSession,
    risk_assessment_id: uuid.UUID,
) -> RiskAssessment | None:
    return await session.get(RiskAssessment, risk_assessment_id)


async def all_for_action(
    session: AsyncSession,
    action_id: uuid.UUID,
) -> list[RiskAssessment]:
    query = (
        select(RiskAssessment)
        .where(RiskAssessment.action_id == action_id)
        .order_by(RiskAssessment.created_at)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def ensure_model_version(
    session: AsyncSession,
    response: RiskAssessmentResponse,
) -> bool:
    """Register an inactive placeholder if the referenced model is unknown."""
    stmt = (
        pg_insert(ModelVersion)
        .values(
            model_version=response.model_version,
            model_kind=response.risk_source.value,
            algorithm="unregistered",
            feature_schema_version="unknown",
            is_active=False,
        )
        .on_conflict_do_nothing(
            index_elements=["model_version"]
        )
        .returning(ModelVersion.model_version_id)
    )
    result = await session.execute(stmt)
    return result.first() is not None


async def add(
    session: AsyncSession,
    response: RiskAssessmentResponse,
) -> RiskAssessment:
    """Persist an assessment returned by assess_risk."""
    row = RiskAssessment(
        risk_assessment_id=response.risk_assessment_id,
        action_id=response.action_id,
        risk_score=response.risk_score,
        risk_level=response.risk_level.value,
        confidence_score=response.confidence_score,
        risk_source=response.risk_source.value,
        model_version=response.model_version,
        features=response.features,
        reason_codes=response.reason_codes,
        latency_ms=response.latency_ms,
        created_at=response.created_at,
    )
    session.add(row)
    await session.flush()
    return row


async def list_assessments(
    session: AsyncSession,
    *,
    risk_level: str | None = None,
    risk_source: str | None = None,
    action_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[RiskAssessment], int]:
    """Return filtered risk assessments and their total count."""

    filters: list[Any] = []

    if risk_level:
        filters.append(RiskAssessment.risk_level == risk_level)

    if risk_source:
        filters.append(RiskAssessment.risk_source == risk_source)

    if action_id:
        filters.append(RiskAssessment.action_id == action_id)

    if created_from:
        filters.append(RiskAssessment.created_at >= created_from)

    if created_to:
        filters.append(RiskAssessment.created_at <= created_to)

    count_query = (
        select(func.count())
        .select_from(RiskAssessment)
        .where(*filters)
    )
    total = int(await session.scalar(count_query) or 0)

    sort_column = (
        RiskAssessment.risk_score
        if sort_by == "risk_score"
        else RiskAssessment.created_at
    )
    ordering = asc(sort_column) if sort_order == "asc" else desc(sort_column)

    query = (
        select(RiskAssessment)
        .where(*filters)
        .order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await session.execute(query)
    return list(result.scalars().all()), total


async def get_summary_rows(
    session: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[RiskAssessment]:
    """Fetch assessments in a time window for summary aggregation."""
    query = (
        select(RiskAssessment)
        .where(
            RiskAssessment.created_at >= window_start,
            RiskAssessment.created_at <= window_end,
        )
        .order_by(RiskAssessment.created_at)
    )
    result = await session.execute(query)
    return list(result.scalars().all())
