import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EvaluationType
from app.models.base import Base, created_at_col, enum_check, uuid_pk


class EvaluationResult(Base):
    """IMMUTABLE after insert."""

    __tablename__ = "evaluation_results"

    evaluation_id: Mapped[uuid.UUID] = uuid_pk()
    evaluation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="SET NULL")
    )
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dataset_id: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("model_versions.model_version", ondelete="SET NULL")
    )
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_eval_type_created", "evaluation_type", text("created_at DESC")),
        enum_check("evaluation_type", EvaluationType, "type_valid"),
    )
