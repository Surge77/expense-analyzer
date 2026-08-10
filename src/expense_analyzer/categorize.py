"""Stage 2 — turn merchant noise into categories.

`UPI-SWIGGY-swiggy@icici-512334-ORDER` is what the bank knows.
`Food` is what you need. The mapping between them is domain knowledge that
exists nowhere in the data, so it is written by hand here.

Rules are tested top to bottom and the first match wins, so specific
categories must sit above generic ones.
"""

import re

import pandas as pd

UNCATEGORIZED = "Uncategorized"

# Every transaction carries a unique reference number, so raw narrations never
# repeat and counting them is useless. Stripping the digits collapses 40 rows
# into the 4 merchants they actually came from.
REFERENCE_DIGITS = re.compile(r"\d{4,}")

CATEGORY_RULES: dict[str, list[str]] = {
    "Rent": ["house rent", "rent"],
    "Subscriptions": ["netflix", "spotify", "cult fitness", "prime video", "autopay"],
    "Bills": ["airtel", "jio", "msedcl", "electricity", "fibernet", "broadband", "recharge"],
    "Groceries": ["dmart", "bigbasket", "kirana", "blinkit", "zepto"],
    "Food": ["swiggy", "zomato", "dominos", "kfc", "restaurant", "cafe", "eatsure"],
    "Transport": ["uber", "ola cabs", "rapido", "indianoil", "petrol", "irctc", "metro"],
    "Shopping": ["amazon pay", "flipkart", "myntra", "ajio", "nykaa"],
    "Income": ["salary", "refund", "cashback", "interest credit", "dividend"],
    # Deliberately last. Money moved between your own accounts is not
    # spending, and `analyze.spending_only` drops this category so it is not
    # counted twice. The keywords must stay narrow and must sit below Income:
    # "IMPS-CASHBACK CREDIT" and "NEFT-...-SALARY CREDIT" both look like
    # transfers by prefix, and matching them here would misfile real income.
    "Transfer": [
        # Not "...transfer": real exports truncate the narration mid-word, so
        # the most common row in the 116k-row bank dataset literally reads
        # "FDRL/INTERNAL FUND TRANSFE". Matching the truncated stem catches
        # both forms.
        "internal fund transfe",
        "trf to",
        "trf from",
        "rtgs",
        "real time gross settl",
        "self transfer",
    ],
}


def categorize(narration: str) -> str:
    """Return the first category whose keyword appears in the narration."""
    text = narration.lower()
    for category, keywords in CATEGORY_RULES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return UNCATEGORIZED


def add_categories(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach a `category` column to a cleaned statement."""
    frame = frame.copy()
    frame["category"] = frame["narration"].apply(categorize)
    return frame


def coverage(frame: pd.DataFrame) -> dict[str, float]:
    """How much of the statement the rules actually explain.

    Report both counts and rupees: a handful of unmatched rows barely
    matters, unless they happen to be the expensive ones.
    """
    unmatched = frame[frame["category"] == UNCATEGORIZED]
    total_value = frame["amount"].abs().sum()

    return {
        "rows_total": float(len(frame)),
        "rows_uncategorized": float(len(unmatched)),
        "pct_rows_uncategorized": round(100 * len(unmatched) / max(len(frame), 1), 1),
        "value_uncategorized": round(unmatched["amount"].abs().sum(), 2),
        "pct_value_uncategorized": round(
            100 * unmatched["amount"].abs().sum() / max(total_value, 1), 1
        ),
    }


def merchant_key(narration: str) -> str:
    """Collapse a narration to the merchant, dropping reference numbers."""
    return REFERENCE_DIGITS.sub("", narration).strip(" -").upper()


def unmatched_narrations(frame: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    """The merchants to read when writing your next batch of rules.

    This is the loop that is the actual project: read these, add keywords,
    re-run, repeat until coverage stops improving. Sorted by rupees, not by
    count, because that is the order in which fixing them matters.
    """
    unmatched = frame[frame["category"] == UNCATEGORIZED].copy()
    unmatched["merchant"] = unmatched["narration"].apply(merchant_key)

    summary = unmatched.groupby("merchant").agg(
        charges=("amount", "size"),
        total=("amount", lambda values: round(values.abs().sum(), 2)),
    )
    return summary.sort_values("total", ascending=False).head(top)
