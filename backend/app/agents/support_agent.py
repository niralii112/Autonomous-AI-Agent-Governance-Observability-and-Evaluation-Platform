"""The Customer Support agent: tickets, responses, refunds and customer info."""

from app.agents.base import BaseAgent
from app.core.enums import AgentCategory


class CustomerSupportAgent(BaseAgent):
    agent_category = AgentCategory.CUSTOMER_SUPPORT
