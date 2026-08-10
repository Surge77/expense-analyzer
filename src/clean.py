"""Stage 1 — load a raw bank statement and make it analysable.

Everything a bank CSV gets wrong is fixed here, and nowhere else. Later
stages assume clean input.
"""

from pathlib import Path

import pandas as pd

RAW_DATE = "Date"
RAW_NARRATION = "Narration"
RAW_WITHDRAWAL = "Withdrawal Amt."
RAW_DEPOSIT = "Deposit Amt."

# Indian statements print dates as dd/mm/yy. Parsing them as month-first
# silently turns 05/07 into 5 May instead of 5 July: wrong totals, no error.
DAY_FIRST = True

# Tried in order. Naming the format keeps every row on the same rule; without
# one, pandas falls back to dateutil per element and can read two rows in the
# same column differently.
DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d")


def load_statement(path: str | Path) -> pd.DataFrame:
    """Read the CSV exactly as the bank exported it, with no coercion."""
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [column.strip() for column in frame.columns]
    return frame


def parse_amount(series: pd.Series) -> pd.Series:
    """Turn '1,347.00' and blank cells into floats.

    Banks thousands-separate amounts, so the column arrives as text. A blank
    means the transaction was the other direction, which is a zero here.
    """
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .replace({"": "0", "nan": "0", "-": "0"})
        .astype(float)
    )


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse a date column with an explicit format where one fits.

    Picks whichever known format parses the most rows. Falls back to the
    day-first guesser only if no format fits, which keeps unusual exports
    working instead of failing outright.
    """
    best = pd.to_datetime(series, dayfirst=DAY_FIRST, errors="coerce", format="mixed")

    for date_format in DATE_FORMATS:
        parsed = pd.to_datetime(series, format=date_format, errors="coerce")
        if parsed.notna().sum() >= best.notna().sum():
            return parsed

    return best


def clean_statement(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one tidy row per transaction.

    Output columns: date, month, day_name, is_weekend, narration, amount.
    `amount` is signed — spending negative, income positive — so a single
    sum answers "what is my net position".
    """
    frame = frame.copy()

    # Statement footers ("computer generated statement") have no parseable
    # date. Coercing to NaT and dropping removes them without a special case.
    frame["date"] = parse_dates(frame[RAW_DATE])
    frame = frame.dropna(subset=["date"])

    withdrawal = parse_amount(frame[RAW_WITHDRAWAL])
    deposit = parse_amount(frame[RAW_DEPOSIT])

    tidy = pd.DataFrame(
        {
            "date": frame["date"],
            "narration": frame[RAW_NARRATION].fillna("").str.strip(),
            "amount": deposit - withdrawal,
        }
    )

    tidy = tidy[tidy["amount"] != 0]
    tidy["month"] = tidy["date"].dt.to_period("M")
    tidy["day_name"] = tidy["date"].dt.day_name()
    tidy["is_weekend"] = tidy["date"].dt.dayofweek >= 5

    ordered = ["date", "month", "day_name", "is_weekend", "narration", "amount"]
    return tidy[ordered].sort_values("date").reset_index(drop=True)


def load_and_clean(path: str | Path) -> pd.DataFrame:
    """Convenience wrapper for the two steps above."""
    return clean_statement(load_statement(path))
