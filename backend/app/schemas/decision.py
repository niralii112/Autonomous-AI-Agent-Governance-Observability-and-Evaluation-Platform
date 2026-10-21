"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.decision
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AgentStatus,
    GovernanceDecision,
    PolicyResult,
    ToolSensitivity,
    ToolStatus,
)
from app.schemas.policy import PolicyEvaluationResponse
from app.schemas.risk import RiskAssessmentResponse


class GovernanceDecisionOutcome(BaseModel):
    """Pure output of make_governance_decision."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    final_decision: GovernanceDecision
    decision_reason_code: str
    decision_rule_id: str


class GovernanceDecisionRequest(BaseModel):
    """Pure input of make_governance_decision."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action_id: UUID
    agent_status: AgentStatus
    tool_found: bool
    tool_status: ToolStatus | None = Field(default=None)
    agent_tool_permitted: bool
    tool_sensitivity: ToolSensitivity | None = Field(default=None)
    policy_evaluation: PolicyEvaluationResponse
    risk_assessment: RiskAssessmentResponse | None = Field(default=None)
    no_match_decision: GovernanceDecision


class GovernanceDecisionResponse(BaseModel):
    """Stored decision (immutable)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    governance_decision_id: UUID
    action_id: UUID
    decision_sequence: int
    policy_result: PolicyResult
    final_decision: GovernanceDecision
    decision_reason_code: str
    decision_rule_id: str
    risk_assessment_id: UUID | None
    matched_policy_ids: list[UUID]
    policy_snapshot_hash: str
    payload_hash: str
    decided_at: datetime
    created_at: datetime


class GovernanceDecisionResponsePage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    items: list[GovernanceDecisionResponse]
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
