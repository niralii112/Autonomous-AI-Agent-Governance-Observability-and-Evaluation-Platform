import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ExecutionStatus
from app.models.base import Base, created_at_col, enum_check, updated_at_col, uuid_pk
from sqlalchemy import text


class Execution(Base):
    """One row per attempt. PENDING -> RUNNING -> terminal; retries insert a new row."""

    __tablename__ = "executions"

    execution_id: Mapped[uuid.UUID] = uuid_pk()
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.action_id", ondelete="RESTRICT"), nullable=False
    )
    governance_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_decisions.governance_decision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.approval_id", ondelete="RESTRICT")
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    execution_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    trace_id: Mapped[str | None] = mapped_column(CHAR(32))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("action_id", "attempt_number", name="uq_exec_action_attempt"),
        Index("ix_exec_status", "execution_status"),
        Index("ix_exec_action", "action_id"),
        Index("ix_exec_created", text("created_at DESC")),
        Index("ix_exec_trace", "trace_id"),
        enum_check("execution_status", ExecutionStatus, "status_valid"),
        CheckConstraint("attempt_number >= 1", name="attempt_positive"),
        CheckConstraint(
            "execution_status <> 'SUCCEEDED' OR (started_at IS NOT NULL"
            " AND completed_at IS NOT NULL AND error_code IS NULL)",
            name="succeeded_fields",
        ),
        CheckConstraint(
            "execution_status <> 'FAILED' OR error_code IS NOT NULL",
            name="failed_has_error_code",
        ),
        CheckConstraint(
            "execution_status <> 'BLOCKED' OR started_at IS NULL",
            name="blocked_never_started",
        ),
    )
