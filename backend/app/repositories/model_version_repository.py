
from __future__ import annotations

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_version import ModelVersion


async def list_model_versions(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    sort_order: str = "desc",
) -> tuple[list[ModelVersion], int]:
    """Return paginated model versions and total count."""

    count_query = select(func.count()).select_from(ModelVersion)
    total = int(await session.scalar(count_query) or 0)

    ordering = (
        asc(ModelVersion.created_at)
        if sort_order == "asc"
        else desc(ModelVersion.created_at)
    )

    query = (
        select(ModelVersion)
        .order_by(ordering, ModelVersion.model_version_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await session.execute(query)

    return list(result.scalars().all()), total
