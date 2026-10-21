import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActorType, AuditEventName, AuditOutcome
from app.models.base import Base, created_at_col, enum_check, uuid_pk


class AuditEvent(Base):
    """APPEND-ONLY: insert and select only (migration 0002 blocks UPDATE and DELETE)."""

    __tablename__ = "audit_events"

    audit_event_id: Mapped[uuid.UUID] = uuid_pk()
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="SET NULL")
    )
    action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.action_id", ondelete="SET NULL")
    )
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trace_id: Mapped[str | None] = mapped_column(CHAR(32))
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_audit_created", text("created_at DESC")),
        Index("ix_audit_event_name", "event_name"),
        Index("ix_audit_action", "action_id"),
        enum_check("event_name", AuditEventName, "event_name_valid"),
        enum_check("actor_type", ActorType, "actor_type_valid"),
        enum_check("outcome", AuditOutcome, "outcome_valid"),
    )
