
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.agents.base import BaseAgent


class FinanceAgent(BaseAgent):
    """Finance agent that prepares proposals for governance review."""

    def __init__(
        self,
        agent_id: str = "finance-agent-001",
        agent_name: str = "Finance Agent",
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            agent_name=agent_name,
            agent_category="FINANCE",
        )

    def propose_action(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a finance scenario into a proposal.

        This method only prepares a proposal. It does not execute a
        payment, refund, or any other controlled operation.
        """
        if not isinstance(scenario, dict):
            raise TypeError("scenario must be a dictionary")

        scenario_key = str(scenario.get("scenario_key", "")).strip()
        action_type = str(scenario.get("action_type", "")).strip()
        tool_name = str(scenario.get("tool_name", "")).strip()
        action_payload = scenario.get("action_payload", {})

        if not scenario_key:
            raise ValueError("scenario_key is required")
        if not action_type:
            raise ValueError("action_type is required")
        if not tool_name:
            raise ValueError("tool_name is required")
        if not isinstance(action_payload, dict):
            raise TypeError("action_payload must be a dictionary")

        return {
            "agent_id": self.agent_id,
            "agent_category": self.agent_category,
            "scenario_key": scenario_key,
            "tool_name": tool_name,
            "action_type": action_type,
            "action_payload": action_payload.copy(),
            "idempotency_key": str(uuid4()),
        }

    def list_scenarios(self) -> list[str]:
        return [
            "FINANCE_PROPOSE_PAYMENT",
            "FINANCE_ACCESS_SENSITIVE_RECORDS",
        ]

    def discover_tools(self) -> list[str]:
        """Return candidate tool names, not executable tool handles."""
        return [
            "payment_proposal",
            "finance_records_reader",
        ]
