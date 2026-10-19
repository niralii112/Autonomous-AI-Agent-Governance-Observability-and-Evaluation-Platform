
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.ml.model_loader import (
    EXPECTED_FEATURE_COLUMNS,
    MODEL_VERSION,
    _artifact_directory,
    _sha256_file,
)

MINIMUM_RECALL = 0.85
MINIMUM_ROC_AUC = 0.90


def validate_model_acceptance(
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Check numeric acceptance gates and artifact integrity.

    This function does not activate the model. Scenario-level acceptance
    remains pending until the canonical scenario catalogue is available.
    """
    result: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "metrics_passed": False,
        "artifact_integrity_passed": False,
        "scenario_checks_completed": False,
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
        if (
            not isinstance(actual_hash, str)
            or actual_hash.lower() != expected_hash.lower()
        ):
            result["reasons"].append("Model checksum verification failed")
            return result

        result["artifact_integrity_passed"] = True

        recall = metrics.get("recall")
        roc_auc = metrics.get("roc_auc")

        if (
            isinstance(recall, bool)
            or not isinstance(recall, (int, float))
            or not math.isfinite(recall)
            or not 0.0 <= recall <= 1.0
        ):
            result["reasons"].append("Recall metric is missing or invalid")
            return result

        if (
            isinstance(roc_auc, bool)
            or not isinstance(roc_auc, (int, float))
            or not math.isfinite(roc_auc)
            or not 0.0 <= roc_auc <= 1.0
        ):
            result["reasons"].append("ROC-AUC metric is missing or invalid")
            return result

        result["metrics"] = {
            "recall": float(recall),
            "roc_auc": float(roc_auc),
            "minimum_recall": MINIMUM_RECALL,
            "minimum_roc_auc": MINIMUM_ROC_AUC,
        }

        recall_passed = recall >= MINIMUM_RECALL
        roc_auc_passed = roc_auc >= MINIMUM_ROC_AUC
        result["metrics_passed"] = recall_passed and roc_auc_passed

        if not recall_passed:
            result["reasons"].append(
                f"Recall is below the required {MINIMUM_RECALL:.2f}"
            )

        if not roc_auc_passed:
            result["reasons"].append(
                f"ROC-AUC is below the required {MINIMUM_ROC_AUC:.2f}"
            )

        result["reasons"].append(
            "Scenario-level acceptance is pending because the scenario catalog "
            "is not available"
        )

        return result

    except Exception as exc:
        # Fail closed: validation errors must never authorize model activation.
        result["metrics_passed"] = False
        result["accepted_for_activation"] = False
        result["reasons"].append(
            f"Acceptance validation failed safely: {type(exc).__name__}"
        )
        return result
