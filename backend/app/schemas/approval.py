"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.approval
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ApprovalStatus,
)
from app.schemas.action import ActionSummary
from app.schemas.execution import ExecutionResponse


class ApprovalResponse(BaseModel):
    """Approval request. action_summary is embedded for the queue screen."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    approval_id: UUID
    action_id: UUID
    governance_decision_id: UUID
    approval_status: ApprovalStatus
    requested_at: datetime
    expires_at: datetime
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_comment: str | None
    consumed_at: datetime | None
    action_summary: ActionSummary | None
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionResponse(BaseModel):
    """Result of approve/reject/cancel. execution present only after approve with ALLOW-path execution."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    approval: ApprovalResponse
    execution: ExecutionResponse | None


class ApprovalRejectRequest(BaseModel):
    """Reject (comment mandatory)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    review_comment: str = Field(..., min_length=1, max_length=1000)


class ApprovalResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[ApprovalResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class ApprovalReviewRequest(BaseModel):
    """Approve."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    review_comment: str | None = Field(default=None, min_length=0, max_length=1000)
