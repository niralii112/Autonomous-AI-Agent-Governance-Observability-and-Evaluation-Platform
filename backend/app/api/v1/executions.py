"""EXE-01 and EXE-02 (spec section 11.2). Read-only: executions are created by submit_action, approve_action and
retry_action, and only execution_service changes them."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import ExecutionStatus, SortOrder
from app.dependencies.auth import get_current_actor
from app.schemas import ActorContext, ExecutionResponse, ExecutionResponsePage
from app.services import execution_query_service

router = APIRouter(prefix="/executions", tags=["EXE"])


@router.get("", response_model=ExecutionResponsePage, operation_id="listExecutions", summary="List executions",
            responses=errors(401, 403, 422))
async def list_executions(
    action_id: uuid.UUID | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    execution_status: ExecutionStatus | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at", "latency_ms"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
) -> ExecutionResponsePage:
    return await execution_query_service.list_executions(
        session, action_id=action_id, agent_id=agent_id, execution_status=execution_status,
        created_from=created_from, created_to=created_to, page=page, page_size=page_size, sort_by=sort_by,
        sort_order=sort_order)


@router.get("/{execution_id}", response_model=ExecutionResponse, operation_id="getExecution",
            summary="Get execution", responses=errors(401, 403, 404))
async def get_execution(execution_id: uuid.UUID, _: ActorContext = Depends(get_current_actor),
                        session: AsyncSession = Depends(get_session)) -> ExecutionResponse:
    return await execution_query_service.get_execution(session, execution_id)
