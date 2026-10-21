"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.policy
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    AgentCategory,
    ErrorCode,
    PolicyEffect,
    PolicyOperator,
    PolicyResult,
    ToolSensitivity,
)


class PolicyActivationRequest(BaseModel):
    """Activate or deactivate one policy version."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    is_active: bool


class PolicyCondition(BaseModel):
    """Leaf condition. field is one of: action_type, agent_id, agent_category, tool_name, tool_sensitivity, or payload.<key> (dot path)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    field: str = Field(..., min_length=1, max_length=100)
    operator: PolicyOperator
    value: Any | None = Field(default=None)


class PolicyConditions(BaseModel):
    """Condition group: (all AND-list) AND (any OR-list). At least one list must be non-empty."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    all: list[PolicyCondition] = Field(default_factory=list)
    any: list[PolicyCondition] = Field(default_factory=list)


class PolicyCreateRequest(BaseModel):
    """Create version 1 of a policy. is_mandatory=true requires effect=BLOCK."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    policy_key: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=0, max_length=1000)
    effect: PolicyEffect
    priority: int = Field(..., ge=1, le=1000)
    is_mandatory: bool = Field(default=False)
    conditions: PolicyConditions
    scope_agent_id: UUID | None = Field(default=None)
    scope_agent_category: AgentCategory | None = Field(default=None)
    scope_action_type: ActionType | None = Field(default=None)


class PolicyEvaluationRequest(BaseModel):
    """Input of evaluate_policy (also the body of POL-06 dry-run; action_id may then be null)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID | None = Field(default=None)
    agent_id: UUID
    agent_category: AgentCategory
    action_type: ActionType
    tool_name: str
    tool_sensitivity: ToolSensitivity | None = Field(default=None)
    action_payload: dict[str, Any]


class MatchedPolicy(BaseModel):
    """A policy that matched."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    policy_id: UUID
    policy_key: str
    version: int
    effect: PolicyEffect
    priority: int
    is_mandatory: bool


class PolicyEvaluationResponse(BaseModel):
    """Output of evaluate_policy."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    policy_result: PolicyResult
    matched_policies: list[MatchedPolicy]
    winning_policy_id: UUID | None
    conflict_detected: bool
    evaluated_policy_count: int
    policy_snapshot_hash: str
    error_code: ErrorCode | None
    latency_ms: float


class PolicyResponse(BaseModel):
    """Policy version row."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    policy_id: UUID
    policy_key: str
    version: int
    name: str
    description: str | None
    effect: PolicyEffect
    priority: int
    is_mandatory: bool
    is_active: bool
    conditions: PolicyConditions
    scope_agent_id: UUID | None
    scope_agent_category: AgentCategory | None
    scope_action_type: ActionType | None
    supersedes_policy_id: UUID | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PolicyResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[PolicyResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class PolicyVersionCreateRequest(BaseModel):
    """Create the next version of an existing policy_key."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=0, max_length=1000)
    effect: PolicyEffect
    priority: int = Field(..., ge=1, le=1000)
    is_mandatory: bool = Field(default=False)
    conditions: PolicyConditions
    scope_agent_id: UUID | None = Field(default=None)
    scope_agent_category: AgentCategory | None = Field(default=None)
    scope_action_type: ActionType | None = Field(default=None)
