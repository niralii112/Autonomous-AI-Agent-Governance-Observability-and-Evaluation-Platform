
from datetime import datetime, timezone

import pytest

from app.services import risk_service


def _request(**overrides):
    request = {
        "action_id": "action-test-001",
        "action_type": "FINANCE_PROPOSE_PAYMENT",
        "agent_category": "FINANCE",
        "tool_sensitivity": "WRITE",
        "action_payload": {
            "amount": 1500,
            "currency": "USD",
            "environment": "PRODUCTION",
        },
        "context": {
            "submitted_at": datetime(
                2026, 1, 15, 12, 0, tzinfo=timezone.utc
            ),
            "recent_blocked_count_24h": 0,
            "recent_failed_count_24h": 0,
            "agent_trust_tier": 2,
        },
    }
    request.update(overrides)
    return request


@pytest.mark.asyncio
async def test_assess_risk_returns_expected_response_fields(monkeypatch):
    monkeypatch.setattr(
        risk_service, "_model_prediction", lambda features: None
    )

    result = await risk_service.assess_risk(_request())

    expected = {
        "risk_assessment_id",
        "action_id",
        "risk_score",
        "risk_level",
        "confidence_score",
        "risk_source",
        "model_version",
        "reason_codes",
        "features",
        "latency_ms",
        "created_at",
    }
    assert expected.issubset(result.keys())
    assert result["action_id"] == "action-test-001"
    assert result["risk_source"] == "HEURISTIC_FALLBACK"
    assert result["model_version"] == "heuristic-v1"
    assert result["confidence_score"] == 0.5
    assert 0 <= result["risk_score"] <= 1


@pytest.mark.asyncio
async def test_assess_risk_uses_heuristic_when_model_is_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        risk_service, "_model_prediction", lambda features: None
    )

    result = await risk_service.assess_risk(_request())
    expected_score, expected_reasons = risk_service.heuristic_risk_score(
        result["features"]
    )

    assert result["risk_score"] == expected_score
    assert result["reason_codes"] == expected_reasons
    assert result["risk_source"] == "HEURISTIC_FALLBACK"


@pytest.mark.asyncio
async def test_assess_risk_uses_accepted_model_prediction(monkeypatch):
    monkeypatch.setattr(
        risk_service,
        "_model_prediction",
        lambda features: (0.91, 0.91),
    )

    result = await risk_service.assess_risk(_request())

    assert result["risk_score"] == 0.91
    assert result["risk_level"] == "CRITICAL"
    assert result["confidence_score"] == 0.91
    assert result["risk_source"] == "ML_MODEL"


@pytest.mark.asyncio
async def test_unexpected_model_exception_falls_back_to_heuristic(
    monkeypatch,
):
    def raise_model_error(features):
        raise RuntimeError("simulated model prediction failure")

    monkeypatch.setattr(
        risk_service, "_model_prediction", raise_model_error
    )

    # assess_risk should catch model-related errors and return a heuristic
    # result rather than allowing an ML exception to escape.
    result = await risk_service.assess_risk(_request())

    assert result["risk_source"] == "HEURISTIC_FALLBACK"
    assert result["model_version"] == "heuristic-v1"


@pytest.mark.asyncio
async def test_invalid_request_type_raises_type_error():
    with pytest.raises(TypeError):
        await risk_service.assess_risk(None)


def test_risk_level_threshold_boundaries():
    assert risk_service._risk_level(0.2999) == "LOW"
    assert risk_service._risk_level(0.30) == "MEDIUM"
    assert risk_service._risk_level(0.60) == "HIGH"
    assert risk_service._risk_level(0.85) == "CRITICAL"


def test_risk_level_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        risk_service._risk_level(
            0.5, medium=0.6, high=0.5, critical=0.9
        )


def test_risk_level_rejects_non_finite_scores():
    with pytest.raises(ValueError):
        risk_service._risk_level(float("nan"))

@pytest.mark.asyncio
async def test_model_acceptance_rejection_uses_heuristic(monkeypatch):
    monkeypatch.setattr(
        risk_service,
        "_model_prediction",
        lambda features: None,
    )

    result = await risk_service.assess_risk(_request())

    assert result["risk_source"] == "HEURISTIC_FALLBACK"
    assert result["model_version"] == "heuristic-v1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_result",
    [
        (float("nan"), 0.9),
        (float("inf"), 0.9),
        (-0.1, 0.9),
        (1.1, 0.9),
        (0.8, float("nan")),
        (0.8, 1.1),
    ],
)
async def test_invalid_model_result_uses_heuristic(
    monkeypatch, model_result
):
    monkeypatch.setattr(
        risk_service,
        "_model_prediction",
        lambda features: model_result,
    )

    result = await risk_service.assess_risk(_request())

    assert result["risk_source"] == "HEURISTIC_FALLBACK"
    assert result["model_version"] == "heuristic-v1"
    assert result["confidence_score"] == 0.5