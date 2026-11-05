from datetime import datetime, timezone

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
