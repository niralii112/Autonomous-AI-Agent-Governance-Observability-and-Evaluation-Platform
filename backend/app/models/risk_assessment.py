import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import RiskLevel, RiskSource
from app.models.base import Base, created_at_col, enum_check


class RiskAssessment(Base):
    """IMMUTABLE. The id is set by assess_risk (Student 2), so it has no database default."""

    __tablename__ = "risk_assessments"

    risk_assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.action_id", ondelete="RESTRICT"), nullable=False
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    risk_source: Mapped[str] = mapped_column(String(24), nullable=False)
    model_version: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("model_versions.model_version", ondelete="RESTRICT"),
        nullable=False,
    )
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_risk_action", "action_id"),
        Index("ix_risk_created", text("created_at DESC")),
        Index("ix_risk_level", "risk_level"),
        CheckConstraint("risk_score BETWEEN 0 AND 1", name="score_range"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        enum_check("risk_level", RiskLevel, "level_valid"),
        enum_check("risk_source", RiskSource, "source_valid"),
    )
