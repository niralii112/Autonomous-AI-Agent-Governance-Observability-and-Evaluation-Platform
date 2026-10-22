
import pytest

from app.services.agent_evaluation import evaluate_agent_outcomes


def test_evaluates_success_failure_and_completion() -> None:
    outcomes = [
        {
            "status": "SUCCEEDED",
            "task_completed": True,
            "tool_latency_ms": 100,
            "agent_category": "FINANCE",
        },
        {
            "status": "FAILED",
            "task_completed": False,
            "tool_latency_ms": 300,
            "agent_category": "FINANCE",
        },
        {
            "status": "SUCCEEDED",
            "task_completed": True,
            "tool_latency_ms": 200,
            "agent_category": "CUSTOMER_SUPPORT",
        },
    ]

    result = evaluate_agent_outcomes(outcomes)

    assert result["total_actions"] == 3
    assert result["succeeded_count"] == 2
    assert result["failed_count"] == 1
    assert result["task_completion_rate"] == pytest.approx(2 / 3)
    assert result["execution_success_rate"] == pytest.approx(2 / 3)
    assert result["avg_tool_latency_ms"] == pytest.approx(200)
    assert result["per_agent_category"]["FINANCE"]["total"] == 2


def test_empty_outcomes_return_empty_metrics() -> None:
    result = evaluate_agent_outcomes([])

    assert result["total_actions"] == 0
    assert result["task_completion_rate"] is None
    assert result["execution_success_rate"] is None


def test_rejects_negative_latency() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        evaluate_agent_outcomes(
            [
                {
                    "status": "FAILED",
                    "task_completed": False,
                    "tool_latency_ms": -1,
                }
            ]
        )
