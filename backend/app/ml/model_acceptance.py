
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import joblib
import pandas as pd

from app.agents.scenarios import SCENARIO_SPECS
from app.core.enums import RiskLevel
from app.ml.features import extract_features
from app.ml.model_loader import (
    EXPECTED_FEATURE_COLUMNS,
    MODEL_VERSION,
    _artifact_directory,
    _sha256_file,
)

MINIMUM_RECALL = 0.85
MINIMUM_ROC_AUC = 0.90


def _score_to_level(score: float) -> RiskLevel:
    """Use the same risk thresholds as the risk service."""
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("Invalid model risk probability")

    if score >= 0.85:
        return RiskLevel.CRITICAL
    if score >= 0.60:
        return RiskLevel.HIGH
    if score >= 0.30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _check_scenarios(model: Any) -> dict[str, Any]:
    """Run the trained model against all fixed Finance and Support scenarios."""
    if not SCENARIO_SPECS:
        raise ValueError("No scenario specifications are available")

    rows = []

    for spec in SCENARIO_SPECS:
        request = SimpleNamespace(
            action_type=spec.scenario.action_type,
            agent_category=spec.agent_category,
            tool_sensitivity=spec.tool_sensitivity,
            action_payload=spec.scenario.action_payload,
            context={
                "submitted_at": datetime(
                    2026, 1, 15, 12, 0, tzinfo=timezone.utc
                ),
                "recent_blocked_count_24h": 0,
                "recent_failed_count_24h": 0,
            },
            agent_trust_tier=2,
        )

        rows.append(extract_features(request))

    frame = pd.DataFrame(
        rows,
        columns=EXPECTED_FEATURE_COLUMNS,
    )

    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError("Model does not contain positive class 1")

    probabilities = model.predict_proba(frame)

    if len(probabilities) != len(SCENARIO_SPECS):
        raise ValueError("Model returned an unexpected number of predictions")

    results = []
    passed = True
    positive_index = classes.index(1)

    for spec, probability_row in zip(SCENARIO_SPECS, probabilities):
        score = float(probability_row[positive_index])
        predicted_level = _score_to_level(score)
        allowed_levels = spec.acceptance_levels

        scenario_passed = predicted_level in allowed_levels
        passed = passed and scenario_passed

        results.append({
            "scenario_key": spec.scenario.scenario_key,
            "risk_score": round(score, 4),
            "predicted_risk_level": predicted_level.value,
            "accepted_risk_levels": [
                level.value for level in allowed_levels
            ],
            "passed": scenario_passed,
        })

    return {
        "scenario_checks_completed": True,
        "scenario_checks_passed": passed,
        "scenario_count": len(results),
        "scenario_results": results,
    }


def validate_model_acceptance(
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate metrics, artifact integrity and all fixed scenarios."""

    result: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "metrics_passed": False,
        "artifact_integrity_passed": False,
        "scenario_checks_completed": False,
        "scenario_checks_passed": False,
        "accepted_for_activation": False,
        "reasons": [],
    }

    try:
        directory = (
            Path(artifact_dir).expanduser().resolve()
            if artifact_dir is not None
            else _artifact_directory()
        )

        metadata_path = directory / f"{MODEL_VERSION}.metadata.json"
        metrics_path = directory / f"{MODEL_VERSION}.metrics.json"
        model_path = directory / f"{MODEL_VERSION}.joblib"

        if not directory.is_dir():
            result["reasons"].append("Artifact directory is missing")
            return result

        if not metadata_path.is_file():
            result["reasons"].append("Model metadata file is missing")
            return result

        if not metrics_path.is_file():
            result["reasons"].append("Model metrics file is missing")
            return result

        if not model_path.is_file():
            result["reasons"].append("Model artifact file is missing")
            return result

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

        if not isinstance(metadata, dict):
            result["reasons"].append("Model metadata must be a JSON object")
            return result

        if not isinstance(metrics, dict):
            result["reasons"].append("Model metrics must be a JSON object")
            return result

        if metadata.get("model_version") != MODEL_VERSION:
            result["reasons"].append("Model version does not match")
            return result

        if metadata.get("feature_columns") != EXPECTED_FEATURE_COLUMNS:
            result["reasons"].append("Feature columns do not match")
            return result

        expected_hash = metadata.get("sha256")
        if not isinstance(expected_hash, str) or not expected_hash.strip():
            result["reasons"].append("Metadata SHA-256 checksum is missing")
            return result

        actual_hash = _sha256_file(model_path)
        if actual_hash.lower() != expected_hash.lower():
            result["reasons"].append("Model checksum verification failed")
            return result

        result["artifact_integrity_passed"] = True

        recall = metrics.get("recall")
        roc_auc = metrics.get("roc_auc")

        for name, value in (("Recall", recall), ("ROC-AUC", roc_auc)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0.0 <= value <= 1.0
            ):
                result["reasons"].append(
                    f"{name} metric is missing or invalid"
                )
                return result

        result["metrics"] = {
            "recall": float(recall),
            "roc_auc": float(roc_auc),
            "minimum_recall": MINIMUM_RECALL,
            "minimum_roc_auc": MINIMUM_ROC_AUC,
        }

        # Check the individual metric thresholds.
        result["metrics_passed"] = True

        if recall < MINIMUM_RECALL:
            result["metrics_passed"] = False
            result["reasons"].append(
                f"Recall is below the minimum threshold "
                f"({recall:.4f} < {MINIMUM_RECALL:.2f})"
            )

        if roc_auc < MINIMUM_ROC_AUC:
            result["metrics_passed"] = False
            result["reasons"].append(
                f"ROC-AUC is below the minimum threshold "
                f"({roc_auc:.4f} < {MINIMUM_ROC_AUC:.2f})"
            )

        if not result["metrics_passed"]:
            return result

        # The checksum has been verified before deserializing this local artifact.
        model = joblib.load(model_path)

        if not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
            raise ValueError("Model does not support probability predictions")

        scenario_result = _check_scenarios(model)
        result.update(scenario_result)

        if not result["scenario_checks_passed"]:
            failed = [
                item["scenario_key"]
                for item in result["scenario_results"]
                if not item["passed"]
            ]
            result["reasons"].append(
                "Scenario acceptance failed for: " + ", ".join(failed)
            )

        result["accepted_for_activation"] = (
            result["artifact_integrity_passed"]
            and result["metrics_passed"]
            and result["scenario_checks_completed"]
            and result["scenario_checks_passed"]
        )

        if result["accepted_for_activation"]:
            result["reasons"].append(
                "Model passed metrics, integrity and scenario acceptance"
            )

        return result

    except Exception as exc:
        result["accepted_for_activation"] = False
        result["scenario_checks_completed"] = False
        result["reasons"].append(
            f"Acceptance validation failed safely: {type(exc).__name__}: {exc}"
        )
        return result
