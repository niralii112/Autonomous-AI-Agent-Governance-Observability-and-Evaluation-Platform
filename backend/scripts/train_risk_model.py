
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BACKEND_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"

TRAIN_PATH = ARTIFACTS_DIR / "risk_train_v1.csv"
EVAL_PATH = ARTIFACTS_DIR / "risk_eval_v1.csv"

MODEL_VERSION = "risk-logreg-1.0.0"

FEATURE_COLUMNS = [
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

NUMERIC_COLUMNS = [
    "amount_usd",
    "record_count",
    "recent_blocked_count_24h",
    "recent_failed_count_24h",
    "agent_trust_tier",
]

CATEGORICAL_COLUMNS = [
    "tool_sensitivity",
    "agent_category",
    "action_type",
    "target_environment",
]

BOOLEAN_COLUMNS = [
    "involves_pii",
    "is_outside_business_hours",
]


def sha256_file(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def prepare_features(dataset: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """Validate and prepare model features using the specified column types."""
    missing = set(FEATURE_COLUMNS + ["label_high_risk"]) - set(dataset.columns)

    if missing:
        raise ValueError(
            f"{dataset_name} dataset is missing columns: {sorted(missing)}"
        )

    if dataset[FEATURE_COLUMNS].isnull().any().any():
        raise ValueError(
            f"{dataset_name} dataset contains missing feature values"
        )

    prepared = dataset[FEATURE_COLUMNS].copy()

    for column in BOOLEAN_COLUMNS:
        values = set(prepared[column].dropna().unique().tolist())

        if not values.issubset({True, False, 0, 1}):
            raise ValueError(
                f"{dataset_name} feature {column!r} must contain boolean "
                "or 0/1 values"
            )

        prepared[column] = prepared[column].astype(int)

    for column in NUMERIC_COLUMNS:
        prepared[column] = pd.to_numeric(
            prepared[column], errors="raise"
        )

    return prepared


def main() -> None:
    if not TRAIN_PATH.is_file():
        raise FileNotFoundError(f"Training dataset not found: {TRAIN_PATH}")

    if not EVAL_PATH.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found: {EVAL_PATH}")

    train = pd.read_csv(TRAIN_PATH)
    evaluation = pd.read_csv(EVAL_PATH)

    X_train = prepare_features(train, "training")
    X_eval = prepare_features(evaluation, "evaluation")

    y_train = train["label_high_risk"]
    y_eval = evaluation["label_high_risk"]

    for name, labels in (
        ("training", y_train),
        ("evaluation", y_eval),
    ):
        if labels.isnull().any():
            raise ValueError(f"{name} dataset contains missing labels")

        if not set(labels.unique()).issubset({0, 1}):
            raise ValueError(
                f"{name} labels must contain only 0 and 1"
            )

        if labels.nunique() != 2:
            raise ValueError(
                f"{name} dataset must contain both risk-label classes"
            )

    y_train = y_train.astype(int)
    y_eval = y_eval.astype(int)

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                StandardScaler(),
                NUMERIC_COLUMNS + BOOLEAN_COLUMNS,
            ),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_COLUMNS,
            ),
        ],
        remainder="drop",
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessing),
            (
                "classifier",
                LogisticRegression(
                    solver="lbfgs",
                    C=1.0,
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_eval)
    probabilities = model.predict_proba(X_eval)[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_eval, predictions)),
        "precision": float(
            precision_score(y_eval, predictions, zero_division=0)
        ),
        "recall": float(
            recall_score(y_eval, predictions, zero_division=0)
        ),
        "f1": float(f1_score(y_eval, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_eval, probabilities)),
        "confusion_matrix": confusion_matrix(
            y_eval, predictions, labels=[0, 1]
        ).tolist(),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = ARTIFACTS_DIR / f"{MODEL_VERSION}.joblib"
    metadata_path = ARTIFACTS_DIR / f"{MODEL_VERSION}.metadata.json"
    metrics_path = ARTIFACTS_DIR / f"{MODEL_VERSION}.metrics.json"

    joblib.dump(model, model_path)

    metadata = {
        "model_version": MODEL_VERSION,
        "model_type": "sklearn_pipeline_logistic_regression",
        "training_rows": int(len(train)),
        "evaluation_rows": int(len(evaluation)),
        "feature_columns": FEATURE_COLUMNS,
        "positive_class": 1,
        "class_weight": "balanced",
        "solver": "lbfgs",
        "C": 1.0,
        "max_iter": 1000,
        "sha256": sha256_file(model_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_source": "synthetic_only",
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    metrics_path.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print("Model training completed.")
    print(f"Model: {model_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Metrics: {metrics_path}")
    print(f"Model SHA-256: {metadata['sha256']}")
    print("\nEvaluation metrics:")
    print(json.dumps(metrics, indent=2))
    print("\nClassification report:")
    print(classification_report(y_eval, predictions, zero_division=0))
    print("Evaluation data source: synthetic holdout dataset only.")


if __name__ == "__main__":
    main()
