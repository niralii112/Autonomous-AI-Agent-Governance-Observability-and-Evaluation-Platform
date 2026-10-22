
from datetime import datetime, timezone
from types import SimpleNamespace

from app.ml.features import extract_features


def make_request(
    action_type="FINANCE_PROPOSE_PAYMENT",
    tool_sensitivity="WRITE",
    amount=1000,
    currency="USD",
    record_count=0,
    record_set="",
    environment="STAGING",
    submitted_at=None,
    blocked=0,
    failed=0,
    trust_tier=2,
):
    if submitted_at is None:
        submitted_at = datetime(
            2026, 10, 18, 12, 0, tzinfo=timezone.utc
        )

    return SimpleNamespace(
        action_type=action_type,
        agent_category="FINANCE",
        tool_sensitivity=tool_sensitivity,
        action_payload={
            "amount": amount,
            "currency": currency,
            "record_count": record_count,
            "record_set": record_set,
            "environment": environment,
        },
        context={
            "submitted_at": submitted_at,
            "recent_blocked_count_24h": blocked,
            "recent_failed_count_24h": failed,
            "agent_trust_tier": trust_tier,
        },
    )


def test_payment_features_and_currency_conversion():
    request = make_request(
        amount=1000,
        currency="INR",
    )

    features = extract_features(request)

    assert features["tool_sensitivity"] == "WRITE"
    assert features["agent_category"] == "FINANCE"
    assert features["action_type"] == "FINANCE_PROPOSE_PAYMENT"
    assert features["amount_usd"] == 12.0
    assert features["record_count"] == 0
    assert features["involves_pii"] is False
    assert features["target_environment"] == "STAGING"
    assert features["is_outside_business_hours"] is False
    assert features["recent_blocked_count_24h"] == 0
    assert features["recent_failed_count_24h"] == 0
    assert features["agent_trust_tier"] == 2


def test_sensitive_records_and_pii_detection():
    request = make_request(
        action_type="FINANCE_ACCESS_SENSITIVE_RECORDS",
        tool_sensitivity="SENSITIVE_READ",
        record_count=250,
        record_set="payroll",
    )

    features = extract_features(request)

    assert features["amount_usd"] == 0.0
    assert features["record_count"] == 250
    assert features["involves_pii"] is True


def test_support_customer_info_is_pii():
    request = make_request(
        action_type="SUPPORT_ACCESS_CUSTOMER_INFO",
        tool_sensitivity="SENSITIVE_READ",
    )

    features = extract_features(request)

    assert features["record_count"] == 1
    assert features["involves_pii"] is True


def test_outside_business_hours_and_context_features():
    request = make_request(
        submitted_at=datetime(
            2026, 10, 18, 22, 0, tzinfo=timezone.utc
        ),
        blocked=3,
        failed=2,
        trust_tier=1,
    )

    features = extract_features(request)

    assert features["is_outside_business_hours"] is True
    assert features["recent_blocked_count_24h"] == 3
    assert features["recent_failed_count_24h"] == 2
    assert features["agent_trust_tier"] == 1


def test_unknown_currency_is_treated_as_usd():
    features = extract_features(make_request(amount=99999, currency="GBP"))
    assert features["amount_usd"] == 99999

def test_business_hours_boundaries():
    # Business hours are 08:00 inclusive to 20:00 exclusive.
    cases = [
        (7, True),
        (8, False),
        (19, False),
        (20, True),
        (23, True),
    ]

    for hour, expected in cases:
        request = make_request(
            submitted_at=datetime(
                2026, 10, 18, hour, 0, tzinfo=timezone.utc
            )
        )

        features = extract_features(request)

        assert features["is_outside_business_hours"] is expected


def test_supported_currency_conversions():
    cases = [
        ("USD", 100, 100.0),
        ("EUR", 100, 110.0),
        ("INR", 100, 1.2),
    ]

    for currency, amount, expected_usd in cases:
        request = make_request(
            amount=amount,
            currency=currency,
        )

        features = extract_features(request)

        assert features["amount_usd"] == expected_usd


def test_iso_timestamp_is_accepted():
    request = make_request(
        submitted_at="2026-10-18T22:00:00Z"
    )

    features = extract_features(request)

    assert features["is_outside_business_hours"] is True


def test_naive_timestamp_is_treated_as_utc():
    request = make_request(
        submitted_at=datetime(2026, 10, 18, 7, 0)
    )

    features = extract_features(request)

    assert features["is_outside_business_hours"] is True