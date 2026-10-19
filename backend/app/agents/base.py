
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRunOutcome:
    """Internal result of an agent scenario run."""

    scenario_key: str
    status: str
    proposed_actions: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None


class BaseAgent(ABC):
    """
    Base interface for sample agents.

    Agents prepare action proposals. They do not execute controlled
    tools directly; proposals must go through the governance workflow.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        agent_category: str,
    ) -> None:
        if not agent_id.strip():
            raise ValueError("agent_id cannot be empty")

        if not agent_name.strip():
            raise ValueError("agent_name cannot be empty")

        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_category = agent_category

    @abstractmethod
    def propose_action(
        self,
        scenario: dict[str, Any],
    ) -> dict[str, Any]:
        """Build an action proposal from scenario data."""
        raise NotImplementedError

    def submit_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """
        Placeholder for integration with Student 1's submit_action service.

        This method deliberately does not execute tools or pretend that
        a proposal has been submitted to the governance backend.
        """
        if not isinstance(proposal, dict):
            raise TypeError("proposal must be a dictionary")

        required_fields = {
            "agent_id",
            "tool_name",
            "action_type",
            "action_payload",
            "idempotency_key",
        }
        missing = required_fields.difference(proposal)

        if missing:
            raise ValueError(
                f"Proposal is missing required fields: {sorted(missing)}"
            )

        return {
            "status": "READY_FOR_GOVERNANCE",
            "proposal": proposal.copy(),
        }

    def handle_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Normalise a governance result for later evaluation."""
        if not isinstance(result, dict):
            raise TypeError("result must be a dictionary")

        return {
            "agent_id": self.agent_id,
            "agent_category": self.agent_category,
            "result": result.copy(),
        }

    def list_scenarios(self) -> list[str]:
        """Return scenario identifiers supported by this agent."""
        return []

    def discover_tools(self) -> list[str]:
        """Return tool names this agent may propose actions for."""
        return []
