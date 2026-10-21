import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActionType
from app.models.base import Base, created_at_col, enum_check, uuid_pk


class Action(Base):
    """IMMUTABLE after insert (migration 0002 adds a trigger)."""

    __tablename__ = "actions"

    action_id: Mapped[uuid.UUID] = uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="RESTRICT"), nullable=False
    )
    tool_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.tool_id", ondelete="RESTRICT")
    )
    requested_tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(48), nullable=False)
    action_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    trace_id: Mapped[str | None] = mapped_column(CHAR(32))
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("agent_id", "idempotency_key", name="uq_actions_agent_idempotency"),
        Index("ix_actions_created_at", text("created_at DESC")),
        Index("ix_actions_agent_created", "agent_id", text("created_at DESC")),
        Index("ix_actions_type", "action_type"),
        Index("ix_actions_trace", "trace_id"),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="payload_hash_format"),
        enum_check("action_type", ActionType, "action_type_valid"),
    )
