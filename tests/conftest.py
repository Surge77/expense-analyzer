"""Shared fixtures.

Every fixture builds a frame with numbers that can be checked by hand, so a
failing assertion points at the bug rather than at arithmetic nobody can
follow. Prefer the factory over hard-coded frames when a test needs a shape
the defaults do not cover.
"""

import pandas as pd
import pytest

TIDY_COLUMNS = ["date", "month", "day_name", "is_weekend", "narration", "amount", "category"]


def build_frame(rows: list[tuple[str, str, float, str]]) -> pd.DataFrame:
    """Build a categorized frame from `(date, narration, amount, category)`.

    `amount` follows the pipeline's sign convention: negative is spending,
    positive is income. The derived columns are computed the same way
    `clean.clean_statement` computes them, so aggregations behave identically.
    """
    frame = pd.DataFrame(rows, columns=["date", "narration", "amount", "category"])
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    frame["month"] = frame["date"].dt.to_period("M")
    frame["day_name"] = frame["date"].dt.day_name()
    frame["is_weekend"] = frame["date"].dt.dayofweek >= 5
    return frame[TIDY_COLUMNS]


@pytest.fixture
def frame_factory():
    """Expose `build_frame` to tests that need a custom shape."""
    return build_frame


@pytest.fixture
def categorized() -> pd.DataFrame:
    """Two months of spending plus one salary credit.

    Hand-checkable totals:
        Food       100 + 200 + 300 = 600
        Groceries  400 + 500       = 900
        Rent       1000            = 1000
        spend total              = 2500
        income                   = 5000
        savings rate = (5000 - 2500) / 5000 = 0.5
    """
    return build_frame(
        [
            # 2026-01-05 is a Monday, 2026-01-10 a Saturday.
            ("2026-01-05", "UPI-SWIGGY-order-1", -100.0, "Food"),
            ("2026-01-10", "UPI-SWIGGY-order-2", -200.0, "Food"),
            ("2026-01-05", "UPI-DMART-1", -400.0, "Groceries"),
            ("2026-01-01", "UPI-SANDEEP-HOUSE RENT", -1000.0, "Rent"),
            ("2026-01-01", "NEFT-ACME-SALARY CREDIT", 5000.0, "Income"),
            ("2026-02-07", "UPI-SWIGGY-order-3", -300.0, "Food"),
            ("2026-02-09", "UPI-DMART-2", -500.0, "Groceries"),
        ]
    )
