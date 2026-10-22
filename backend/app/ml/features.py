
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dictionary or an object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _enum_text(value: Any) -> str:
    """Convert an enum or string to its string value."""
    return str(getattr(value, "value", value))


def _utc_datetime(value: Any) -> datetime:
    """Convert a datetime or ISO timestamp to UTC."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if not isinstance(value, datetime):
        raise ValueError("submitted_at must be a datetime or ISO-8601 string")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def extract_features(request: Any) -> dict[str, float | int | str | bool]:
    """
    Extract the 11 risk features defined for the project.

    `Any` temporarily allows isolated development before Student 1's
    shared RiskAssessmentRequest schema is available. Do not recreate
    that shared schema in this module.
    """
    action_type = _enum_text(_get(request, "action_type", ""))
    agent_category = _enum_text(_get(request, "agent_category", ""))
    tool_sensitivity = _enum_text(_get(request, "tool_sensitivity", ""))

    payload = _get(request, "action_payload", {}) or {}
    context = _get(request, "context", {}) or {}

    # Convert supported currencies to USD for payment/refund actions.
    amount_usd = 0.0
    if action_type in {
        "FINANCE_PROPOSE_PAYMENT",
        "SUPPORT_PROPOSE_REFUND",
    }:
        amount = float(_get(payload, "amount", 0) or 0)
        currency = str(_get(payload, "currency", "USD") or "USD").upper()

        currency_rates = {
            "USD": 1.0,
            "EUR": 1.1,
            "INR": 0.012,
        }
        amount_usd = amount * currency_rates.get(currency, 1.0)

    # Record count depends on the action type.
    if action_type == "FINANCE_ACCESS_SENSITIVE_RECORDS":
        record_count = int(_get(payload, "record_count", 0) or 0)
    elif action_type == "SUPPORT_ACCESS_CUSTOMER_INFO":
        record_count = 1
    else:
        record_count = 0

    record_set = str(_get(payload, "record_set", "") or "").lower()

    involves_pii = (
        action_type == "SUPPORT_ACCESS_CUSTOMER_INFO"
        or (
            action_type == "FINANCE_ACCESS_SENSITIVE_RECORDS"
            and record_set in {"bank_accounts", "payroll", "tax"}
        )
    )

    target_environment = str(
        _get(payload, "environment", "NONE") or "NONE"
    ).upper()

    submitted_at = _utc_datetime(_get(context, "submitted_at"))
    is_outside_business_hours = (
        submitted_at.hour < 8 or submitted_at.hour >= 20
    )

    recent_blocked_count = int(
        _get(context, "recent_blocked_count_24h", 0) or 0
    )
    recent_failed_count = int(
        _get(context, "recent_failed_count_24h", 0) or 0
    )
    agent_trust_tier = int(_get(context, "agent_trust_tier", 2))

    return {
        "tool_sensitivity": tool_sensitivity,
        "agent_category": agent_category,
        "action_type": action_type,
        "amount_usd": round(amount_usd, 4),
        "record_count": record_count,
        "involves_pii": involves_pii,
        "target_environment": target_environment,
        "is_outside_business_hours": is_outside_business_hours,
        "recent_blocked_count_24h": recent_blocked_count,
        "recent_failed_count_24h": recent_failed_count,
        "agent_trust_tier": agent_trust_tier,
    }
