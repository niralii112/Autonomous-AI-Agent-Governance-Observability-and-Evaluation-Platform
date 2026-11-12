"""The Finance agent: reports, summaries, payments and sensitive records."""

from app.agents.base import BaseAgent
from app.core.enums import AgentCategory


class FinanceAgent(BaseAgent):
    agent_category = AgentCategory.FINANCE
