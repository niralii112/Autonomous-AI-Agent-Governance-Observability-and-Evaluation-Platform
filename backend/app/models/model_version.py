import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, Boolean, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import RiskSource
from app.models.base import Base, created_at_col, enum_check, uuid_pk


class ModelVersion(Base):
    __tablename__ = "model_versions"

    model_version_id: Mapped[uuid.UUID] = uuid_pk()
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    model_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(255))
    artifact_sha256: Mapped[str | None] = mapped_column(CHAR(64))
    training_dataset_hash: Mapped[str | None] = mapped_column(CHAR(64))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index(
            "ux_model_one_active",
            "model_kind",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        enum_check("model_kind", RiskSource, "kind_valid"),
    )
