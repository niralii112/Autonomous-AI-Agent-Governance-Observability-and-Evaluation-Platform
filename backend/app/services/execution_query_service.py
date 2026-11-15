"""Read access to executions (EXE-01 list, EXE-02 get). Executions are WRITTEN by execution_service."""

import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ExecutionStatus, SortOrder
from app.core.exceptions import NotFoundError
from app.repositories import execution_repository
from app.schemas import ExecutionResponse, ExecutionResponsePage


async def get_execution(session: AsyncSession, execution_id: uuid.UUID) -> ExecutionResponse:
    row = await execution_repository.get_by_id(session, execution_id)
    if row is None:
        raise NotFoundError("Execution not found.")
    return ExecutionResponse.model_validate(row)


async def list_executions(
    session: AsyncSession, *, action_id: uuid.UUID | None, agent_id: uuid.UUID | None,
    execution_status: ExecutionStatus | None, created_from: datetime | None, created_to: datetime | None,
    page: int, page_size: int, sort_by: str, sort_order: SortOrder,
) -> ExecutionResponsePage:
    rows, total = await execution_repository.list_page(
        session, action_id=action_id, agent_id=agent_id,
        execution_status=execution_status.value if execution_status else None, created_from=created_from,
        created_to=created_to, page=page, page_size=page_size, sort_by=sort_by,
        descending=sort_order == SortOrder.desc)
    return ExecutionResponsePage(
        items=[ExecutionResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size))
