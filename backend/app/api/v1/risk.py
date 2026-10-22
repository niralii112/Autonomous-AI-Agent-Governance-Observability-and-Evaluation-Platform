
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from app.services.risk_service import assess_risk

router = APIRouter(
    prefix="/risk-assessments",
    tags=["Risk Assessment"],
)


@router.post(
    "/preview",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview an action's risk assessment",
)
async def preview_risk(
    request: RiskAssessmentRequest,
) -> RiskAssessmentResponse:
    """Assess risk without submitting or executing an action.

    This endpoint is for independent Student 2 testing.
    It does not persist a governance decision or execute a tool.
    """
    try:
        result = await assess_risk(request)
        return RiskAssessmentResponse.model_validate(result)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Risk assessment failed.",
        ) from exc
