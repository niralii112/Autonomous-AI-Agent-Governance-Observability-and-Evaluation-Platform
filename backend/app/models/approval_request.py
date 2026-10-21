import uuid
from datetime import datetime

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ApprovalStatus
from app.models.base import Base, created_at_col, enum_check, updated_at_col, uuid_pk


class ApprovalRequest(Base):
    """Status moves PENDING -> terminal once; consumed_at is set at most once; never deleted."""

    __tablename__ = "approval_requests"

    approval_id: Mapped[uuid.UUID] = uuid_pk()
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.action_id", ondelete="RESTRICT"), nullable=False
    )
    governance_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_decisions.governance_decision_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index("ix_approvals_status_expires", "approval_status", "expires_at"),
        Index("ix_approvals_action", "action_id"),
        enum_check("approval_status", ApprovalStatus, "status_valid"),
        CheckConstraint(
            "(approval_status IN ('APPROVED','REJECTED')"
            " AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL)"
            " OR (approval_status NOT IN ('APPROVED','REJECTED')"
            " AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL)",
            name="reviewer_set_iff_reviewed",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR approval_status = 'APPROVED'",
            name="consumed_only_if_approved",
        ),
    )
