"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.action
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    ApprovalStatus,
    ExecutionStatus,
    GovernanceDecision,
    PolicyResult,
    RiskLevel,
)


class ActionSubmissionRequest(BaseModel):
    """Propose an action. Used by agents (in-process) and by ACT-01."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    tool_name: str = Field(..., min_length=1, max_length=100)
    action_type: ActionType
    action_payload: dict[str, Any]
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class ActionResponse(BaseModel):
    """Stored action. action_payload is null and payload_redacted true for VIEWER."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID
    agent_id: UUID
    tool_id: UUID | None
    requested_tool_name: str
    action_type: ActionType
    action_payload: dict[str, Any] | None
    payload_redacted: bool
    payload_hash: str
    idempotency_key: str
    submitted_by_user_id: UUID | None
    trace_id: str | None
    created_at: datetime


class ActionSummary(BaseModel):
    """Row of action lists and approval queue."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID
    agent_id: UUID
    agent_name: str
    action_type: ActionType
    requested_tool_name: str
    policy_result: PolicyResult | None
    final_decision: GovernanceDecision | None
    risk_score: float | None
    risk_level: RiskLevel | None
    approval_status: ApprovalStatus | None
    execution_status: ExecutionStatus | None
    trace_id: str | None
    created_at: datetime


class ActionSummaryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[ActionSummary]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class ActionHistoryFilter(BaseModel):
    """Filters of get_action_history."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID | None = Field(default=None)
    action_type: ActionType | None = Field(default=None)
    final_decision: GovernanceDecision | None = Field(default=None)
    approval_status: ApprovalStatus | None = Field(default=None)
    execution_status: ExecutionStatus | None = Field(default=None)
    risk_level: RiskLevel | None = Field(default=None)
    created_from: datetime | None = Field(default=None)
    created_to: datetime | None = Field(default=None)


def __getattr__(name: str):
    """ActionSubmissionResponse and ActionDetailResponse live in action_detail.py (avoids a
    circular import). This keeps `from app.schemas.action import ActionSubmissionResponse` working."""
    if name in ("ActionSubmissionResponse", "ActionDetailResponse"):
        from app.schemas import action_detail

        return getattr(action_detail, name)
    raise AttributeError(name)
