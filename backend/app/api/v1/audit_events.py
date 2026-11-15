"""AUD-01 and AUD-02 (spec section 11.2). Read-only, ADMIN and REVIEWER only. The audit log is append-only:
there is deliberately no write route here."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.responses import errors
from app.core.database import get_session
from app.core.enums import ActorType, AuditEventName, AuditOutcome, SortOrder, UserRole
from app.dependencies.auth import require_roles
from app.schemas import ActorContext, AuditEventResponse, AuditEventResponsePage
from app.services import audit_query_service

router = APIRouter(prefix="/audit-events", tags=["AUD"])
admin_or_reviewer = require_roles(UserRole.ADMIN, UserRole.REVIEWER)


@router.get("", response_model=AuditEventResponsePage, operation_id="listAuditEvents",
            summary="List audit events", responses=errors(401, 403, 422))
async def list_audit_events(
    event_name: AuditEventName | None = Query(None),
    actor_type: ActorType | None = Query(None),
    outcome: AuditOutcome | None = Query(None),
    agent_id: uuid.UUID | None = Query(None),
    action_id: uuid.UUID | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: Literal["created_at"] = Query("created_at"),
    sort_order: SortOrder = Query(SortOrder.desc),
    _: ActorContext = Depends(admin_or_reviewer),
    session: AsyncSession = Depends(get_session),
) -> AuditEventResponsePage:
    return await audit_query_service.list_audit_events(
        session, event_name=event_name, actor_type=actor_type, outcome=outcome, agent_id=agent_id,
        action_id=action_id, created_from=created_from, created_to=created_to, page=page, page_size=page_size,
        sort_order=sort_order)


@router.get("/{audit_event_id}", response_model=AuditEventResponse, operation_id="getAuditEvent",
            summary="Get audit event", responses=errors(401, 403, 404))
async def get_audit_event(audit_event_id: uuid.UUID, _: ActorContext = Depends(admin_or_reviewer),
                          session: AsyncSession = Depends(get_session)) -> AuditEventResponse:
    return await audit_query_service.get_audit_event(session, audit_event_id)
