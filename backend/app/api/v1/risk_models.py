
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories import model_version_repository as repository
from app.schemas.risk import (
    ModelVersionResponse,
    ModelVersionResponsePage,
)


router = APIRouter(
    prefix="/risk-models",
    tags=["Risk Models"],
)


@router.get(
    "",
    response_model=ModelVersionResponsePage,
    operation_id="listRiskModels",
    summary="List model versions",
)
async def list_risk_models(
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^created_at$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
) -> ModelVersionResponsePage:
    rows, total = await repository.list_model_versions(
        session,
        page=page,
        page_size=page_size,
        sort_order=sort_order,
    )

    return ModelVersionResponsePage(
        items=[
            ModelVersionResponse.model_validate(row)
            for row in rows
        ],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
