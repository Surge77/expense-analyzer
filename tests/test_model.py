"""The classifier, and the benchmark preparation it depends on.

Trained here on a tiny hand-built corpus rather than the real download, so
the suite stays offline and fast. The real numbers come from the integration
tests and from `docs/results.md`.
"""

import pandas as pd
import pytest

from expense_analyzer import baselines, benchmark, model


@pytest.fixture
def tiny_corpus() -> pd.DataFrame:
    """Two obviously separable classes, repeated enough to fit on."""
    food = ["idli dosa", "vada pav snack", "lunch thali", "tea and samosa", "dinner rice"]
    travel = ["bus ticket", "train pass", "auto rickshaw fare", "petrol refill", "cab ride"]
    return pd.DataFrame(
        {
            "narration": food * 3 + travel * 3,
            "label": ["Food"] * 15 + ["Transportation"] * 15,
        }
    )


class TestCollapseRareClasses:
    def test_folds_classes_below_the_threshold_into_other(self):
        labels = pd.Series(["Food"] * 25 + ["Interest"] * 3)

        collapsed = benchmark.collapse_rare_classes(labels, minimum=20)

        assert set(collapsed) == {"Food", baselines.OTHER}
        assert (collapsed == baselines.OTHER).sum() == 3

    def test_leaves_classes_at_the_threshold_alone(self):
        labels = pd.Series(["Food"] * 20)
        assert set(benchmark.collapse_rare_classes(labels, minimum=20)) == {"Food"}


class TestBaselines:
    def test_majority_always_answers_the_commonest_training_class(self):
        train = pd.DataFrame({"label": ["Food"] * 8 + ["Health"] * 2})
        test = pd.DataFrame({"label": ["Health"] * 3})

        predicted = baselines.predict_majority(train, test)

        assert set(predicted) == {"Food"}
        assert len(predicted) == 3

    def test_rules_are_translated_into_the_benchmark_vocabulary(self):
        """Rules say "Transport"; the benchmark says "Transportation". An
        untranslated comparison would score every correct answer as wrong."""
        test = pd.DataFrame({"narration": ["UPI-UBER INDIA-9921", "UPI-SWIGGY-1"]})

        predicted = baselines.predict_bank_rules(test)

        assert list(predicted) == ["Transportation", "Food"]

    def test_every_rule_category_has_a_translation(self):
        """A missing entry would raise KeyError partway through scoring."""
        from expense_analyzer.categorize import CATEGORY_RULES, UNCATEGORIZED

        expected = set(CATEGORY_RULES) | {UNCATEGORIZED}
        assert expected == set(baselines.RULE_TO_BENCHMARK)

    def test_unmatched_narrations_fall_through_to_other(self):
        test = pd.DataFrame({"narration": ["fruits and vegetables"]})
        assert list(baselines.predict_bank_rules(test)) == [baselines.OTHER]


class TestPipeline:
    def test_learns_two_separable_classes(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)

        predicted = model.predict(pipeline, pd.DataFrame({"narration": ["dosa", "bus ticket"]}))

        assert list(predicted) == ["Food", "Transportation"]

    def test_character_ngrams_handle_a_spelling_never_seen_in_training(self, tiny_corpus):
        """The notes are one person's shorthand full of typos. Word n-grams
        alone would miss "rikshaw"; character n-grams match the fragments."""
        pipeline = model.train(tiny_corpus)

        predicted = model.predict(pipeline, pd.DataFrame({"narration": ["rikshaw fare"]}))

        assert list(predicted) == ["Transportation"]

    def test_predictions_keep_the_callers_index(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)
        frame = pd.DataFrame({"narration": ["dosa", "bus"]}, index=[17, 42])

        assert list(model.predict(pipeline, frame).index) == [17, 42]

    def test_balanced_and_unbalanced_pipelines_are_both_buildable(self):
        assert model.build_pipeline(balanced=True) is not None
        assert model.build_pipeline(balanced=False) is not None


class TestPersistence:
    def test_saves_and_reloads_to_the_same_predictions(self, tiny_corpus, tmp_path):
        pipeline = model.train(tiny_corpus)
        frame = pd.DataFrame({"narration": ["dosa", "petrol"]})
        before = list(model.predict(pipeline, frame))

        path = model.save(pipeline, tmp_path / "nested" / "m.joblib")
        after = list(model.predict(model.load(path), frame))

        assert path.exists()
        assert before == after

    def test_loading_a_missing_model_says_how_to_make_one(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Train one first"):
            model.load(tmp_path / "absent.joblib")


class TestExplainability:
    def test_top_features_name_words_a_human_would_expect(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)

        features = model.top_features_for(pipeline, "Transportation", top=40)
        words = " ".join(features["feature"])

        assert any(term in words for term in ("bus", "train", "cab", "petrol"))
        assert (features["weight"] > 0).all()

    def test_rejects_a_label_the_model_never_saw(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)

        with pytest.raises(ValueError, match="unknown label"):
            model.top_features_for(pipeline, "Nonexistent")


class TestConfidenceThresholding:
    def test_abstains_below_the_threshold_instead_of_guessing(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)
        frame = pd.DataFrame({"narration": ["dosa", "completely unrelated gibberish"]})

        # A threshold of 1.0 is unreachable, so everything must abstain.
        result = model.predict_with_confidence(pipeline, frame, threshold=1.0)

        assert set(result["prediction"]) == {model.UNCERTAIN}
        assert not result["answered"].any()

    def test_answers_everything_at_a_threshold_of_zero(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)
        frame = pd.DataFrame({"narration": ["dosa", "bus ticket"]})

        result = model.predict_with_confidence(pipeline, frame, threshold=0.0)

        assert result["answered"].all()
        assert model.UNCERTAIN not in set(result["prediction"])

    def test_confidence_is_a_probability_between_zero_and_one(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)
        result = model.predict_with_confidence(
            pipeline, pd.DataFrame({"narration": ["dosa", "petrol"]})
        )

        assert ((result["confidence"] >= 0) & (result["confidence"] <= 1)).all()

    def test_keeps_the_callers_index(self, tiny_corpus):
        pipeline = model.train(tiny_corpus)
        frame = pd.DataFrame({"narration": ["dosa"]}, index=[99])

        assert list(model.predict_with_confidence(pipeline, frame).index) == [99]
