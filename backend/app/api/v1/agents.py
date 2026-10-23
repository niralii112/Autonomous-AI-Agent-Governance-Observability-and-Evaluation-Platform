from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.agents.finance_agent import FinanceAgent
from app.agents.support_agent import SupportAgent

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)

finance_agent = FinanceAgent()
support_agent = SupportAgent()


def get_agent(agent_id: str):
    normalized = agent_id.lower()

    if normalized.startswith("finance"):
        return finance_agent

    if normalized.startswith("support"):
        return support_agent

    raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/{agent_id}/scenarios")
async def list_scenarios(agent_id: str) -> dict[str, Any]:
    agent = get_agent(agent_id)
    return {
        "agent_id": agent_id,
        "scenarios": agent.list_scenarios(),
    }


@router.post("/{agent_id}/proposals")
async def create_proposal(
    agent_id: str,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    agent = get_agent(agent_id)

    try:
        proposal = agent.propose_action(scenario)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "READY_FOR_GOVERNANCE",
        "proposal": proposal,
    }