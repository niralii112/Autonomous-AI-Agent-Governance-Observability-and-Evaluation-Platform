"""Base class for the sample agents.

An agent only PROPOSES actions. It never runs a tool: every proposal goes
through Student 1's submit_action, where the policy, the risk score, the
human approval and the execution grant decide what really happens.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any

from app.agents.scenarios import get_scenario_spec, scenarios_for_category
from app.core.enums import (
    AgentCategory,
    ApprovalStatus,
    ErrorCode,
    ExecutionStatus,
    GovernanceDecision,
    RiskLevel,
)
from app.core.exceptions import AppError, NotFoundError
from app.schemas.action import ActionSubmissionRequest
from app.schemas.agent_run import AgentScenario


@dataclass(frozen=True)
class AgentOutcome:
    """A short summary of what governance did with one proposal."""

    action_id: uuid.UUID
    final_decision: GovernanceDecision
    risk_level: RiskLevel | None
    approval_status: ApprovalStatus | None
    execution_status: ExecutionStatus | None
    duplicate: bool


class BaseAgent:
    """Common behaviour of the Finance and Customer Support agents."""

    # Every agent class sets its own category.
    agent_category: AgentCategory

    def __init__(self, agent_id: uuid.UUID, agent_name: str) -> None:
        if not hasattr(self, "agent_category"):
            raise TypeError("An agent class must set agent_category")

        if not agent_name.strip():
            raise ValueError("agent_name cannot be empty")

        self.agent_id = agent_id
        self.agent_name = agent_name

    def list_scenarios(self) -> list[AgentScenario]:
        """The fixed scenarios this agent can run."""
        return scenarios_for_category(self.agent_category)

    def propose_action(
        self,
        scenario_key: str,
        idempotency_key: str | None = None,
    ) -> ActionSubmissionRequest:
        """Turn a scenario into an action request. Nothing is executed here."""
        spec = get_scenario_spec(self.agent_category, scenario_key)

        if spec is None:
            raise NotFoundError(
                "Scenario not found.",
                {"scenario_key": scenario_key},
            )

        scenario = spec.scenario

        return ActionSubmissionRequest(
            agent_id=self.agent_id,
            tool_name=scenario.tool_name,
            action_type=scenario.action_type,
            # A copy, so changing the proposal never changes the scenario.
            action_payload=copy.deepcopy(scenario.action_payload),
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    async def discover_tools(self, session: Any) -> list[str]:
        """Names of the tools this agent is allowed to use, from the registry."""
        from app.services import agent_service

        permissions = await agent_service.get_tool_permissions(session, self.agent_id)

        return sorted(
            permission.tool_name
            for permission in permissions.permissions
            if permission.is_allowed
        )

    async def submit_proposal(
        self,
        session: Any,
        proposal: ActionSubmissionRequest,
        actor: Any,
    ) -> Any:
        """Send a proposal to governance. This is the only way an agent acts."""
        from app.services.action_service import submit_action

        if proposal.agent_id != self.agent_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "An agent can only submit its own proposals.",
            )

        return await submit_action(session, proposal, actor)

    def handle_result(self, response: Any) -> AgentOutcome:
        """Summarise the governance response for evaluation."""
        risk = response.risk_assessment
        approval = response.approval
        execution = response.execution

        return AgentOutcome(
            action_id=response.action.action_id,
            final_decision=response.governance_decision.final_decision,
            risk_level=risk.risk_level if risk is not None else None,
            approval_status=approval.approval_status if approval is not None else None,
            execution_status=execution.execution_status if execution is not None else None,
            duplicate=response.duplicate,
        )
