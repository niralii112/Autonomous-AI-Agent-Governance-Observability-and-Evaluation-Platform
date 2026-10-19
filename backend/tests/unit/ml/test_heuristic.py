
from app.ml.heuristic import heuristic_risk_score


def base_features():
    return {
        "tool_sensitivity": "READ_ONLY",
        "agent_category": "IT",
        "action_type": "IT_READ_LOGS",
        "amount_usd": 0.0,
        "record_count": 0,
        "involves_pii": False,
        "target_environment": "NONE",
        "is_outside_business_hours": False,
        "recent_blocked_count_24h": 0,
        "recent_failed_count_24h": 0,
        "agent_trust_tier": 2,
    }


def test_write_sensitivity_and_amount_threshold():
    features = base_features()
    features["tool_sensitivity"] = "WRITE"
    features["amount_usd"] = 1000

    score, reasons = heuristic_risk_score(features)

    assert score == 0.55
    assert reasons == ["SENSITIVITY_WRITE", "AMOUNT_GTE_1000"]


def test_production_pii_and_trust_tier_one():
    features = base_features()
    features.update({
        "tool_sensitivity": "SENSITIVE_READ",
        "involves_pii": True,
        "target_environment": "PRODUCTION",
        "agent_trust_tier": 1,
    })

    score, reasons = heuristic_risk_score(features)

    assert score == 0.70
    assert reasons == [
        "SENSITIVITY_SENSITIVE_READ",
        "INVOLVES_PII",
        "TARGET_PRODUCTION",
        "TRUST_TIER_1",
    ]


def test_risk_score_is_capped_at_one():
    features = base_features()
    features.update({
        "tool_sensitivity": "PRIVILEGED",
        "amount_usd": 50000,
        "record_count": 1000,
        "involves_pii": True,
        "target_environment": "PRODUCTION",
        "is_outside_business_hours": True,
        "recent_blocked_count_24h": 10,
        "recent_failed_count_24h": 10,
        "agent_trust_tier": 1,
    })

    score, _ = heuristic_risk_score(features)

    assert score == 1.0


def test_trust_tier_three_reduces_score():
    features = base_features()
    features["tool_sensitivity"] = "WRITE"
    features["agent_trust_tier"] = 3

    score, reasons = heuristic_risk_score(features)

    assert score == 0.35
    assert reasons == ["SENSITIVITY_WRITE", "TRUST_TIER_3"]


def test_amount_threshold_uses_first_match():
    features = base_features()
    features["amount_usd"] = 50000

    score, reasons = heuristic_risk_score(features)

    assert score == 0.40
    assert reasons == ["SENSITIVITY_READ_ONLY", "AMOUNT_GTE_50000"]

def test_amount_threshold_boundaries():
    cases = [
        (99.99, 0.0),
        (100, 0.05),
        (999.99, 0.05),
        (1000, 0.15),
        (9999.99, 0.15),
        (10000, 0.25),
        (49999.99, 0.25),
        (50000, 0.35),
    ]

    for amount, expected_weight in cases:
        features = base_features()
        features["amount_usd"] = amount

        score, _ = heuristic_risk_score(features)

        assert round(score - 0.05, 4) == expected_weight, (
            f"Unexpected amount weight for amount_usd={amount}"
        )


def test_record_count_threshold_boundaries():
    cases = [
        (99, 0.0),
        (100, 0.08),
        (999, 0.08),
        (1000, 0.15),
    ]

    for record_count, expected_weight in cases:
        features = base_features()
        features["record_count"] = record_count

        score, _ = heuristic_risk_score(features)

        assert round(score - 0.05, 4) == expected_weight, (
            f"Unexpected record-count weight for record_count={record_count}"
        )