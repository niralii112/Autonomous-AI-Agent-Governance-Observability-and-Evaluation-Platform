
import pandas as pd
import pytest

from app.ml.model_loader import get_active_model


def test_model_predicts_risk_for_valid_features():
    model = get_active_model()

    if model is None:
        pytest.fail("Expected the trained model artifact to load")

    features = pd.DataFrame([{
        "tool_sensitivity": "PRIVILEGED",
        "agent_category": "FINANCE",
        "action_type": "FINANCE_PROPOSE_PAYMENT",
        "amount_usd": 50000.0,
        "record_count": 0,
        "involves_pii": False,
        "target_environment": "PRODUCTION",
        "is_outside_business_hours": True,
        "recent_blocked_count_24h": 3,
        "recent_failed_count_24h": 2,
        "agent_trust_tier": 1,
    }])

    probabilities = model.predict_proba(features)

    assert probabilities.shape == (1, 2)
    assert list(model.classes_) == [0, 1]

    positive_class_index = list(model.classes_).index(1)
    risk_score = float(probabilities[0, positive_class_index])

    assert 0.0 <= risk_score <= 1.0


def test_model_handles_unseen_categorical_values():
    model = get_active_model()

    if model is None:
        pytest.fail("Expected the trained model artifact to load")

    features = pd.DataFrame([{
        "tool_sensitivity": "UNSEEN_SENSITIVITY",
        "agent_category": "UNSEEN_AGENT",
        "action_type": "UNSEEN_ACTION",
        "amount_usd": 0.0,
        "record_count": 0,
        "involves_pii": False,
        "target_environment": "UNSEEN_ENVIRONMENT",
        "is_outside_business_hours": False,
        "recent_blocked_count_24h": 0,
        "recent_failed_count_24h": 0,
        "agent_trust_tier": 2,
    }])

    probabilities = model.predict_proba(features)

    assert probabilities.shape == (1, 2)
    assert all(0.0 <= float(p) <= 1.0 for p in probabilities[0])
