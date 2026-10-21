import uuid
from datetime import datetime

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ActionType, ToolSensitivity, ToolStatus
from app.models.base import Base, created_at_col, enum_check, updated_at_col, uuid_pk


class Tool(Base):
    __tablename__ = "tools"

    tool_id: Mapped[uuid.UUID] = uuid_pk()
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    tool_sensitivity: Mapped[str] = mapped_column(String(16), nullable=False)
    supported_action_type: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    tool_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index("ix_tools_sensitivity", "tool_sensitivity"),
        enum_check("tool_sensitivity", ToolSensitivity, "sensitivity_valid"),
        enum_check("supported_action_type", ActionType, "action_type_valid"),
        enum_check("tool_status", ToolStatus, "status_valid"),
    )
