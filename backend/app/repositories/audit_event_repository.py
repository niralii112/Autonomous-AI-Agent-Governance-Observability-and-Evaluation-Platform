from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


async def add(session: AsyncSession, **fields) -> AuditEvent:
    row = AuditEvent(**fields)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row
