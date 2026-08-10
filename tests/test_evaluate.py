"""Scoring, and the reason accuracy alone is not reported anywhere."""

import pandas as pd
import pytest

from expense_analyzer import evaluate


@pytest.fixture
def imbalanced():
    """Eight of one class, two of another — the shape of the real benchmark."""
    truth = pd.Series(["Food"] * 8 + ["Health"] * 2)
    lazy = pd.Series(["Food"] * 10)
    return truth, lazy


class TestScore:
    def test_perfect_predictions_score_one(self):
        truth = pd.Series(["Food", "Health", "Food"])
        result = evaluate.score("perfect", truth, truth.copy())

        assert result.accuracy == 1.0
        assert result.macro_f1 == 1.0
        assert result.n == 3

    def test_macro_f1_exposes_a_model_that_only_predicts_the_big_class(self, imbalanced):
        """The whole reason macro F1 is reported. 80% accuracy looks
        respectable until you see the model never found a single Health row."""
        truth, lazy = imbalanced
        result = evaluate.score("lazy", truth, lazy)

        assert result.accuracy == 0.8
        assert result.macro_f1 < 0.5

    def test_a_class_never_predicted_scores_zero_rather_than_raising(self, imbalanced):
        truth, lazy = imbalanced
        assert evaluate.score("lazy", truth, lazy).macro_f1 == pytest.approx(0.444, abs=0.01)


class TestComparisonTable:
    def test_lists_every_approach_with_a_header(self):
        rows = [
            evaluate.Scores("majority class", 0.429, 0.05, 0.257, 485),
            evaluate.Scores("TF-IDF + LogReg", 0.870, 0.769, 0.864, 485),
        ]
        table = evaluate.comparison_table(rows)

        assert "accuracy" in table
        assert "majority class" in table
        assert "42.9%" in table
        assert "0.769" in table


class TestPerClassReport:
    def test_orders_classes_by_recall_so_the_misses_come_first(self, imbalanced):
        truth, lazy = imbalanced
        report = evaluate.per_class_report(truth, lazy)

        classes = [name for name in report.index if "avg" not in name]
        assert classes[0] == "Health", "the class the model never found comes first"
        assert report.loc["Health", "recall"] == 0.0
        assert report.loc["Food", "recall"] == 1.0

    def test_keeps_the_summary_rows_at_the_bottom(self, imbalanced):
        truth, lazy = imbalanced
        report = evaluate.per_class_report(truth, lazy)

        assert list(report.index[-2:]) == ["macro avg", "weighted avg"]


class TestConfusion:
    def test_rows_are_truth_and_columns_are_guesses(self):
        truth = pd.Series(["Food", "Food", "Health"])
        predicted = pd.Series(["Food", "Health", "Health"])

        matrix = evaluate.confusion(truth, predicted)

        assert matrix.at["Food", "Food"] == 1
        assert matrix.at["Food", "Health"] == 1, "one Food row was called Health"
        assert matrix.at["Health", "Health"] == 1

    def test_includes_labels_that_only_appear_in_the_predictions(self):
        truth = pd.Series(["Food", "Food"])
        predicted = pd.Series(["Food", "Gift"])

        assert "Gift" in evaluate.confusion(truth, predicted).columns


class TestWorstConfusions:
    def test_names_the_most_frequent_mistake_first(self):
        truth = pd.Series(["Food"] * 5 + ["Health"] * 2)
        predicted = pd.Series(["Household"] * 5 + ["Food"] * 2)

        worst = evaluate.worst_confusions(truth, predicted)

        assert list(worst.iloc[0]) == ["Food", "Household", 5]

    def test_excludes_correct_predictions(self):
        truth = pd.Series(["Food"] * 9 + ["Health"])
        predicted = pd.Series(["Food"] * 9 + ["Food"])

        worst = evaluate.worst_confusions(truth, predicted)

        assert len(worst) == 1
        assert worst.at[0, "actual"] == "Health"


class TestPlotConfusion:
    def test_writes_a_png_and_creates_the_directory(self, tmp_path):
        truth = pd.Series(["Food", "Health", "Food"])
        predicted = pd.Series(["Food", "Food", "Food"])

        path = evaluate.plot_confusion(
            truth, predicted, tmp_path / "nested" / "cm.png", "test matrix"
        )

        assert path.exists()
        assert path.stat().st_size > 0

    def test_survives_a_class_with_no_predictions_at_all(self, tmp_path):
        """Row-normalising divides by the row total, which is zero for a
        class present in predictions but absent from truth."""
        truth = pd.Series(["Food", "Food"])
        predicted = pd.Series(["Food", "Gift"])

        path = evaluate.plot_confusion(truth, predicted, tmp_path / "cm.png", "edge case")

        assert path.exists()
