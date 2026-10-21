"""Generated from contracts/openapi.yaml by scripts/generate_schemas.py. Do not edit by hand.

Module: app.schemas.agent_run
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ActionType,
    GovernanceDecision,
)
from app.schemas.action_detail import ActionSubmissionResponse


class AgentScenario(BaseModel):
    """A deterministic runnable scenario."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    scenario_key: str
    action_type: ActionType
    tool_name: str
    description: str
    expected_decision: GovernanceDecision
    action_payload: dict[str, Any]


class AgentScenarioListResponse(BaseModel):
    """Scenarios of an agent."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    scenarios: list[AgentScenario]


class AgentRunRequest(BaseModel):
    """Run a scenario through governance."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    scenario_key: str = Field(..., min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class AgentRunResponse(BaseModel):
    """Result of running a scenario."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, protected_namespaces=())

    agent_id: UUID
    scenario_key: str
    submission: ActionSubmissionResponse
