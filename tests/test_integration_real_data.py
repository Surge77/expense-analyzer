"""Tests that download and parse the real public datasets.

Marked `integration` and deselected by default, because they hit the network
and read ~6 MB of Excel. Run them explicitly:

    pytest -m integration

These exist because 180 synthetic rows cannot exercise what a real export
does to a parser. Every assertion here corresponds to something that was
actually wrong or surprising in the data.
"""

import pytest

from expense_analyzer import analyze, categorize
from expense_analyzer.clean import clean_statement
from expense_analyzer.data import load_raw

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def bank():
    raw, schema = load_raw("bank")
    return raw, clean_statement(raw, schema)


@pytest.fixture(scope="module")
def household():
    raw, schema = load_raw("household")
    return raw, clean_statement(raw, schema)


class TestRealBankExport:
    def test_parses_every_row_without_losing_one(self, bank):
        raw, tidy = bank

        assert len(raw) == 116_201
        assert len(tidy) == 116_201, "a dropped row means a date or amount failed to parse"

    def test_no_date_falls_through_as_not_a_time(self, bank):
        """Dates arrive as `2017-06-29 00:00:00`, which matches none of
        DATE_FORMATS. The mixed-parser fallback has to catch them."""
        _, tidy = bank

        assert not tidy["date"].isna().any()
        assert tidy["date"].min().year == 2015
        assert tidy["date"].max().year == 2019

    def test_account_numbers_lose_the_stray_quote(self, bank):
        _, tidy = bank

        assert len(analyze.accounts(tidy)) == 10
        assert not tidy["account"].str.contains("'").any()

    def test_aggregations_survive_seven_orders_of_magnitude(self, bank):
        """Amounts run from rupees to hundreds of millions in one column."""
        _, tidy = bank
        one = analyze.for_account(tidy, analyze.accounts(tidy)[0])
        spend = analyze.spending_only(categorize.add_categories(one))

        assert analyze.by_category(spend).notna().all()
        assert analyze.monthly_totals(spend).notna().all()

    def test_the_transfer_rule_catches_the_truncated_narration(self, bank):
        """The most common narration is "FDRL/INTERNAL FUND TRANSFE" — the
        bank truncates mid-word, so the rule matches the stem."""
        _, tidy = bank
        labelled = categorize.add_categories(tidy)

        assert (labelled["category"] == "Transfer").sum() > 10_000


class TestRealHouseholdExport:
    def test_parses_every_row_and_keeps_the_labels(self, household):
        raw, tidy = household

        assert len(raw) == 2_461
        assert len(tidy) == 2_461
        assert tidy["label"].nunique() == 50

    def test_direction_flag_signs_the_amounts(self, household):
        _, tidy = household

        assert (tidy["amount"] < 0).sum() > 2_000, "most rows are expenses"
        assert (tidy["amount"] > 0).sum() > 100, "some rows are income"

    def test_a_fifth_of_notes_are_empty(self, household):
        """521 of 2,461 rows carry no note. They cannot be classified from
        text, so the Phase 4 benchmark has to exclude them and say so."""
        _, tidy = household

        assert (tidy["narration"] == "").sum() == pytest.approx(521, abs=5)


class TestBenchmarkAndModel:
    """The numbers quoted in docs/results.md and the README.

    Pinned loosely — a few points either way is noise on 485 test rows — but
    tight enough that a real regression in the pipeline shows up here.
    """

    @staticmethod
    def _bench():
        from expense_analyzer import benchmark

        return benchmark.load_benchmark()

    def test_benchmark_shape_matches_what_the_docs_claim(self):
        bench = self._bench()

        assert bench.total == 1_940
        assert bench.dropped_without_note == 521
        assert len(bench.classes) == 12
        assert len(bench.test) == 485

    def test_rules_score_below_the_majority_baseline(self):
        """The headline finding: rules built for bank narrations do not
        transfer to a human's shorthand."""
        from expense_analyzer import baselines, evaluate

        bench = self._bench()
        truth = bench.test["label"]
        majority_guess = baselines.predict_majority(bench.train, bench.test)
        majority = evaluate.score("majority", truth, majority_guess)
        rules = evaluate.score("rules", truth, baselines.predict_bank_rules(bench.test))

        assert majority.accuracy == pytest.approx(0.429, abs=0.02)
        assert rules.accuracy < majority.accuracy
        assert rules.accuracy == pytest.approx(0.134, abs=0.03)

    def test_classifier_clearly_beats_both_baselines(self):
        from expense_analyzer import baselines

        bench = self._bench()
        scores, _ = baselines.compare_all(bench)
        by_name = {item.name: item for item in scores}

        model_score = by_name["TF-IDF + LogReg"]
        assert model_score.accuracy > 0.80
        assert model_score.macro_f1 > 0.70
        assert model_score.accuracy > by_name["majority class"].accuracy
        assert model_score.macro_f1 > by_name["bank rules (out of domain)"].macro_f1

    def test_model_leans_on_words_a_human_would_expect(self):
        """A model relying on something absurd has memorised a quirk."""
        from expense_analyzer import model

        bench = self._bench()
        pipeline = model.train(bench.train)
        words = " ".join(model.top_features_for(pipeline, "Transportation", top=60)["feature"])

        assert any(term in words for term in ("bus", "train", "petrol", "rickshaw", "place"))


class TestSplitStrategiesOnRealData:
    """The three splits answer different questions and give different
    numbers. These pin the relationships, loosely — a few points is noise —
    but tightly enough that a regression in the split logic shows up."""

    def test_random_split_has_substantial_note_overlap(self):
        from expense_analyzer import benchmark

        bench = benchmark.load_benchmark(strategy="random")
        assert bench.seen_in_train.mean() == pytest.approx(0.567, abs=0.05)

    def test_grouped_split_has_no_note_overlap_at_all(self):
        """The guarantee the grouped strategy exists to provide."""
        from expense_analyzer import benchmark

        bench = benchmark.load_benchmark(strategy="grouped")
        assert bench.seen_in_train.sum() == 0

    def test_temporal_split_trains_only_on_earlier_transactions(self):
        from expense_analyzer import benchmark

        bench = benchmark.load_benchmark(strategy="temporal")
        assert bench.train["date"].max() <= bench.test["date"].min()

    def test_generalisation_score_is_lower_than_the_headline(self):
        """The finding that matters: the random-split score is inflated by
        notes the model has already seen."""
        from expense_analyzer import baselines, benchmark

        random_scores, _ = baselines.compare_all(benchmark.load_benchmark(strategy="random"))
        grouped_scores, _ = baselines.compare_all(benchmark.load_benchmark(strategy="grouped"))

        random_model = next(s for s in random_scores if s.name == "TF-IDF + LogReg")
        grouped_model = next(s for s in grouped_scores if s.name == "TF-IDF + LogReg")

        assert grouped_model.accuracy < random_model.accuracy - 0.05

    def test_in_domain_rules_beat_the_ported_bank_rules_by_a_wide_margin(self):
        """Separates "a model beats rules" from "in-domain beats out-of-domain"."""
        from expense_analyzer import baselines, benchmark

        scores, _ = baselines.compare_all(benchmark.load_benchmark(strategy="grouped"))
        by_name = {s.name: s for s in scores}

        in_domain = by_name["in-domain rules"].accuracy
        ported = by_name["bank rules (out of domain)"].accuracy
        assert in_domain > ported * 3

    def test_hybrid_beats_the_model_on_genuinely_unseen_text(self):
        """The measured justification for recommending the hybrid at all."""
        from expense_analyzer import baselines, benchmark

        scores, _ = baselines.compare_all(benchmark.load_benchmark(strategy="grouped"))
        by_name = {s.name: s for s in scores}

        assert by_name["hybrid (rules, then model)"].macro_f1 > by_name["TF-IDF + LogReg"].macro_f1
