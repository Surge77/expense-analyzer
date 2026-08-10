"""Stage 3 — aggregate transactions into answers.

Every function here takes the categorized frame and returns one thing you
could put in a sentence. No plotting, no printing.
"""

import pandas as pd

from .categorize import merchant_key

# A subscription is only interesting if it repeats at a stable price.
RECURRING_MIN_MONTHS = 2
RECURRING_MAX_SPREAD = 0.05
# A transaction this many times its category median is worth a second look.
ANOMALY_MULTIPLIER = 3.0


def spending_only(frame: pd.DataFrame) -> pd.DataFrame:
    """Outgoing rows with a positive `amount`, for readable charts.

    Transfers are excluded because moving money between your own accounts
    is not spending, and counting it double-counts everything downstream.
    """
    spend = frame[(frame["amount"] < 0) & (frame["category"] != "Transfer")].copy()
    spend["amount"] = spend["amount"].abs()
    return spend


def by_category(spend: pd.DataFrame) -> pd.Series:
    """Total spend per category, biggest first."""
    return spend.groupby("category")["amount"].sum().sort_values(ascending=False)


def monthly_totals(spend: pd.DataFrame) -> pd.Series:
    """Total spend per month, chronological."""
    return spend.groupby("month")["amount"].sum().sort_index()


def category_by_month(spend: pd.DataFrame) -> pd.DataFrame:
    """Month x category matrix — shows which category is growing."""
    return spend.pivot_table(
        index="month",
        columns="category",
        values="amount",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()


def weekday_split(spend: pd.DataFrame) -> pd.Series:
    """Spend per day of week.

    Bank statements carry a date but no clock time, so day-of-week is the
    finest time signal available. Hour-of-day analysis is not possible.
    """
    order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    totals = spend.groupby("day_name")["amount"].sum()
    return totals.reindex(order).fillna(0.0)


def top_transactions(spend: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """The single largest outflows."""
    columns = ["date", "narration", "category", "amount"]
    return spend.nlargest(top, "amount")[columns].reset_index(drop=True)


def savings_rate(frame: pd.DataFrame) -> float:
    """Fraction of income not spent, across the whole statement."""
    income = frame[frame["amount"] > 0]["amount"].sum()
    if income == 0:
        return 0.0
    spent = spending_only(frame)["amount"].sum()
    return round((income - spent) / income, 4)


def recurring_candidates(spend: pd.DataFrame) -> pd.DataFrame:
    """Charges that repeat monthly at a near-identical amount.

    Groups by merchant-ish narration prefix rather than the full string,
    because reference numbers differ on every transaction.
    """
    working = spend.copy()
    working["merchant"] = working["narration"].apply(merchant_key)

    grouped = working.groupby("merchant").agg(
        months=("month", "nunique"),
        charges=("amount", "size"),
        mean_amount=("amount", "mean"),
        min_amount=("amount", "min"),
        max_amount=("amount", "max"),
    )

    spread = (grouped["max_amount"] - grouped["min_amount"]) / grouped["mean_amount"]
    stable = grouped[
        (grouped["months"] >= RECURRING_MIN_MONTHS) & (spread <= RECURRING_MAX_SPREAD)
    ]

    result = stable.sort_values("mean_amount", ascending=False)
    result["annual_cost"] = (result["mean_amount"] * 12).round(2)
    return result.round(2)


def anomalies(spend: pd.DataFrame) -> pd.DataFrame:
    """Transactions far above the typical size for their own category."""
    medians = spend.groupby("category")["amount"].transform("median")
    flagged = spend[spend["amount"] > medians * ANOMALY_MULTIPLIER].copy()
    flagged["category_median"] = medians[flagged.index].round(2)
    flagged["times_median"] = (flagged["amount"] / medians[flagged.index]).round(1)

    columns = ["date", "narration", "category", "amount", "category_median", "times_median"]
    return flagged.sort_values("times_median", ascending=False)[columns].reset_index(drop=True)
