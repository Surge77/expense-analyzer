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
