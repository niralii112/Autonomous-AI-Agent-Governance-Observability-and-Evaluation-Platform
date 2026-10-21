"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.action_detail
"""

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.action import ActionResponse
from app.schemas.approval import ApprovalResponse
from app.schemas.decision import GovernanceDecisionResponse
from app.schemas.execution import ExecutionResponse
from app.schemas.policy import PolicyEvaluationResponse
from app.schemas.risk import RiskAssessmentResponse


class ActionSubmissionResponse(BaseModel):
    """Complete outcome of submit_action / retry."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action: ActionResponse
    policy_evaluation: PolicyEvaluationResponse
    risk_assessment: RiskAssessmentResponse | None
    governance_decision: GovernanceDecisionResponse
    approval: ApprovalResponse | None
    execution: ExecutionResponse | None
    duplicate: bool


class ActionDetailResponse(BaseModel):
    """Everything known about one action."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    action: ActionResponse
    governance_decisions: list[GovernanceDecisionResponse]
    risk_assessments: list[RiskAssessmentResponse]
    approvals: list[ApprovalResponse]
    executions: list[ExecutionResponse]
    trace_ids: list[str]
