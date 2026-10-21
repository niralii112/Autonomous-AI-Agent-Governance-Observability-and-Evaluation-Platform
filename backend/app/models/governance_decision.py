import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GovernanceDecision, PolicyResult
from app.models.base import Base, created_at_col, enum_check, uuid_pk


class GovernanceDecisionRow(Base):
    """IMMUTABLE. One row per evaluation of an action (a retry adds decision_sequence + 1)."""

    __tablename__ = "governance_decisions"

    governance_decision_id: Mapped[uuid.UUID] = uuid_pk()
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.action_id", ondelete="RESTRICT"), nullable=False
    )
    decision_sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    policy_result: Mapped[str] = mapped_column(String(16), nullable=False)
    final_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decision_reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_rule_id: Mapped[str] = mapped_column(String(8), nullable=False)
    risk_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_assessments.risk_assessment_id", ondelete="SET NULL"),
    )
    matched_policy_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    policy_snapshot_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("action_id", "decision_sequence", name="uq_decisions_action_sequence"),
        Index("ix_decisions_action", "action_id"),
        Index("ix_decisions_final", "final_decision", text("decided_at DESC")),
        enum_check("final_decision", GovernanceDecision, "final_decision_valid"),
        enum_check("policy_result", PolicyResult, "policy_result_valid"),
    )
