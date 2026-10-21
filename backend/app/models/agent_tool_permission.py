import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class AgentToolPermission(Base):
    __tablename__ = "agent_tool_permissions"

    permission_id: Mapped[uuid.UUID] = uuid_pk()
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.tool_id", ondelete="CASCADE"), nullable=False
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_atp_agent_tool"),
        Index("ix_atp_tool", "tool_id"),
    )
