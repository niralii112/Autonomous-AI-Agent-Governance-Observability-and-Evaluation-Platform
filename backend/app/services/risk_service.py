
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.ml.features import extract_features
from app.ml.heuristic import heuristic_risk_score

logger = logging.getLogger(__name__)

HEURISTIC_MODEL_VERSION = "heuristic-v1"


def _risk_level(
    score: float,
    medium: float = 0.30,
    high: float = 0.60,
    critical: float = 0.85,
) -> str:
    """Convert a valid score to a risk-level name."""
    if not (0 < medium < high < critical <= 1):
        raise ValueError(
            "Thresholds must satisfy 0 < medium < high < critical <= 1"
        )

    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("Risk score must be finite and between 0 and 1")

    if score >= critical:
        return "CRITICAL"
    if score >= high:
        return "HIGH"
    if score >= medium:
        return "MEDIUM"
    return "LOW"


def _model_prediction(
    features: dict[str, float | int | str | bool],
) -> tuple[float, float] | None:
    """
    Return (risk score, confidence) only when the model is accepted.

    Model loading, acceptance, and prediction errors fail closed by
    returning None. Scenario-level acceptance is currently pending.
    """
    try:
        from app.ml.model_acceptance import validate_model_acceptance

        acceptance = validate_model_acceptance()
        if not acceptance.get("accepted_for_activation", False):
            return None

        from app.ml.model_loader import (
            EXPECTED_FEATURE_COLUMNS,
            get_active_model,
        )

        import pandas as pd

        model = get_active_model()
        if model is None:
            return None

        row = {
            column: features[column]
            for column in EXPECTED_FEATURE_COLUMNS
        }
        frame = pd.DataFrame([row], columns=EXPECTED_FEATURE_COLUMNS)

        probabilities = model.predict_proba(frame)
        classes = list(model.classes_)

        if 1 not in classes:
            return None

        score = float(probabilities[0][classes.index(1)])
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            return None

        confidence = max(score, 1.0 - score)
        return round(score, 4), round(confidence, 4)

    except Exception:
        logger.exception(
            "RISK_FALLBACK: ML prediction failed; using heuristic"
        )
        return None


async def assess_risk(request: Any) -> dict[str, Any]:
    """
    Assess risk with an accepted ML model or deterministic heuristic.

    The Any/dict interface is temporary until Student 1 supplies the
    shared request and response schemas and canonical enums.
    """
    started = time.perf_counter()

    if request is None or isinstance(
        request, (str, bytes, int, float, bool)
    ):
        raise TypeError(
            "request must be a risk assessment request object"
        )

    # Feature extraction and heuristic errors are input or programming
    # errors, not model errors, so they should not be silently swallowed.
    features = extract_features(request)
    heuristic_score, reason_codes = heuristic_risk_score(features)

    # Defence in depth: even if the model helper unexpectedly raises,
    # risk assessment must still return the deterministic heuristic result.
    try:
        model_result = _model_prediction(features)
    except Exception:
        logger.exception(
            "RISK_FALLBACK: unexpected model error; using heuristic"
        )
        model_result = None

    if model_result is None:
        score = heuristic_score
        confidence = 0.5000
        risk_source = "HEURISTIC_FALLBACK"
        model_version = HEURISTIC_MODEL_VERSION
    else:
        try:
            candidate_score, candidate_confidence = model_result

            if (
                not math.isfinite(candidate_score)
                or not 0.0 <= candidate_score <= 1.0
                or not math.isfinite(candidate_confidence)
                or not 0.0 <= candidate_confidence <= 1.0
            ):
                raise ValueError("Model returned invalid risk values")

            from app.ml.model_loader import MODEL_VERSION

            score = round(candidate_score, 4)
            confidence = round(candidate_confidence, 4)
            risk_source = "ML_MODEL"
            model_version = MODEL_VERSION

        except Exception:
            logger.exception(
                "RISK_FALLBACK: invalid model result; using heuristic"
            )
            score = heuristic_score
            confidence = 0.5000
            risk_source = "HEURISTIC_FALLBACK"
            model_version = HEURISTIC_MODEL_VERSION

    risk_level = _risk_level(score)
    latency_ms = round(
        (time.perf_counter() - started) * 1000, 3
    )

    action_id = (
        request.get("action_id")
        if isinstance(request, dict)
        else getattr(request, "action_id", None)
    )

    response = {
        "risk_assessment_id": str(uuid4()),
        "action_id": str(action_id) if action_id is not None else None,
        "risk_score": round(score, 4),
        "risk_level": risk_level,
        "confidence_score": round(confidence, 4),
        "risk_source": risk_source,
        "model_version": model_version,
        "reason_codes": reason_codes,
        "features": features,
        "latency_ms": latency_ms,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if risk_source == "HEURISTIC_FALLBACK":
        logger.warning(
            "RISK_FALLBACK: deterministic heuristic used "
            "(model_version=%s)",
            model_version,
        )

    return response
