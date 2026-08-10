"""Rule order is a design decision, so it gets a test."""

import pandas as pd
import pytest

from src.categorize import UNCATEGORIZED, add_categories, categorize, coverage


@pytest.mark.parametrize(
    "narration,expected",
    [
        ("UPI-SWIGGY-swiggy@icici-512334-ORDER", "Food"),
        ("UPI-ZOMATO ONLINE-zomato@hdfcbank-4411", "Food"),
        ("UPI-UBER INDIA-uber@axisbank-9921", "Transport"),
        ("POS 4532XXXX8821 INDIANOIL PETROL PUMP", "Transport"),
        ("UPI-DMART READY-dmart@hdfcbank-7781", "Groceries"),
        ("BILLPAY MSEDCL ELECTRICITY MAHARASHTRA", "Bills"),
        ("NEFT-ACME SOFTWARE PVT LTD-SALARY CREDIT", "Income"),
    ],
)
def test_maps_known_merchants_to_categories(narration, expected):
    assert categorize(narration) == expected


def test_matching_is_case_insensitive():
    assert categorize("upi-swiggy-lowercase") == categorize("UPI-SWIGGY-UPPERCASE")


def test_unknown_merchant_falls_back_instead_of_guessing():
    assert categorize("UPI-9876543210@ybl-PAYMENT FROM PHONE") == UNCATEGORIZED


def test_first_matching_rule_wins():
    """Netflix autopay hits both Subscriptions and Bills ('recharge' family).

    Subscriptions is declared first, so it takes precedence. Reordering
    CATEGORY_RULES silently changes results, which is why this is pinned.
    """
    assert categorize("UPI-NETFLIX ENTERTAINMENT-netflix@hdfcbank-AUTOPAY") == "Subscriptions"


def test_coverage_reports_rows_and_rupees_separately():
    frame = pd.DataFrame(
        {
            "narration": ["UPI-SWIGGY-x", "UPI-999@ybl-UNKNOWN"],
            "amount": [-100.0, -900.0],
        }
    )
    report = coverage(add_categories(frame))

    assert report["pct_rows_uncategorized"] == 50.0
    # Half the rows but 90% of the money: the reason both are reported.
    assert report["pct_value_uncategorized"] == 90.0
