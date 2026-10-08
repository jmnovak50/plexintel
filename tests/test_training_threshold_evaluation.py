import numpy as np

from train_model import (
    EVALUATION_THRESHOLDS,
    evaluate_classification_thresholds,
    print_classification_threshold_evaluation,
    thresholds_with_best_metric,
)


def test_evaluates_all_seven_thresholds_with_explicit_label_order():
    y_true = np.array([0, 0, 1, 1])
    positive_probabilities = np.array([0.10, 0.70, 0.60, 0.90])

    results = evaluate_classification_thresholds(y_true, positive_probabilities)

    assert [result["threshold"] for result in results] == list(EVALUATION_THRESHOLDS)
    np.testing.assert_array_equal(
        results[0]["confusion_matrix"],
        np.array([[1, 1], [0, 2]]),
    )


def test_metrics_match_classification_report_and_handle_missing_predictions():
    y_true = np.array([0, 0, 1, 1])
    positive_probabilities = np.array([0.10, 0.20, 0.60, 0.70])

    result = evaluate_classification_thresholds(
        y_true,
        positive_probabilities,
        thresholds=[0.80],
    )[0]
    report = result["classification_report_data"]

    np.testing.assert_array_equal(
        result["confusion_matrix"],
        np.array([[2, 0], [2, 0]]),
    )
    assert result["class_1_precision"] == 0
    assert result["class_1_recall"] == 0
    assert result["class_1_f1"] == 0
    assert result["accuracy"] == report["accuracy"]
    assert result["class_0_precision"] == report["0"]["precision"]
    assert result["class_0_recall"] == report["0"]["recall"]
    assert result["class_0_f1"] == report["0"]["f1-score"]
    assert result["class_1_precision"] == report["1"]["precision"]
    assert result["class_1_recall"] == report["1"]["recall"]
    assert result["class_1_f1"] == report["1"]["f1-score"]
    assert result["macro_f1"] == report["macro avg"]["f1-score"]
    assert result["weighted_f1"] == report["weighted avg"]["f1-score"]
    assert result["balanced_accuracy"] == 0.5


def test_best_metric_preserves_tied_thresholds():
    results = [
        {"threshold": 0.50, "macro_f1": 0.70},
        {"threshold": 0.55, "macro_f1": 0.75},
        {"threshold": 0.60, "macro_f1": 0.75},
    ]

    tied_results = thresholds_with_best_metric(results, "macro_f1")

    assert [result["threshold"] for result in tied_results] == [0.55, 0.60]


def test_summary_follows_detailed_reports_and_uses_their_values(capsys):
    results = evaluate_classification_thresholds(
        np.array([0, 0, 1, 1]),
        np.array([0.10, 0.70, 0.60, 0.90]),
        thresholds=[0.50, 0.80],
    )

    best_metrics = print_classification_threshold_evaluation(results)
    output = capsys.readouterr().out

    assert output.index("Classification report at threshold 0.80") < output.index(
        "Threshold comparison"
    )
    expected_summary_row = (
        f"0.50 | {results[0]['accuracy']:.3f} | "
        f"{results[0]['class_0_precision']:.3f} | "
        f"{results[0]['class_0_recall']:.3f} | "
        f"{results[0]['class_0_f1']:.3f} | "
        f"{results[0]['class_1_precision']:.3f} | "
        f"{results[0]['class_1_recall']:.3f} | "
        f"{results[0]['class_1_f1']:.3f} | "
        f"{results[0]['macro_f1']:.3f} | "
        f"{results[0]['weighted_f1']:.3f} | "
        f"{results[0]['balanced_accuracy']:.3f}"
    )
    assert expected_summary_row in output
    assert set(best_metrics) == {
        "macro_f1",
        "class_0_f1",
        "class_0_recall",
        "balanced_accuracy",
    }
