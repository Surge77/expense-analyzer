"""The aggregation stage. Every number here ends up in a finding, so a
silent arithmetic change is a wrong conclusion, not a crash.
"""

import pandas as pd
import pytest

from expense_analyzer import analyze


class TestSpendingOnly:
    def test_keeps_outgoing_rows_and_makes_them_positive(self, categorized):
        spend = analyze.spending_only(categorized)

        assert len(spend) == 6, "the single income row must be dropped"
        assert (spend["amount"] > 0).all(), "spending is flipped positive for readable charts"
        assert spend["amount"].sum() == 2500.0

    def test_excludes_transfers_because_they_are_not_spending(self, frame_factory):
        """Moving money between your own accounts double-counts everything
        downstream if it is treated as spend."""
        frame = frame_factory(
            [
                ("2026-01-05", "UPI-SWIGGY-order", -100.0, "Food"),
                ("2026-01-06", "TRF TO SELF SAVINGS", -900.0, "Transfer"),
            ]
        )
        spend = analyze.spending_only(frame)

        assert spend["amount"].sum() == 100.0
        assert "Transfer" not in spend["category"].to_numpy()

    def test_does_not_mutate_the_caller_frame(self, categorized):
        before = categorized["amount"].tolist()
        analyze.spending_only(categorized)
        assert categorized["amount"].tolist() == before


class TestAggregations:
    def test_by_category_totals_biggest_first(self, categorized):
        totals = analyze.by_category(analyze.spending_only(categorized))

        assert totals.index.tolist() == ["Rent", "Groceries", "Food"]
        assert totals["Food"] == 600.0
        assert totals["Groceries"] == 900.0

    def test_monthly_totals_are_chronological(self, categorized):
        totals = analyze.monthly_totals(analyze.spending_only(categorized))

        assert [str(period) for period in totals.index] == ["2026-01", "2026-02"]
        assert totals.iloc[0] == 1700.0  # 100 + 200 + 400 + 1000
        assert totals.iloc[1] == 800.0  # 300 + 500

    def test_category_by_month_fills_absent_combinations_with_zero(self, categorized):
        pivot = analyze.category_by_month(analyze.spending_only(categorized))

        # `.at` returns the scalar; `.loc` is typed as possibly returning a
        # Series, which makes the comparison ambiguous to a type checker.
        assert pivot.at[pivot.index[1], "Rent"] == 0.0, "no rent in February"
        assert pivot.at[pivot.index[0], "Rent"] == 1000.0

    def test_weekday_split_returns_all_seven_days_in_order(self, categorized):
        split = analyze.weekday_split(analyze.spending_only(categorized))

        assert split.index.tolist() == [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        # 10 Jan and 7 Feb 2026 are both Saturdays: 200 + 300.
        assert split["Saturday"] == 500.0
        assert split["Tuesday"] == 0.0, "absent days are zero, not missing"

    def test_top_transactions_returns_largest_outflows(self, categorized):
        top = analyze.top_transactions(analyze.spending_only(categorized), top=2)

        assert top["amount"].tolist() == [1000.0, 500.0]
        assert list(top.columns) == ["date", "narration", "category", "amount"]


class TestSavingsRate:
    def test_computes_fraction_of_income_not_spent(self, categorized):
        assert analyze.savings_rate(categorized) == 0.5

    def test_returns_zero_when_there_is_no_income(self, frame_factory):
        """Guards a division by zero. A statement of pure spending is a real
        case — a credit card export has no salary line."""
        frame = frame_factory([("2026-01-05", "UPI-SWIGGY", -100.0, "Food")])
        assert analyze.savings_rate(frame) == 0.0

    def test_is_negative_when_spending_exceeds_income(self, frame_factory):
        frame = frame_factory(
            [
                ("2026-01-01", "NEFT-SALARY", 100.0, "Income"),
                ("2026-01-05", "UPI-SWIGGY", -150.0, "Food"),
            ]
        )
        assert analyze.savings_rate(frame) == -0.5


class TestRecurringCandidates:
    def test_flags_a_charge_repeating_monthly_at_a_stable_price(self, frame_factory):
        frame = frame_factory(
            [
                ("2026-01-04", "UPI-NETFLIX-AUTOPAY-111111", -649.0, "Subscriptions"),
                ("2026-02-04", "UPI-NETFLIX-AUTOPAY-222222", -649.0, "Subscriptions"),
                ("2026-03-04", "UPI-NETFLIX-AUTOPAY-333333", -649.0, "Subscriptions"),
            ]
        )
        recurring = analyze.recurring_candidates(analyze.spending_only(frame))

        assert len(recurring) == 1, "reference numbers differ; the merchant is one"
        assert recurring["months"].iloc[0] == 3
        assert recurring["annual_cost"].iloc[0] == pytest.approx(649.0 * 12)

    def test_ignores_a_charge_whose_amount_moves_too_much(self, frame_factory):
        """Groceries recur monthly but at a different price every time, which
        is what separates a subscription from a habit."""
        frame = frame_factory(
            [
                ("2026-01-04", "UPI-DMART-111111", -500.0, "Groceries"),
                ("2026-02-04", "UPI-DMART-222222", -900.0, "Groceries"),
            ]
        )
        assert analyze.recurring_candidates(analyze.spending_only(frame)).empty

    def test_ignores_a_charge_seen_in_only_one_month(self, frame_factory):
        frame = frame_factory(
            [
                ("2026-01-04", "UPI-NETFLIX-AUTOPAY-111111", -649.0, "Subscriptions"),
                ("2026-01-20", "UPI-NETFLIX-AUTOPAY-222222", -649.0, "Subscriptions"),
            ]
        )
        assert analyze.recurring_candidates(analyze.spending_only(frame)).empty


class TestAnomalies:
    def test_flags_a_transaction_far_above_its_category_median(self, frame_factory):
        frame = frame_factory(
            [
                ("2026-01-01", "UPI-SWIGGY-a", -100.0, "Food"),
                ("2026-01-02", "UPI-SWIGGY-b", -100.0, "Food"),
                ("2026-01-03", "UPI-SWIGGY-c", -100.0, "Food"),
                ("2026-01-04", "UPI-BIG DINNER", -500.0, "Food"),
            ]
        )
        flagged = analyze.anomalies(analyze.spending_only(frame))

        assert len(flagged) == 1
        assert flagged["amount"].iloc[0] == 500.0
        assert flagged["category_median"].iloc[0] == 100.0
        assert flagged["times_median"].iloc[0] == 5.0

    def test_compares_within_a_category_not_across_the_statement(self, frame_factory):
        """Rent is 10x a typical meal but is entirely normal for rent. A
        global threshold would flag it every month and teach you nothing."""
        frame = frame_factory(
            [
                ("2026-01-01", "UPI-SWIGGY-a", -100.0, "Food"),
                ("2026-01-02", "UPI-SWIGGY-b", -100.0, "Food"),
                ("2026-01-03", "HOUSE RENT", -1000.0, "Rent"),
            ]
        )
        assert analyze.anomalies(analyze.spending_only(frame)).empty

    def test_returns_empty_frame_rather_than_raising_when_nothing_is_odd(self, categorized):
        flagged = analyze.anomalies(analyze.spending_only(categorized))
        assert isinstance(flagged, pd.DataFrame)
