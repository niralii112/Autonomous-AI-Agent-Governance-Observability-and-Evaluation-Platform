"""Picks the agent class that belongs to an agent category."""

import uuid

from app.agents.base import BaseAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.support_agent import CustomerSupportAgent
from app.core.enums import AgentCategory, ErrorCode
from app.core.exceptions import AppError

AGENT_CLASSES: dict[AgentCategory, type[BaseAgent]] = {
    AgentCategory.FINANCE: FinanceAgent,
    AgentCategory.CUSTOMER_SUPPORT: CustomerSupportAgent,
}


def create_agent(
    agent_category: AgentCategory,
    agent_id: uuid.UUID,
    agent_name: str,
) -> BaseAgent:
    """Build the agent for a category. Unsupported categories are rejected."""
    agent_class = AGENT_CLASSES.get(agent_category)

    if agent_class is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "No agent is available for this category.",
            {"agent_category": agent_category.value},
        )

    return agent_class(agent_id, agent_name)
