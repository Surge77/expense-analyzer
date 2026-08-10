"""Property-based tests for the parsing functions.

`clean.py` is where "silent, un-crashing bugs" live — the module docstring
says so. Example-based tests only check the cases somebody thought of.
Hypothesis generates the ones nobody did, which is the right tool for
functions whose failure mode is a plausible wrong number rather than an
exception.

Each test states an invariant that must hold for *every* input, not an
expected output for one.
"""

import pandas as pd
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from expense_analyzer.benchmark import normalise_note
from expense_analyzer.categorize import categorize, merchant_key
from expense_analyzer.clean import parse_amount, parse_dates

# Deadlines off: constructing a pandas Series dominates the runtime and varies
# enough between runs to make a per-example deadline flaky.
SETTINGS = settings(max_examples=200, deadline=None)


class TestParseAmount:
    @SETTINGS
    @given(st.floats(min_value=-1e12, max_value=1e12, allow_nan=False, allow_infinity=False))
    def test_round_trips_any_plain_number(self, value):
        formatted = f"{value:.2f}"
        parsed = parse_amount(pd.Series([formatted]))

        assert parsed.iloc[0] == float(formatted)

    @SETTINGS
    @given(st.integers(min_value=0, max_value=10**12))
    def test_thousands_separators_never_change_the_value(self, value):
        """`1,347.00` and `1347.00` must parse identically — the separator is
        presentation, and treating it as data silently divides by a thousand."""
        with_commas = f"{value:,}"
        without = str(value)

        assert parse_amount(pd.Series([with_commas])).iloc[0] == float(without)

    @SETTINGS
    @given(st.sampled_from(["", " ", "-", "nan", None]))
    def test_every_kind_of_blank_becomes_zero(self, blank):
        """A blank means the transaction went the other way, which is zero on
        this side. Anything else would propagate NaN into every total."""
        assert parse_amount(pd.Series([blank])).iloc[0] == 0.0

    @SETTINGS
    @given(st.lists(st.integers(min_value=0, max_value=10**9), min_size=1, max_size=30))
    def test_output_length_always_matches_input_length(self, values):
        series = pd.Series([f"{value:,}" for value in values])
        assert len(parse_amount(series)) == len(series)


class TestParseDates:
    @SETTINGS
    @given(
        st.dates(
            min_value=pd.Timestamp("1990-01-01").date(),
            max_value=pd.Timestamp("2050-12-31").date(),
        )
    )
    def test_day_first_format_round_trips(self, day):
        """`05/07/26` is 5 July in India and 7 May to pandas' default parser.
        Getting this wrong produces wrong monthly totals and no error."""
        parsed = parse_dates(pd.Series([day.strftime("%d/%m/%Y")]))

        assert parsed.iloc[0].date() == day

    @SETTINGS
    @given(st.text(max_size=20))
    def test_unparseable_text_never_raises(self, text):
        """Statement footers and junk rows go through this. Coercing to NaT
        lets them be dropped; raising would take the whole file down."""
        assume(not text.strip().isdigit())
        result = parse_dates(pd.Series([text]))

        assert len(result) == 1

    @SETTINGS
    @given(st.lists(st.text(max_size=12), min_size=1, max_size=20))
    def test_output_length_always_matches_input_length(self, values):
        assert len(parse_dates(pd.Series(values))) == len(values)


class TestCategorize:
    @SETTINGS
    @given(st.text(max_size=60))
    def test_always_returns_a_known_category(self, text):
        from expense_analyzer.categorize import CATEGORY_RULES, UNCATEGORIZED

        assert categorize(text) in set(CATEGORY_RULES) | {UNCATEGORIZED}

    @SETTINGS
    @given(st.text(max_size=60))
    def test_is_case_insensitive_for_every_input(self, text):
        assert categorize(text.lower()) == categorize(text.upper())

    @SETTINGS
    @given(st.text(max_size=60), st.integers(min_value=1000, max_value=10**9))
    def test_a_reference_number_never_changes_the_category(self, text, reference):
        """Every transaction carries a unique reference. If it could change
        the category, no rule would be stable."""
        assert categorize(text) == categorize(f"{text}-{reference}")


class TestMerchantKey:
    @SETTINGS
    @given(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
            min_size=1,
            max_size=20,
        )
    )
    def test_same_merchant_with_different_references_collapses_to_one_key(self, merchant):
        """This is what makes `recurring_candidates` able to group at all."""
        first = merchant_key(f"UPI-{merchant}-123456")
        second = merchant_key(f"UPI-{merchant}-987654")

        assert first == second

    @SETTINGS
    @given(st.text(max_size=40))
    def test_is_idempotent(self, text):
        once = merchant_key(text)
        assert merchant_key(once) == once


class TestNormaliseNote:
    @SETTINGS
    @given(st.text(max_size=40))
    def test_is_idempotent(self, text):
        """Grouping depends on this: normalising twice must not drift, or
        identical notes could land on both sides of a grouped split."""
        once = normalise_note(text)
        assert normalise_note(once) == once

    @SETTINGS
    @given(st.text(max_size=40))
    def test_never_returns_leading_or_trailing_space(self, text):
        result = normalise_note(text)
        assert result == result.strip()
