import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActionType, AgentCategory, PolicyEffect
from app.models.base import Base, created_at_col, enum_check, updated_at_col, uuid_pk


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[uuid.UUID] = uuid_pk()
    policy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    effect: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scope_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id")
    )
    scope_agent_category: Mapped[str | None] = mapped_column(String(32))
    scope_action_type: Mapped[str | None] = mapped_column(String(48))
    supersedes_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.policy_id")
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("policy_key", "version", name="uq_policies_key_version"),
        Index("ix_policies_active_priority", "is_active", "priority"),
        Index(
            "ux_policies_one_active_version",
            "policy_key",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        enum_check("effect", PolicyEffect, "effect_valid"),
        CheckConstraint("priority BETWEEN 1 AND 1000", name="priority_range"),
        CheckConstraint("NOT is_mandatory OR effect = 'BLOCK'", name="mandatory_means_block"),
        enum_check("scope_agent_category", AgentCategory, "scope_category_valid", nullable=True),
        enum_check("scope_action_type", ActionType, "scope_action_type_valid", nullable=True),
    )
