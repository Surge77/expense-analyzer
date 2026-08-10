"""The baselines, and the split strategies that decide what a score means."""

import pandas as pd
import pytest

from expense_analyzer import baselines, benchmark


def frame(notes: list[str], labels: list[str] | None = None) -> pd.DataFrame:
    data = {"narration": notes}
    if labels is not None:
        data["label"] = labels
    return pd.DataFrame(data)


class TestNormaliseNote:
    @pytest.mark.parametrize(
        "left,right",
        [
            ("Grocery", "grocery"),
            ("fruits, and vegetables", "fruits and vegetables"),
            ("  Bus  Ticket ", "bus ticket"),
            ("Auto-rickshaw!", "auto rickshaw"),
        ],
    )
    def test_treats_case_and_punctuation_as_the_same_note(self, left, right):
        assert benchmark.normalise_note(left) == benchmark.normalise_note(right)

    def test_keeps_genuinely_different_notes_apart(self):
        assert benchmark.normalise_note("bus ticket") != benchmark.normalise_note("train ticket")


class TestHouseholdRules:
    @pytest.mark.parametrize(
        "note,expected",
        [
            ("Mutual fund A", "Investment"),
            ("mobile recharge", "subscription"),
            ("doctor consultation fees", "Health"),
            ("hair cut", "Beauty"),
            ("birthday gift for friend", "Gift"),
            ("ironing clothes", "Apparel"),
            ("2 Place 0 to Place 3", "Transportation"),
            ("From workplace", "Salary"),
            ("grocery for the week", "Household"),
            ("idli medu vada", "Food"),
        ],
    )
    def test_maps_training_vocabulary_to_the_right_class(self, note, expected):
        assert baselines.categorize_household(note) == expected

    def test_falls_through_to_other_rather_than_guessing(self):
        assert baselines.categorize_household("zzz unknowable zzz") == baselines.OTHER

    def test_matching_is_case_insensitive(self):
        assert baselines.categorize_household("DOCTOR FEES") == "Health"

    def test_has_no_rule_for_family(self):
        """Its training rows share no vocabulary — ipad, scratch guard, exam
        form. Any keyword broad enough to catch them costs precision
        elsewhere, so the class is deliberately left to the model."""
        assert "Family" not in baselines.HOUSEHOLD_RULES

    def test_salary_is_matched_before_transportation(self):
        """Transportation matches the bare substring "place", which also
        appears inside "workplace" — the only salary note in the data. Salary
        is declared first so it wins. Reordering fails silently, hence a test."""
        labels = list(baselines.HOUSEHOLD_RULES)

        assert labels.index("Salary") < labels.index("Transportation")
        assert baselines.categorize_household("From workplace") == "Salary"

    def test_specific_rules_are_tried_before_generic_ones(self):
        """`subscription` sits above `Household`, so "mobile recharge" is not
        swallowed by a generic bill keyword."""
        labels = list(baselines.HOUSEHOLD_RULES)
        assert labels.index("subscription") < labels.index("Household")


class TestPredictors:
    def test_majority_always_answers_the_commonest_training_class(self):
        train = pd.DataFrame({"label": ["Food"] * 8 + ["Health"] * 2})
        predicted = baselines.predict_majority(train, pd.DataFrame({"label": ["Health"] * 3}))

        assert set(predicted) == {"Food"}

    def test_bank_rules_are_translated_into_the_benchmark_vocabulary(self):
        """Rules say "Transport"; the benchmark says "Transportation". An
        untranslated comparison scores every correct answer as wrong."""
        predicted = baselines.predict_bank_rules(frame(["UPI-UBER INDIA-9921", "UPI-SWIGGY-1"]))

        assert list(predicted) == ["Transportation", "Food"]

    def test_every_bank_rule_category_has_a_translation(self):
        from expense_analyzer.categorize import CATEGORY_RULES, UNCATEGORIZED

        assert set(CATEGORY_RULES) | {UNCATEGORIZED} == set(baselines.RULE_TO_BENCHMARK)

    def test_hybrid_prefers_the_rule_and_falls_back_to_the_model(self):
        """The measured justification for the hybrid: rules keep working on
        unseen text, the model covers everything they do not reach."""
        train = pd.DataFrame(
            {
                "narration": ["idli dosa", "bus ticket"] * 8,
                "label": ["Food", "Transportation"] * 8,
            }
        )
        test = frame(["doctor consultation", "idli sambar"])

        predicted = baselines.predict_hybrid(train, test)

        # The rule fires for the first and wins outright.
        assert predicted.iloc[0] == "Health"
        # No rule reaches the second in a way the model cannot, so it is covered.
        assert predicted.iloc[1] in {"Food", "Transportation"}


class TestSplitStrategies:
    def test_rejects_an_unknown_strategy_and_names_the_options(self):
        with pytest.raises(ValueError, match="random, grouped, temporal"):
            benchmark.load_benchmark(strategy="sideways")  # type: ignore[arg-type]

    def test_collapse_folds_classes_below_the_threshold(self):
        labels = pd.Series(["Food"] * 25 + ["Interest"] * 3)
        collapsed = benchmark.collapse_rare_classes(labels, minimum=20)

        assert set(collapsed) == {"Food", benchmark.OTHER}

    def test_collapse_leaves_classes_at_the_threshold_alone(self):
        assert set(benchmark.collapse_rare_classes(pd.Series(["Food"] * 20), 20)) == {"Food"}


@pytest.fixture
def labelled() -> pd.DataFrame:
    """A synthetic labelled frame with deliberate duplicate notes.

    "grocery" appears four times, which is what makes the random and grouped
    splits behave differently — the whole point of having both.
    """
    notes = ["grocery"] * 4 + ["bus ticket"] * 4 + ["doctor"] * 4 + ["idli"] * 4
    labels = ["Household"] * 4 + ["Transportation"] * 4 + ["Health"] * 4 + ["Food"] * 4
    frame = pd.DataFrame({"narration": notes, "label": labels})
    frame["date"] = pd.date_range("2026-01-01", periods=len(frame), freq="D")
    return frame


class TestSplitMechanics:
    def test_random_split_keeps_every_row(self, labelled):
        train, test = benchmark._split_random(labelled, test_size=0.25, seed=42)
        assert len(train) + len(test) == len(labelled)

    def test_grouped_split_never_puts_the_same_note_on_both_sides(self, labelled):
        """The property the whole grouped strategy exists to guarantee."""
        train, test = benchmark._split_grouped(labelled, seed=42)

        train_notes = {benchmark.normalise_note(n) for n in train["narration"]}
        test_notes = {benchmark.normalise_note(n) for n in test["narration"]}

        assert not (train_notes & test_notes)
        assert len(train) + len(test) == len(labelled)

    def test_temporal_split_trains_on_the_past_only(self, labelled):
        train, test = benchmark._split_temporal(labelled, test_size=0.25)

        assert train["date"].max() <= test["date"].min()
        assert len(train) + len(test) == len(labelled)

    def test_seen_in_train_is_empty_for_a_grouped_split(self, labelled):
        train, test = benchmark._split_grouped(labelled, seed=42)
        bench = benchmark.Benchmark(
            train=train.reset_index(drop=True),
            test=test.reset_index(drop=True),
            classes=sorted(labelled["label"].unique()),
            strategy="grouped",
            dropped_without_note=0,
            collapsed_to_other=0,
        )

        assert bench.seen_in_train.sum() == 0
        assert "0.0% of test notes" in bench.summary()

    def test_seen_in_train_detects_overlap(self, labelled):
        bench = benchmark.Benchmark(
            train=labelled,
            test=labelled.head(4),
            classes=["Household"],
            strategy="random",
            dropped_without_note=0,
            collapsed_to_other=0,
        )
        assert bench.seen_in_train.all()


class TestCompareAll:
    def test_scores_every_approach_on_the_same_test_set(self, labelled):
        bench = benchmark.Benchmark(
            train=labelled,
            test=labelled.copy(),
            classes=sorted(labelled["label"].unique()),
            strategy="random",
            dropped_without_note=0,
            collapsed_to_other=0,
        )

        scores, predictions = baselines.compare_all(bench)

        names = [item.name for item in scores]
        assert names == [
            "majority class",
            "bank rules (out of domain)",
            "in-domain rules",
            "TF-IDF + LogReg",
            "hybrid (rules, then model)",
        ]
        assert all(item.n == len(bench.test) for item in scores)
        assert len(predictions) == len(bench.test)
