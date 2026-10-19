
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow the script to import the existing ML heuristic.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.heuristic import heuristic_risk_score


SEED = 42
TOTAL_ROWS = 6000
TRAIN_ROWS = 5100
EVAL_ROWS = 900

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


def generate_features(
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate artificial risk features without production data."""

    sensitivities = np.array(
        ["READ_ONLY", "SENSITIVE_READ", "WRITE", "PRIVILEGED"]
    )
    agents = np.array(["FINANCE", "SUPPORT", "IT"])
    actions = np.array([
        "FINANCE_PROPOSE_PAYMENT",
        "FINANCE_ACCESS_SENSITIVE_RECORDS",
        "SUPPORT_PROPOSE_REFUND",
        "SUPPORT_ACCESS_CUSTOMER_INFO",
        "IT_READ_LOGS",
        "IT_DEPLOY_SERVICE",
    ])
    environments = np.array(["NONE", "STAGING", "PRODUCTION"])

    rows = []

    for _ in range(TOTAL_ROWS):
        action = str(rng.choice(actions))

        amount = 0.0
        record_count = 0
        involves_pii = False

        if action in {
            "FINANCE_PROPOSE_PAYMENT",
            "SUPPORT_PROPOSE_REFUND",
        }:
            amount = float(
                rng.choice([
                    0, 50, 100, 250, 500, 1000,
                    2500, 10000, 25000, 50000, 100000,
                ])
            )

        if action == "FINANCE_ACCESS_SENSITIVE_RECORDS":
            record_count = int(
                rng.choice([1, 10, 50, 100, 250, 1000, 2000])
            )
            involves_pii = bool(
                rng.choice([True, False], p=[0.75, 0.25])
            )

        elif action == "SUPPORT_ACCESS_CUSTOMER_INFO":
            record_count = 1
            involves_pii = True

        rows.append({
            "tool_sensitivity": str(rng.choice(sensitivities)),
            "agent_category": str(rng.choice(agents)),
            "action_type": action,
            "amount_usd": amount,
            "record_count": record_count,
            "involves_pii": involves_pii,
            "target_environment": str(rng.choice(
                environments, p=[0.35, 0.25, 0.40]
            )),
            "is_outside_business_hours": bool(
                rng.choice([True, False], p=[0.35, 0.65])
            ),
            "recent_blocked_count_24h": int(
                rng.integers(0, 7)
            ),
            "recent_failed_count_24h": int(
                rng.integers(0, 8)
            ),
            "agent_trust_tier": int(
                rng.choice([1, 2, 3], p=[0.20, 0.50, 0.30])
            ),
        })

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def add_synthetic_labels(
    features: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Create artificial binary labels from heuristic scores plus noise."""

    labelled = features.copy()
    scores = []

    for record in labelled.to_dict(orient="records"):
        score, _ = heuristic_risk_score(record)
        scores.append(score)

    labelled["heuristic_score"] = scores

    noise = rng.normal(loc=0.0, scale=0.08, size=len(labelled))
    noisy_scores = np.asarray(scores) + noise

    labelled["label_high_risk"] = (noisy_scores >= 0.60).astype(int)

    return labelled


def main() -> None:
    rng = np.random.default_rng(SEED)

    features = generate_features(rng)
    dataset = add_synthetic_labels(features, rng)

    # Shuffle reproducibly before splitting.
    dataset = dataset.sample(
        frac=1,
        random_state=SEED,
    ).reset_index(drop=True)

    train = dataset.iloc[:TRAIN_ROWS].copy()
    evaluation = dataset.iloc[TRAIN_ROWS:].copy()

    artifacts_dir = BACKEND_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    train_path = artifacts_dir / "risk_train_v1.csv"
    eval_path = artifacts_dir / "risk_eval_v1.csv"

    train.to_csv(train_path, index=False)
    evaluation.to_csv(eval_path, index=False)

    print("Synthetic risk dataset generated successfully.")
    print(f"Training file: {train_path}")
    print(f"Evaluation file: {eval_path}")
    print(f"Training rows: {len(train)}")
    print(f"Evaluation rows: {len(evaluation)}")
    print(
    "Training label counts:\n"
    f"{train['label_high_risk'].value_counts().sort_index()}"
    )
    print(
    "Evaluation label counts:\n"
    f"{evaluation['label_high_risk'].value_counts().sort_index()}"
    )
    print("Data source: synthetic only.")


if __name__ == "__main__":
    main()
