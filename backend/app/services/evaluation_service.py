
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


from statistics import mean


def _status(value) -> str:
    """Normalize enum or string status values."""
    return str(getattr(value, "value", value) or "").upper()


def evaluate_production_records(records: dict) -> dict:
    """
    Calculate operational metrics from real production database records.

    Production records do not contain ground-truth labels, so this function
    deliberately does not calculate precision, recall, F1 or ROC-AUC.
    """
    actions = records["actions"]
    decisions = records["decisions"]
    approvals = records["approvals"]
    executions = records["executions"]
    risks = records["risks"]

    total_actions = len(actions)

    allowed = [
        row for row in decisions
        if _status(row.final_decision) in {"ALLOW", "APPROVE"}
    ]
    blocked = [
        row for row in decisions
        if _status(row.final_decision) in {"BLOCK", "DENY"}
    ]
    review = [
        row for row in decisions
        if _status(row.final_decision) in {
            "REQUIRE_APPROVAL", "HUMAN_REVIEW", "REVIEW"
        }
    ]

    approved = [
        row for row in approvals
        if _status(row.approval_status) == "APPROVED"
    ]
    rejected = [
        row for row in approvals
        if _status(row.approval_status) == "REJECTED"
    ]
    expired = [
        row for row in approvals
        if _status(row.approval_status) == "EXPIRED"
    ]

    succeeded = [
        row for row in executions
        if _status(row.execution_status) == "SUCCEEDED"
    ]
    failed = [
        row for row in executions
        if _status(row.execution_status) == "FAILED"
    ]

    latencies = [
        float(row.latency_ms)
        for row in executions
        if row.latency_ms is not None
    ]
    latencies.sort()

    p95 = None
    if latencies:
        p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
        p95 = latencies[p95_index]

    policy_violations = sum(
        1 for row in decisions
        if "VIOLATION" in _status(row.policy_result)
    )

    fallback_count = sum(
        1 for row in risks
        if _status(row.risk_source) in {
            "HEURISTIC_FALLBACK", "FALLBACK"
        }
    )

    def rate(numerator: int, denominator: int):
        return numerator / denominator if denominator else None

    return {
        "total_actions": total_actions,
        "allow_count": len(allowed),
        "human_review_count": len(review),
        "block_count": len(blocked),
        "executions_total": len(executions),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "expired_count": len(expired),
        "policy_violation_count": policy_violations,
        "task_completion_rate": rate(len(succeeded), total_actions),
        "execution_success_rate": rate(len(succeeded), len(executions)),
        "blocked_action_rate": rate(len(blocked), total_actions),
        "human_review_rate": rate(len(review), total_actions),
        "approval_rate": rate(len(approved), len(approvals)),
        "rejection_rate": rate(len(rejected), len(approvals)),
        "policy_violation_rate": rate(policy_violations, total_actions),
        "fallback_risk_rate": rate(fallback_count, len(risks)),
        "avg_tool_latency_ms": mean(latencies) if latencies else None,
        "p95_tool_latency_ms": p95,
        "agent_reliability_score": rate(
            len(succeeded), len(executions)
        ),
    }


async def evaluate_agent_performance(
    session,
    agent_id,
    window_start,
    window_end,
):
    from app.repositories.evaluation_repository import (
        get_agent,
        get_production_records,
    )

    agent = await get_agent(session, agent_id)
    if agent is None:
        raise ValueError(f"Agent not found: {agent_id}")

    records = await get_production_records(
        session,
        window_start=window_start,
        window_end=window_end,
        agent_id=agent_id,
    )

    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "window_start": window_start,
        "window_end": window_end,
        "metrics": evaluate_production_records(records),
    }
