
import json
import shutil
from pathlib import Path

from app.ml.model_loader import MODEL_VERSION, get_active_model


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_SOURCE = PROJECT_ROOT / "artifacts"


def prepare_artifacts(tmp_path, monkeypatch):
    """Copy the trained artifacts to an isolated test directory."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    for suffix in (".joblib", ".metadata.json"):
        source = ARTIFACT_SOURCE / f"{MODEL_VERSION}{suffix}"
        assert source.is_file(), f"Missing expected artifact: {source.name}"
        shutil.copy2(source, artifact_dir / source.name)

    monkeypatch.setenv("RISK_MODEL_ARTIFACT_DIR", str(artifact_dir))
    return artifact_dir


def test_loader_rejects_wrong_model_version(tmp_path, monkeypatch):
    artifact_dir = prepare_artifacts(tmp_path, monkeypatch)
    metadata_path = artifact_dir / f"{MODEL_VERSION}.metadata.json"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["model_version"] = "incorrect-version"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert get_active_model() is None


def test_loader_rejects_wrong_feature_list(tmp_path, monkeypatch):
    artifact_dir = prepare_artifacts(tmp_path, monkeypatch)
    metadata_path = artifact_dir / f"{MODEL_VERSION}.metadata.json"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["feature_columns"] = ["unexpected_feature"]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert get_active_model() is None
