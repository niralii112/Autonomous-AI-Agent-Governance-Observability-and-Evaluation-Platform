"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.execution
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ErrorCode,
    ExecutionStatus,
)


class ExecutionOutcome(BaseModel):
    """Input of record_execution_result."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    execution_status: ExecutionStatus
    result_summary: dict[str, Any] | None = Field(default=None)
    error_code: ErrorCode | None = Field(default=None)
    error_message: str | None = Field(default=None)
    latency_ms: float


class ExecutionResponse(BaseModel):
    """One execution attempt."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    execution_id: UUID
    action_id: UUID
    governance_decision_id: UUID
    approval_id: UUID | None
    attempt_number: int
    execution_status: ExecutionStatus
    started_at: datetime | None
    completed_at: datetime | None
    result_summary: dict[str, Any] | None
    error_code: ErrorCode | None
    error_message: str | None
    latency_ms: float | None
    trace_id: str | None
    created_at: datetime
    updated_at: datetime


class ExecutionResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[ExecutionResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
