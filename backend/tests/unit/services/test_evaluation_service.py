
import pytest

from app.services.evaluation_service import (
    evaluate_binary_classifier,
    evaluate_by_agent_category,
)


def test_evaluation_returns_expected_metrics():
    result = evaluate_binary_classifier(
        y_true=[0, 0, 1, 1],
        y_pred=[0, 1, 1, 1],
        y_score=[0.1, 0.7, 0.8, 0.9],
    )

    assert result["sample_count"] == 4
    assert result["accuracy"] == 0.75
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == 1.0
    assert result["f1"] == pytest.approx(0.8)
    assert result["confusion_matrix"] == [[1, 1], [0, 2]]
    assert 0.0 <= result["roc_auc"] <= 1.0


def test_evaluation_without_scores_omits_roc_auc():
    result = evaluate_binary_classifier([0, 1], [0, 1])

    assert result["accuracy"] == 1.0
    assert "roc_auc" not in result


def test_evaluation_rejects_empty_labels():
    with pytest.raises(ValueError, match="cannot be empty"):
        evaluate_binary_classifier([], [])


def test_evaluation_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="equal lengths"):
        evaluate_binary_classifier([0, 1], [1])


def test_evaluation_rejects_non_binary_labels():
    with pytest.raises(ValueError, match="binary labels"):
        evaluate_binary_classifier([0, 2], [0, 1])


def test_evaluation_handles_single_class_auc():
    result = evaluate_binary_classifier(
        y_true=[1, 1],
        y_pred=[1, 0],
        y_score=[0.9, 0.4],
    )

    assert result["roc_auc"] is None


def test_evaluation_calculates_metrics_by_agent_category():
    result = evaluate_by_agent_category(
        y_true=[0, 1, 1, 0, 1],
        y_pred=[0, 1, 0, 1, 1],
        agent_categories=[
            "FINANCE",
            "FINANCE",
            "FINANCE",
            "SUPPORT",
            "SUPPORT",
        ],
    )

    assert result["FINANCE"]["sample_count"] == 3
    assert result["FINANCE"]["precision"] == 1.0
    assert result["FINANCE"]["recall"] == 0.5

    assert result["SUPPORT"]["sample_count"] == 2
    assert result["SUPPORT"]["precision"] == pytest.approx(0.5)
    assert result["SUPPORT"]["recall"] == 1.0


def test_category_evaluation_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="equal lengths"):
        evaluate_by_agent_category(
            [0, 1],
            [0, 1],
            ["FINANCE"],
        )


def test_category_evaluation_rejects_empty_category():
    with pytest.raises(ValueError, match="non-empty strings"):
        evaluate_by_agent_category(
            [0],
            [0],
            [""],
        )


@pytest.mark.parametrize(
    "invalid_score",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.1,
        1.1,
    ],
)
def test_evaluation_rejects_invalid_scores(invalid_score):
    with pytest.raises(ValueError, match="finite numbers"):
        evaluate_binary_classifier(
            y_true=[0, 1],
            y_pred=[0, 1],
            y_score=[0.1, invalid_score],
        )


def test_evaluation_rejects_non_numeric_scores():
    with pytest.raises(ValueError, match="finite numbers"):
        evaluate_binary_classifier(
            y_true=[0, 1],
            y_pred=[0, 1],
            y_score=[0.1, "invalid"],
        )
