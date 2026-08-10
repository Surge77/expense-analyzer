"""The cleaning stage is where silent, un-crashing bugs live."""

import pandas as pd
import pytest

from expense_analyzer.clean import clean_statement, load_and_clean, parse_amount, parse_dates


@pytest.fixture
def raw_statement() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": ["05/07/26", "06/07/26", "07/07/26", ""],
            "Narration": [
                "UPI-SWIGGY-swiggy@icici-512334",
                "NEFT-ACME SOFTWARE PVT LTD-SALARY CREDIT",
                "UPI-DMART READY-dmart@hdfcbank-901221",
                "*** This is a computer generated statement. ***",
            ],
            "Withdrawal Amt.": ["347.00", "", "1,240.50", ""],
            "Deposit Amt.": ["", "32,000.00", "", ""],
        }
    )


def test_parses_thousands_separator_as_number():
    parsed = parse_amount(pd.Series(["1,347.00", "12,00,500.25"]))
    assert parsed.tolist() == [1347.00, 1200500.25]


def test_treats_blank_amount_as_zero():
    parsed = parse_amount(pd.Series(["", None, "-"]))
    assert parsed.tolist() == [0.0, 0.0, 0.0]


def test_reads_dates_day_first_not_month_first(raw_statement):
    cleaned = clean_statement(raw_statement)
    first = cleaned["date"].iloc[0]
    assert (first.day, first.month) == (5, 7), "05/07 must be 5 July, not 7 May"


def test_load_and_clean_reads_a_file_and_tidies_it_in_one_call(tmp_path):
    path = tmp_path / "statement.csv"
    path.write_text(
        "Date,Narration,Withdrawal Amt.,Deposit Amt.\n05/07/26,UPI-SWIGGY-1,347.00,\n",
        encoding="utf-8",
    )

    tidy = load_and_clean(path)

    assert len(tidy) == 1
    assert tidy["amount"].iloc[0] == -347.00
    assert tidy["day_name"].iloc[0] == "Sunday"


def test_falls_back_to_the_general_parser_for_formats_not_in_the_list():
    """The 116k-row real bank export stores dates as `2017-06-29 00:00:00`,
    which none of DATE_FORMATS matches because of the time component. Every
    explicit format scores zero, so the mixed parser must win."""
    parsed = parse_dates(pd.Series(["2017-06-29 00:00:00", "2017-07-05 00:00:00"]))

    assert not parsed.isna().any()
    assert (parsed.iloc[0].year, parsed.iloc[0].month, parsed.iloc[0].day) == (2017, 6, 29)


def test_unparseable_dates_become_nat_rather_than_raising():
    parsed = parse_dates(pd.Series(["not a date", "31/02/26"]))
    assert parsed.isna().all()


def test_drops_footer_rows_without_a_date(raw_statement):
    cleaned = clean_statement(raw_statement)
    assert len(cleaned) == 3
    assert not cleaned["narration"].str.contains("computer generated").any()


def test_spending_is_negative_and_income_is_positive(raw_statement):
    cleaned = clean_statement(raw_statement)
    amounts = dict(zip(cleaned["narration"].str[4:10], cleaned["amount"], strict=True))
    assert amounts["SWIGGY"] == -347.00
    assert cleaned.loc[cleaned["amount"] > 0, "amount"].iloc[0] == 32000.00


def test_derives_weekend_flag_from_date(raw_statement):
    cleaned = clean_statement(raw_statement)
    # 5 July 2026 is a Sunday.
    assert cleaned["day_name"].iloc[0] == "Sunday"
    assert bool(cleaned["is_weekend"].iloc[0]) is True
