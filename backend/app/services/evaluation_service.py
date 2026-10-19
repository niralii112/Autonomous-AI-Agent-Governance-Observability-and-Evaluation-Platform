
from __future__ import annotations

import math
from typing import Any

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _binary_metrics(
    y_true: list[int],
    y_pred: list[int],
    y_score: list[float] | None = None,
) -> dict[str, Any]:
    if not y_true:
        raise ValueError("y_true cannot be empty")

    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have equal lengths")

    if any(label not in (0, 1) for label in y_true):
        raise ValueError("y_true must contain only binary labels 0 and 1")

    if any(label not in (0, 1) for label in y_pred):
        raise ValueError("y_pred must contain only binary labels 0 and 1")

    if y_score is not None:
        if len(y_score) != len(y_true):
            raise ValueError("y_score must have the same length as y_true")

        try:
            scores = [float(score) for score in y_score]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "y_score values must be finite numbers between 0 and 1"
            ) from exc

        if any(
            not math.isfinite(score) or not 0.0 <= score <= 1.0
            for score in scores
        ):
            raise ValueError(
                "y_score values must be finite numbers between 0 and 1"
            )

        y_score = scores

    metrics: dict[str, Any] = {
        "sample_count": len(y_true),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, zero_division=0)
        ),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=[0, 1]
        ).tolist(),
    }

    if y_score is not None:
        metrics["roc_auc"] = (
            float(roc_auc_score(y_true, y_score))
            if len(set(y_true)) == 2
            else None
        )

    return metrics


def evaluate_binary_classifier(
    y_true: list[int],
    y_pred: list[int],
    y_score: list[float] | None = None,
) -> dict[str, Any]:
    """Evaluate binary predictions against labelled evaluation data."""
    return _binary_metrics(y_true, y_pred, y_score)


def evaluate_by_agent_category(
    y_true: list[int],
    y_pred: list[int],
    agent_categories: list[str],
) -> dict[str, dict[str, float | int]]:
    """
    Calculate precision and recall for each agent category.

    Inputs must come from a labelled evaluation dataset, not production
    records. Categories with no positive examples receive recall 0.0.
    """
    if not y_true:
        raise ValueError("y_true cannot be empty")

    if not (len(y_true) == len(y_pred) == len(agent_categories)):
        raise ValueError(
            "y_true, y_pred and agent_categories must have equal lengths"
        )

    # Validate labels and predictions through the common metric helper.
    _binary_metrics(y_true, y_pred)

    if any(
        not isinstance(category, str) or not category.strip()
        for category in agent_categories
    ):
        raise ValueError("agent_categories must contain non-empty strings")

    results: dict[str, dict[str, float | int]] = {}

    for category in sorted(set(agent_categories)):
        indices = [
            index
            for index, value in enumerate(agent_categories)
            if value == category
        ]
        category_true = [y_true[index] for index in indices]
        category_pred = [y_pred[index] for index in indices]

        results[category] = {
            "sample_count": len(indices),
            "precision": float(
                precision_score(
                    category_true,
                    category_pred,
                    zero_division=0,
                )
            ),
            "recall": float(
                recall_score(
                    category_true,
                    category_pred,
                    zero_division=0,
                )
            ),
        }

    return results
