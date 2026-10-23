"""Append-only audit log (spec 12: record_audit_event). The caller's unit of work commits."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.trace_context import current_trace_id
from app.repositories import audit_event_repository
from app.schemas import AuditEventCreate, AuditEventResponse


async def record_audit_event(session: AsyncSession, event: AuditEventCreate) -> AuditEventResponse:
    row = await audit_event_repository.add(
        session,
        event_name=event.event_name.value,
        actor_type=event.actor_type.value,
        actor_user_id=event.actor_user_id,
        agent_id=event.agent_id,
        action_id=event.action_id,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        trace_id=current_trace_id(),
        outcome=event.outcome.value,
        event_data=event.event_data,
    )
    return AuditEventResponse.model_validate(row)
