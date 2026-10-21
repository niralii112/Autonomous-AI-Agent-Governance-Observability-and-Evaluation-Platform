import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AgentCategory, AgentStatus
from app.models.base import Base, created_at_col, enum_check, updated_at_col, uuid_pk


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[uuid.UUID] = uuid_pk()
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    agent_category: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    agent_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    trust_tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="2")
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index("ix_agents_category_status", "agent_category", "agent_status"),
        CheckConstraint("trust_tier BETWEEN 1 AND 3", name="trust_tier_range"),
        enum_check("agent_category", AgentCategory, "category_valid"),
        enum_check("agent_status", AgentStatus, "status_valid"),
    )
