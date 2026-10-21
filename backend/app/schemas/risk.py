"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.risk
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    AgentCategory,
    RiskLevel,
    RiskSource,
    ToolSensitivity,
)


class RiskContext(BaseModel):
    """History context supplied by action_service to the risk service."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    recent_blocked_count_24h: int = Field(..., ge=0, le=100000)
    recent_failed_count_24h: int = Field(..., ge=0, le=100000)
    agent_trust_tier: int = Field(..., ge=1, le=3)
    submitted_at: datetime


class RiskAssessmentRequest(BaseModel):
    """Canonical input of assess_risk (also body of RSK-01)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID
    agent_id: UUID
    agent_category: AgentCategory
    action_type: ActionType
    tool_name: str
    tool_sensitivity: ToolSensitivity
    action_payload: dict[str, Any]
    context: RiskContext


class RiskAssessmentResponse(BaseModel):
    """Canonical output of assess_risk; persisted as-is by action_service."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    risk_assessment_id: UUID
    action_id: UUID
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: RiskLevel
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    risk_source: RiskSource
    model_version: str
    reason_codes: list[str]
    features: dict[str, Any]
    latency_ms: float
    created_at: datetime


class RiskAssessmentResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[RiskAssessmentResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class RiskLevelCount(BaseModel):
    """Count per level."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    risk_level: RiskLevel
    count: int


class RiskSourceCount(BaseModel):
    """Count per source."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    risk_source: RiskSource
    count: int


class ScoreBucket(BaseModel):
    """Histogram bucket [bucket_start, bucket_end)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    bucket_start: float
    bucket_end: float
    count: int


class RiskSummaryResponse(BaseModel):
    """Risk monitoring aggregates."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    window_start: datetime
    window_end: datetime
    total_assessments: int
    by_risk_level: list[RiskLevelCount]
    by_risk_source: list[RiskSourceCount]
    score_buckets: list[ScoreBucket]
    avg_latency_ms: float | None
    fallback_rate: float | None


class ModelVersionResponse(BaseModel):
    """Registered model version."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    model_version_id: UUID
    model_version: str
    model_kind: RiskSource
    algorithm: str
    feature_schema_version: str
    artifact_path: str | None
    artifact_sha256: str | None
    training_dataset_hash: str | None
    metrics: dict[str, Any] | None
    is_active: bool
    trained_at: datetime | None
    created_at: datetime


class ModelVersionResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[ModelVersionResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
