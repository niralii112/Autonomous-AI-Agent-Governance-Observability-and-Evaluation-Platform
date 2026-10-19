
from __future__ import annotations

from typing import Any

SENSITIVITY_WEIGHTS = {
    "READ_ONLY": 0.05,
    "SENSITIVE_READ": 0.35,
    "WRITE": 0.40,
    "PRIVILEGED": 0.65,
}


def heuristic_risk_score(
    features: dict[str, float | int | str | bool],
) -> tuple[float, list[str]]:
    """Calculate a deterministic risk score and its reason codes."""

    score = 0.0
    reason_codes: list[str] = []

    sensitivity = str(features.get("tool_sensitivity", ""))
    sensitivity_weight = SENSITIVITY_WEIGHTS.get(sensitivity, 0.0)
    score += sensitivity_weight

    if sensitivity in SENSITIVITY_WEIGHTS:
        reason_codes.append(f"SENSITIVITY_{sensitivity}")

    amount_usd = float(features.get("amount_usd", 0) or 0)

    # Apply only the first matching amount threshold.
    for threshold, weight in (
        (50000, 0.35),
        (10000, 0.25),
        (1000, 0.15),
        (100, 0.05),
    ):
        if amount_usd >= threshold:
            score += weight
            reason_codes.append(f"AMOUNT_GTE_{threshold}")
            break

    record_count = int(features.get("record_count", 0) or 0)

    # Apply only the first matching record-count threshold.
    for threshold, weight in ((1000, 0.15), (100, 0.08)):
        if record_count >= threshold:
            score += weight
            reason_codes.append(f"RECORDS_GTE_{threshold}")
            break

    if bool(features.get("involves_pii", False)):
        score += 0.10
        reason_codes.append("INVOLVES_PII")

    environment = str(
        features.get("target_environment", "NONE")
    ).upper()

    if environment == "PRODUCTION":
        score += 0.15
        reason_codes.append("TARGET_PRODUCTION")

    if bool(features.get("is_outside_business_hours", False)):
        score += 0.05
        reason_codes.append("OUTSIDE_BUSINESS_HOURS")

    blocked_count = int(
        features.get("recent_blocked_count_24h", 0) or 0
    )
    if blocked_count > 0:
        score += 0.05 * min(blocked_count, 4)
        reason_codes.append("RECENT_BLOCKED_ACTIONS")

    failed_count = int(
        features.get("recent_failed_count_24h", 0) or 0
    )
    if failed_count > 0:
        score += 0.02 * min(failed_count, 5)
        reason_codes.append("RECENT_FAILED_ACTIONS")

    trust_tier = int(features.get("agent_trust_tier", 2))

    if trust_tier == 1:
        score += 0.10
        reason_codes.append("TRUST_TIER_1")
    elif trust_tier == 3:
        score -= 0.05
        reason_codes.append("TRUST_TIER_3")

    score = round(max(0.0, min(score, 1.0)), 4)

    return score, reason_codes


def score_to_level(
    risk_score: float,
    medium: float = 0.30,
    high: float = 0.60,
    critical: float = 0.85,
) -> Any:
    """Map a numeric risk score to the project's RiskLevel enum."""

    if not (0 < medium < high < critical <= 1):
        raise ValueError(
            "Thresholds must satisfy 0 < medium < high < critical <= 1"
        )

    if not 0.0 <= risk_score <= 1.0:
        raise ValueError("risk_score must be between 0 and 1")

    # Import the shared enum rather than defining a duplicate.
    from app.core.enums import RiskLevel

    if risk_score >= critical:
        return RiskLevel.CRITICAL
    if risk_score >= high:
        return RiskLevel.HIGH
    if risk_score >= medium:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
