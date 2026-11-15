import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


async def add(session: AsyncSession, **fields) -> AuditEvent:
    # Stamp each event with its own time. The database's now() is fixed for a whole transaction, so several
    # events written together would otherwise share one timestamp and lose their order.
    row = AuditEvent(created_at=datetime.now(timezone.utc), **fields)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def get_by_id(session: AsyncSession, audit_event_id: uuid.UUID) -> AuditEvent | None:
    return await session.get(AuditEvent, audit_event_id)


async def list_page(
    session: AsyncSession, *, event_name: str | None, actor_type: str | None, outcome: str | None,
    agent_id: uuid.UUID | None, action_id: uuid.UUID | None, created_from: datetime | None,
    created_to: datetime | None, page: int, page_size: int, descending: bool,
) -> tuple[list[AuditEvent], int]:
    """AUD-01. Read only: the audit log is append-only. sort_by is always created_at."""
    query, count = select(AuditEvent), select(func.count()).select_from(AuditEvent)
    conditions = []
    if event_name is not None:
        conditions.append(AuditEvent.event_name == event_name)
    if actor_type is not None:
        conditions.append(AuditEvent.actor_type == actor_type)
    if outcome is not None:
        conditions.append(AuditEvent.outcome == outcome)
    if agent_id is not None:
        conditions.append(AuditEvent.agent_id == agent_id)
    if action_id is not None:
        conditions.append(AuditEvent.action_id == action_id)
    if created_from is not None:
        conditions.append(AuditEvent.created_at >= created_from)
    if created_to is not None:
        conditions.append(AuditEvent.created_at <= created_to)
    for condition in conditions:  # only the filters that were supplied
        query, count = query.where(condition), count.where(condition)
    direction = desc if descending else asc
    query = (query.order_by(direction(AuditEvent.created_at), AuditEvent.audit_event_id)
             .offset((page - 1) * page_size).limit(page_size))
    return list((await session.execute(query)).scalars()), (await session.execute(count)).scalar_one()
