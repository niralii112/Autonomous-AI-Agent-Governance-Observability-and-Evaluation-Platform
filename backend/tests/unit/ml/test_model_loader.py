
import json
import shutil
from pathlib import Path

from app.ml.model_loader import (
    MODEL_VERSION,
    get_active_model,
)


REAL_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[3] / "artifacts"
)


def copy_model_artifacts(destination: Path) -> None:
    """Copy the trained artifacts into an isolated test directory."""
    destination.mkdir(parents=True, exist_ok=True)

    for suffix in (".joblib", ".metadata.json"):
        filename = f"{MODEL_VERSION}{suffix}"
        source = REAL_ARTIFACT_DIR / filename

        if not source.is_file():
            raise FileNotFoundError(f"Required test artifact missing: {source}")

        shutil.copy2(source, destination / filename)


def test_valid_model_loads(tmp_path, monkeypatch):
    copy_model_artifacts(tmp_path)
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(tmp_path))

    model = get_active_model()

    assert model is not None
    assert hasattr(model, "predict_proba")


def test_missing_model_returns_none(tmp_path, monkeypatch):
    # The configured directory exists, but contains no model artifacts.
    tmp_path.mkdir(exist_ok=True)
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(tmp_path))

    model = get_active_model()

    assert model is None


def test_checksum_mismatch_returns_none(tmp_path, monkeypatch):
    copy_model_artifacts(tmp_path)
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(tmp_path))

    metadata_path = tmp_path / f"{MODEL_VERSION}.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    metadata["sha256"] = "0" * 64

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    model = get_active_model()

    assert model is None

def test_malformed_metadata_returns_none(tmp_path, monkeypatch):
    copy_model_artifacts(tmp_path)
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(tmp_path))

    metadata_path = tmp_path / f"{MODEL_VERSION}.metadata.json"
    metadata_path.write_text("{invalid json", encoding="utf-8")

    model = get_active_model()

    assert model is None


def test_corrupted_model_artifact_returns_none(tmp_path, monkeypatch):
    copy_model_artifacts(tmp_path)
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(tmp_path))

    model_path = tmp_path / f"{MODEL_VERSION}.joblib"
    model_path.write_bytes(b"not a valid joblib artifact")

    # Update the checksum so the loader reaches deserialization.
    import hashlib

    metadata_path = tmp_path / f"{MODEL_VERSION}.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    model = get_active_model()

    assert model is None