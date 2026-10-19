
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

MODEL_VERSION = "risk-logreg-1.0.0"
EXPECTED_FEATURE_COLUMNS = [
    "tool_sensitivity",
    "agent_category",
    "action_type",
    "amount_usd",
    "record_count",
    "involves_pii",
    "target_environment",
    "is_outside_business_hours",
    "recent_blocked_count_24h",
    "recent_failed_count_24h",
    "agent_trust_tier",
]


def _artifact_directory() -> Path:
    """Resolve the configured model artifact directory."""
    configured = os.environ.get("RISK_MODEL_ARTIFACT_DIR")

    if configured:
        directory = Path(configured).expanduser().resolve()
    else:
        # backend/app/ml/model_loader.py -> backend/artifacts
        directory = Path(__file__).resolve().parents[2] / "artifacts"

    return directory


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_model_artifact() -> Any | None:
    """
    Load the configured model only when its metadata and SHA-256 match.

    Returns None on missing files, invalid metadata, checksum mismatch,
    or deserialization errors so callers can use heuristic fallback.
    Only load model artifacts from a trusted local directory.
    """
    try:
        artifact_dir = _artifact_directory()

        model_path = (
            artifact_dir / f"{MODEL_VERSION}.joblib"
        ).resolve()
        metadata_path = (
            artifact_dir / f"{MODEL_VERSION}.metadata.json"
        ).resolve()

        # Require the files to be direct children of the configured directory.
        if model_path.parent != artifact_dir or metadata_path.parent != artifact_dir:
            logger.error("Model artifact path escaped configured directory")
            return None

        if not artifact_dir.is_dir():
            logger.warning("Model artifact directory does not exist")
            return None

        if not model_path.is_file() or not metadata_path.is_file():
            logger.warning("Model or metadata file is missing")
            return None

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        if metadata.get("model_version") != MODEL_VERSION:
            logger.error("Model version metadata does not match")
            return None

        if metadata.get("feature_columns") != EXPECTED_FEATURE_COLUMNS:
            logger.error("Model feature list does not match expected features")
            return None

        expected_sha256 = metadata.get("sha256")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            logger.error("Model metadata has no valid SHA-256 checksum")
            return None

        actual_sha256 = _sha256_file(model_path)

        if actual_sha256.lower() != expected_sha256.lower():
            logger.error("Model checksum validation failed")
            return None

        # joblib/pickle can execute code while loading. Only load trusted,
        # locally generated artifacts after verifying their checksum.
        model = joblib.load(model_path)

        if not hasattr(model, "predict_proba"):
            logger.error("Loaded model does not support predict_proba")
            return None

        if not hasattr(model, "classes_"):
            logger.error("Loaded model does not expose fitted classes")
            return None

        classes = list(model.classes_)
        if 1 not in classes:
            logger.error("Loaded model has no positive class (1)")
            return None

        logger.info("Model %s loaded and checksum verified", MODEL_VERSION)
        return model

    except Exception:
        logger.exception("Model loading failed; heuristic fallback is required")
        return None


def get_active_model() -> Any | None:
    """Return the validated model, or None to trigger heuristic fallback."""
    return load_model_artifact()
