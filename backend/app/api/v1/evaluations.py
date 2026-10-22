from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.agent_evaluation import evaluate_agent_outcomes

router = APIRouter(
    prefix="/evaluations",
    tags=["Evaluation"],
)


class AgentOutcomeRequest(BaseModel):
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


@router.post(
    "/agent-outcomes",
    summary="Evaluate recorded agent outcomes",
)
async def evaluate_outcomes(
    request: AgentOutcomeRequest,
) -> dict[str, Any]:
    try:
        return evaluate_agent_outcomes(request.outcomes)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc