"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.evaluation
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AgentCategory,
    EvaluationType,
)
from app.schemas.action import ActionSummary


class CategoryMetric(BaseModel):
    """Per agent_category metrics."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_category: AgentCategory
    support: int
    precision: float | None
    recall: float | None
    f1_score: float | None


class ConfusionMatrix(BaseModel):
    """Binary confusion matrix (positive = label_high_risk 1)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    true_negative: int
    false_positive: int
    false_negative: int
    true_positive: int


class LabelledMetrics(BaseModel):
    """Metrics computed ONLY from a labelled dataset."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    dataset_id: str
    dataset_size: int
    positive_rate: float
    threshold_used: float
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1_score: float | None
    roc_auc: float | None
    confusion_matrix: ConfusionMatrix
    per_agent_category: list[CategoryMetric]


class ProductionMetrics(BaseModel):
    """Metrics computed ONLY from execution/decision/approval records. No precision or recall: production events carry no ground-truth labels."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    total_actions: int
    allow_count: int
    human_review_count: int
    block_count: int
    executions_total: int
    succeeded_count: int
    failed_count: int
    approved_count: int
    rejected_count: int
    expired_count: int
    policy_violation_count: int
    task_completion_rate: float | None
    execution_success_rate: float | None
    blocked_action_rate: float | None
    human_review_rate: float | None
    approval_rate: float | None
    rejection_rate: float | None
    policy_violation_rate: float | None
    fallback_risk_rate: float | None
    avg_tool_latency_ms: float | None
    p95_tool_latency_ms: float | None
    agent_reliability_score: float | None


class EvaluationResultResponse(BaseModel):
    """Stored evaluation. Exactly one of production_metrics / labelled_metrics is non-null, matching evaluation_type."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    evaluation_id: UUID
    evaluation_type: EvaluationType
    agent_id: UUID | None
    window_start: datetime | None
    window_end: datetime | None
    dataset_id: str | None
    model_version: str | None
    sample_size: int
    production_metrics: ProductionMetrics | None
    labelled_metrics: LabelledMetrics | None
    started_at: datetime
    completed_at: datetime
    created_by_user_id: UUID | None
    created_at: datetime


class EvaluationResultResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[EvaluationResultResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class EvaluationRunRequest(BaseModel):
    """Run and store an evaluation."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    evaluation_type: EvaluationType
    agent_id: UUID | None = Field(default=None)
    window_hours: int = Field(default=24, ge=1, le=720)
    dataset_id: str = Field(default='risk_eval_v1', min_length=1, max_length=64)


class TimeBucketCount(BaseModel):
    """Decisions per time bucket."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    bucket_start: datetime
    allow_count: int
    human_review_count: int
    block_count: int


class OverviewMetricsResponse(BaseModel):
    """Data of the overview dashboard."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    window_start: datetime
    window_end: datetime
    total_actions: int
    allow_count: int
    human_review_count: int
    block_count: int
    pending_approvals: int
    running_executions: int
    failed_executions: int
    active_agents: int
    avg_risk_score: float | None
    actions_over_time: list[TimeBucketCount]
    recent_actions: list[ActionSummary]


class AgentPerformanceResponse(BaseModel):
    """Production metrics for one agent over a window."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    agent_name: str
    window_start: datetime
    window_end: datetime
    metrics: ProductionMetrics
