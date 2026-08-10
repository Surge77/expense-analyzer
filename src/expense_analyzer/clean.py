"""Stage 1 — load a raw bank statement and make it analysable.

Everything a bank CSV gets wrong is fixed here, and nowhere else. Later
stages assume clean input.
"""

from pathlib import Path

import pandas as pd

from .data.loaders import read_file
from .data.schemas import HDFC_SAMPLE, StatementSchema

# Indian statements print dates as dd/mm/yy. Parsing them as month-first
# silently turns 05/07 into 5 May instead of 5 July: wrong totals, no error.
DAY_FIRST = True

# Tried in order. Naming the format keeps every row on the same rule; without
# one, pandas falls back to dateutil per element and can read two rows in the
# same column differently.
DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d")


def load_statement(path: str | Path) -> pd.DataFrame:
    """Read a statement file exactly as exported, with no type coercion.

    Delegates to `data.loaders.read_file`, which also handles the Excel
    exports. Kept as a name here because it reads better at a call site that
    is about cleaning, and because the notebook and README use it.
    """
    return read_file(Path(path))


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


def parse_dates(series: pd.Series, dayfirst: bool = DAY_FIRST) -> pd.Series:
    """Parse a date column with an explicit format where one fits.

    Picks whichever known format parses the most rows. Falls back to the
    day-first guesser only if no format fits, which keeps unusual exports
    working instead of failing outright.
    """
    best = pd.to_datetime(series, dayfirst=dayfirst, errors="coerce", format="mixed")

    for date_format in DATE_FORMATS:
        parsed = pd.to_datetime(series, format=date_format, errors="coerce")
        if parsed.notna().sum() >= best.notna().sum():
            return parsed

    return best


def signed_amounts(frame: pd.DataFrame, schema: StatementSchema) -> pd.Series:
    """Collapse a source's amount columns into one signed column.

    Spending is negative and income positive, so a single `.sum()` answers
    "what is my net position" without the caller tracking direction.
    """
    if schema.is_paired:
        withdrawal = parse_amount(frame[schema.withdrawal])
        deposit = parse_amount(frame[schema.deposit])
        return deposit - withdrawal

    # Signed shape: one magnitude column plus a flag naming the direction.
    # The flag is authoritative — the magnitude is always positive.
    magnitude = parse_amount(frame[schema.amount]).abs()
    is_expense = frame[schema.direction].isin(schema.expense_values)
    return magnitude.where(~is_expense, -magnitude)


def clean_statement(
    frame: pd.DataFrame,
    schema: StatementSchema = HDFC_SAMPLE,
) -> pd.DataFrame:
    """Return one tidy row per transaction.

    Output columns: date, month, day_name, is_weekend, narration, amount,
    plus `account` and `label` when the source carries them.
    """
    frame = frame.copy()

    # Statement footers ("computer generated statement") have no parseable
    # date. Coercing to NaT and dropping removes them without a special case.
    frame["date"] = parse_dates(frame[schema.date], dayfirst=schema.dayfirst)
    frame = frame.dropna(subset=["date"])

    tidy = pd.DataFrame(
        {
            "date": frame["date"],
            "narration": frame[schema.narration].fillna("").astype(str).str.strip(),
            "amount": signed_amounts(frame, schema),
        }
    )

    # An account number arrives as text and sometimes carries a stray quote,
    # e.g. "409000611074'" in the real bank export — an artefact of Excel
    # forcing the value to stay a string.
    if schema.account is not None:
        tidy["account"] = frame[schema.account].fillna("").astype(str).str.strip(" '\"")
    if schema.label is not None:
        tidy["label"] = frame[schema.label].fillna("").astype(str).str.strip()

    tidy = tidy[tidy["amount"] != 0]
    tidy["month"] = tidy["date"].dt.to_period("M")
    tidy["day_name"] = tidy["date"].dt.day_name()
    tidy["is_weekend"] = tidy["date"].dt.dayofweek >= 5

    ordered = ["date", "month", "day_name", "is_weekend", "narration", "amount"]
    ordered += [column for column in ("account", "label") if column in tidy.columns]
    return tidy[ordered].sort_values("date").reset_index(drop=True)


def load_and_clean(
    path: str | Path,
    schema: StatementSchema = HDFC_SAMPLE,
) -> pd.DataFrame:
    """Convenience wrapper for the two steps above."""
    return clean_statement(load_statement(path), schema)
