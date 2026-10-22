from datetime import datetime, timezone

import pytest

from app.ml.features import extract_features
from app.ml.heuristic import heuristic_risk_score
from app.services.risk_service import _risk_level


def _request(
    *,
    action_type="FINANCE_GET_REPORT",
    category="FINANCE",
    sensitivity="READ_ONLY",
    payload=None,
    submitted_at="2026-01-15T12:00:00+00:00",
    blocked=0,
    failed=0,
    trust=2,
):
    return {
        "action_id": "scenario-test",
        "agent_id": "agent-test",
        "agent_category": category,
        "action_type": action_type,
        "tool_name": "scenario-test-tool",
        "tool_sensitivity": sensitivity,
        "action_payload": payload or {},
        "context": {
            "submitted_at": datetime.fromisoformat(submitted_at),
            "recent_blocked_count_24h": blocked,
            "recent_failed_count_24h": failed,
            "agent_trust_tier": trust,
        },
    }


@pytest.mark.parametrize(
    ("name", "scenario_input", "expected_min", "expected_max", "reason"),
    [
        (
            "routine_read",
            _request(),
            0.0,
            0.30,
            "SENSITIVITY_READ_ONLY",
        ),
        (
            "large_production_payment",
            _request(
                action_type="FINANCE_PROPOSE_PAYMENT",
                sensitivity="PRIVILEGED",
                payload={
                    "amount": 60000,
                    "currency": "USD",
                    "environment": "PRODUCTION",
                },
            ),
            0.80,
            1.0,
            "AMOUNT_GTE_50000",
        ),
        (
            "sensitive_finance_records",
            _request(
                action_type="FINANCE_ACCESS_SENSITIVE_RECORDS",
                sensitivity="SENSITIVE_READ",
                payload={
                    "record_count": 1200,
                    "record_set": "payroll",
                    "environment": "PRODUCTION",
                },
            ),
            0.60,
            1.0,
            "INVOLVES_PII",
        ),
        (
            "support_customer_information",
            _request(
                action_type="SUPPORT_ACCESS_CUSTOMER_INFO",
                category="CUSTOMER_SUPPORT",
                sensitivity="SENSITIVE_READ",
                payload={"environment": "PRODUCTION"},
                blocked=2,
                failed=1,
                trust=1,
            ),
            0.50,
            1.0,
            "INVOLVES_PII",
        ),
    ],
)
def test_heuristic_risk_scenarios(
    name, scenario_input, expected_min, expected_max, reason
):
    features = extract_features(scenario_input)
    score, reason_codes = heuristic_risk_score(features)

    assert expected_min <= score <= expected_max, name
    assert reason in reason_codes, name
    assert _risk_level(score) in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_unknown_currency_uses_documented_usd_fallback():
    request = _request(
        action_type="FINANCE_PROPOSE_PAYMENT",
        sensitivity="WRITE",
        payload={"amount": 1000, "currency": "XYZ"},
    )

    features = extract_features(request)

    assert features["amount_usd"] == 1000.0


def test_large_payment_scores_higher_than_routine_read():
    routine_features = extract_features(_request())
    payment_features = extract_features(
        _request(
            action_type="FINANCE_PROPOSE_PAYMENT",
            sensitivity="PRIVILEGED",
            payload={
                "amount": 60000,
                "currency": "USD",
                "environment": "PRODUCTION",
            },
        )
    )

    routine_score, _ = heuristic_risk_score(routine_features)
    payment_score, _ = heuristic_risk_score(payment_features)

    assert payment_score > routine_score