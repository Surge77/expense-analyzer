"""The cleaning stage is where silent, un-crashing bugs live."""

import pandas as pd
import pytest

from src.clean import clean_statement, parse_amount


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


def test_drops_footer_rows_without_a_date(raw_statement):
    cleaned = clean_statement(raw_statement)
    assert len(cleaned) == 3
    assert not cleaned["narration"].str.contains("computer generated").any()


def test_spending_is_negative_and_income_is_positive(raw_statement):
    cleaned = clean_statement(raw_statement)
    amounts = dict(zip(cleaned["narration"].str[4:10], cleaned["amount"]))
    assert amounts["SWIGGY"] == -347.00
    assert cleaned.loc[cleaned["amount"] > 0, "amount"].iloc[0] == 32000.00


def test_derives_weekend_flag_from_date(raw_statement):
    cleaned = clean_statement(raw_statement)
    # 5 July 2026 is a Sunday.
    assert cleaned["day_name"].iloc[0] == "Sunday"
    assert bool(cleaned["is_weekend"].iloc[0]) is True
