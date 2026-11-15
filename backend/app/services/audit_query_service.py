"""Read access to the audit log (AUD-01 list, AUD-02 get). Events are WRITTEN by record_audit_event; the API cannot
change or delete them."""

import math
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, AuditEventName, AuditOutcome, SortOrder
from app.core.exceptions import NotFoundError
from app.repositories import audit_event_repository
from app.schemas import AuditEventResponse, AuditEventResponsePage


async def get_audit_event(session: AsyncSession, audit_event_id: uuid.UUID) -> AuditEventResponse:
    row = await audit_event_repository.get_by_id(session, audit_event_id)
    if row is None:
        raise NotFoundError("Audit event not found.")
    return AuditEventResponse.model_validate(row)


async def list_audit_events(
    session: AsyncSession, *, event_name: AuditEventName | None, actor_type: ActorType | None,
    outcome: AuditOutcome | None, agent_id: uuid.UUID | None, action_id: uuid.UUID | None,
    created_from: datetime | None, created_to: datetime | None, page: int, page_size: int, sort_order: SortOrder,
) -> AuditEventResponsePage:
    rows, total = await audit_event_repository.list_page(
        session, event_name=event_name.value if event_name else None,
        actor_type=actor_type.value if actor_type else None, outcome=outcome.value if outcome else None,
        agent_id=agent_id, action_id=action_id, created_from=created_from, created_to=created_to, page=page,
        page_size=page_size, descending=sort_order == SortOrder.desc)
    return AuditEventResponsePage(
        items=[AuditEventResponse.model_validate(r) for r in rows], page=page, page_size=page_size,
        total_items=total, total_pages=math.ceil(total / page_size))
