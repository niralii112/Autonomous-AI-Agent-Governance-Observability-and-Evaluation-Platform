
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def evaluate_agent_outcomes(
    outcomes: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize recorded, simulated agent outcomes.

    Each outcome should contain:
      - status: SUCCEEDED or FAILED
      - task_completed: bool
      - tool_latency_ms: optional non-negative number
      - agent_category: optional category string

    These metrics describe supplied outcomes; they are not a substitute
    for production database metrics.
    """
    total = len(outcomes)

    if total == 0:
        return {
            "total_actions": 0,
            "succeeded_count": 0,
            "failed_count": 0,
            "task_completion_rate": None,
            "execution_success_rate": None,
            "avg_tool_latency_ms": None,
            "p95_tool_latency_ms": None,
            "per_agent_category": {},
        }

    succeeded = [
        item for item in outcomes
        if str(item.get("status", "")).upper() == "SUCCEEDED"
    ]
    failed = [
        item for item in outcomes
        if str(item.get("status", "")).upper() == "FAILED"
    ]

    completed = [
        item for item in outcomes
        if item.get("task_completed") is True
    ]

    latencies: list[float] = []
    for item in outcomes:
        value = item.get("tool_latency_ms")
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("tool_latency_ms must be numeric")
        if value < 0:
            raise ValueError("tool_latency_ms cannot be negative")
        latencies.append(float(value))

    ordered_latencies = sorted(latencies)
    p95 = None
    if ordered_latencies:
        # Nearest-rank 95th percentile.
        index = max(0, int(0.95 * len(ordered_latencies) + 0.999999) - 1)
        p95 = ordered_latencies[index]

    categories: dict[str, dict[str, int]] = {}
    for item in outcomes:
        category = str(item.get("agent_category", "UNKNOWN")).upper()
        bucket = categories.setdefault(
            category,
            {"total": 0, "succeeded": 0, "failed": 0, "completed": 0},
        )
        bucket["total"] += 1

        if str(item.get("status", "")).upper() == "SUCCEEDED":
            bucket["succeeded"] += 1
        elif str(item.get("status", "")).upper() == "FAILED":
            bucket["failed"] += 1

        if item.get("task_completed") is True:
            bucket["completed"] += 1

    return {
        "total_actions": total,
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "task_completion_rate": len(completed) / total,
        "execution_success_rate": len(succeeded) / total,
        "avg_tool_latency_ms": (
            sum(latencies) / len(latencies) if latencies else None
        ),
        "p95_tool_latency_ms": p95,
        "per_agent_category": {
            category: {
                **counts,
                "task_completion_rate": (
                    counts["completed"] / counts["total"]
                ),
                "execution_success_rate": (
                    counts["succeeded"] / counts["total"]
                ),
            }
            for category, counts in categories.items()
        },
    }
