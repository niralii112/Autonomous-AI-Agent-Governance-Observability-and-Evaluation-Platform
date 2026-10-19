
import json

import pytest

from app.ml import model_acceptance
from app.ml.model_acceptance import validate_model_acceptance


def _write_test_artifacts(tmp_path, monkeypatch, metrics=None, metadata_overrides=None):
    """Create isolated artifacts for acceptance tests."""
    version = model_acceptance.MODEL_VERSION
    model_path = tmp_path / f"{version}.joblib"
    metadata_path = tmp_path / f"{version}.metadata.json"
    metrics_path = tmp_path / f"{version}.metrics.json"

    model_path.write_bytes(b"test model artifact")

    metadata = {
        "model_version": version,
        "feature_columns": model_acceptance.EXPECTED_FEATURE_COLUMNS,
        "sha256": "test-checksum",
    }
    if metadata_overrides:
        metadata.update(metadata_overrides)

    if metrics is None:
        metrics = {
            "recall": 0.90,
            "roc_auc": 0.95,
        }

    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    monkeypatch.setattr(
        model_acceptance,
        "_sha256_file",
        lambda path: "test-checksum",
    )

    return metadata_path, metrics_path


def test_current_model_passes_numeric_gates_but_is_not_activated():
    result = validate_model_acceptance()

    assert result["artifact_integrity_passed"] is True
    assert result["metrics_passed"] is True
    assert result["scenario_checks_completed"] is False
    assert result["accepted_for_activation"] is False
    assert result["metrics"]["recall"] >= model_acceptance.MINIMUM_RECALL
    assert result["metrics"]["roc_auc"] >= model_acceptance.MINIMUM_ROC_AUC


def test_missing_artifact_directory_fails_closed(tmp_path):
    result = validate_model_acceptance(tmp_path / "missing")

    assert result["artifact_integrity_passed"] is False
    assert result["metrics_passed"] is False
    assert result["accepted_for_activation"] is False
    assert result["reasons"]


def test_recall_below_threshold_fails_numeric_gate(tmp_path, monkeypatch):
    _write_test_artifacts(
        tmp_path,
        monkeypatch,
        metrics={
            "recall": model_acceptance.MINIMUM_RECALL - 0.01,
            "roc_auc": model_acceptance.MINIMUM_ROC_AUC + 0.05,
        },
    )

    result = validate_model_acceptance(tmp_path)

    assert result["artifact_integrity_passed"] is True
    assert result["metrics_passed"] is False
    assert result["accepted_for_activation"] is False
    assert any("Recall is below" in reason for reason in result["reasons"])


def test_roc_auc_below_threshold_fails_numeric_gate(tmp_path, monkeypatch):
    _write_test_artifacts(
        tmp_path,
        monkeypatch,
        metrics={
            "recall": model_acceptance.MINIMUM_RECALL + 0.05,
            "roc_auc": model_acceptance.MINIMUM_ROC_AUC - 0.01,
        },
    )

    result = validate_model_acceptance(tmp_path)

    assert result["artifact_integrity_passed"] is True
    assert result["metrics_passed"] is False
    assert result["accepted_for_activation"] is False
    assert any("ROC-AUC is below" in reason for reason in result["reasons"])


def test_missing_metrics_file_fails_closed(tmp_path, monkeypatch):
    _write_test_artifacts(tmp_path, monkeypatch)
    (tmp_path / f"{model_acceptance.MODEL_VERSION}.metrics.json").unlink()

    result = validate_model_acceptance(tmp_path)

    assert result["artifact_integrity_passed"] is False
    assert result["metrics_passed"] is False
    assert result["accepted_for_activation"] is False
    assert any("missing" in reason.lower() for reason in result["reasons"])


def test_checksum_mismatch_fails_closed(tmp_path, monkeypatch):
    _write_test_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(model_acceptance, "_sha256_file", lambda path: "wrong-checksum")

    result = validate_model_acceptance(tmp_path)

    assert result["artifact_integrity_passed"] is False
    assert result["accepted_for_activation"] is False
    assert any("checksum" in reason.lower() for reason in result["reasons"])


@pytest.mark.parametrize(
    "overrides, expected_reason",
    [
        ({"model_version": "unexpected-version"}, "version"),
        ({"feature_columns": ["wrong_feature"]}, "Feature columns"),
    ],
)
def test_invalid_metadata_fails_closed(
    tmp_path, monkeypatch, overrides, expected_reason
):
    _write_test_artifacts(
        tmp_path,
        monkeypatch,
        metadata_overrides=overrides,
    )

    result = validate_model_acceptance(tmp_path)

    assert result["artifact_integrity_passed"] is False
    assert result["accepted_for_activation"] is False
    assert any(
        expected_reason.lower() in reason.lower()
        for reason in result["reasons"]
    )


@pytest.mark.parametrize(
    "metrics",
    [
        {"recall": "not-a-number", "roc_auc": 0.95},
        {"recall": float("nan"), "roc_auc": 0.95},
        {"recall": float("inf"), "roc_auc": 0.95},
        {"recall": 1.01, "roc_auc": 0.95},
        {"recall": 0.90, "roc_auc": -0.01},
        {"recall": True, "roc_auc": 0.95},
        {"roc_auc": 0.95},
    ],
)
def test_invalid_metrics_fail_closed(tmp_path, monkeypatch, metrics):
    _write_test_artifacts(tmp_path, monkeypatch, metrics=metrics)

    result = validate_model_acceptance(tmp_path)

    assert result["metrics_passed"] is False
    assert result["accepted_for_activation"] is False
    assert result["reasons"]


@pytest.mark.parametrize("filename", [
    "risk-logreg-1.0.0.metadata.json",
    "risk-logreg-1.0.0.metrics.json",
])
def test_malformed_json_fails_closed(tmp_path, monkeypatch, filename):
    _write_test_artifacts(tmp_path, monkeypatch)
    (tmp_path / filename).write_text("{invalid json", encoding="utf-8")

    result = validate_model_acceptance(tmp_path)

    assert result["accepted_for_activation"] is False
    assert result["reasons"]


def test_non_object_json_fails_closed(tmp_path, monkeypatch):
    _write_test_artifacts(tmp_path, monkeypatch)
    metadata_path = tmp_path / (
        f"{model_acceptance.MODEL_VERSION}.metadata.json"
    )
    metadata_path.write_text("[]", encoding="utf-8")

    result = validate_model_acceptance(tmp_path)

    assert result["accepted_for_activation"] is False
    assert result["artifact_integrity_passed"] is False
    assert result["reasons"]


def test_unexpected_checksum_error_fails_closed(tmp_path, monkeypatch):
    _write_test_artifacts(tmp_path, monkeypatch)

    def raise_unexpected_error(path):
        raise RuntimeError("simulated checksum failure")

    monkeypatch.setattr(
        model_acceptance, "_sha256_file", raise_unexpected_error
    )

    result = validate_model_acceptance(tmp_path)

    assert result["accepted_for_activation"] is False
    assert result["artifact_integrity_passed"] is False
    assert any(
        "RuntimeError" in reason for reason in result["reasons"]
    )
