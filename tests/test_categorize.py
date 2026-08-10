"""Rule order is a design decision, so it gets a test."""

import pandas as pd
import pytest

from expense_analyzer.categorize import UNCATEGORIZED, add_categories, categorize, coverage


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


@pytest.mark.parametrize(
    "narration",
    [
        "FDRL/INTERNAL FUND TRANSFE",
        "TRF TO  Indiaforensic SERVICES I",
        "TRF FROM  Indiaforensic SERVICES",
        "FDRL/REAL TIME GROSS SETTL",
    ],
)
def test_recognises_self_transfers_seen_in_real_bank_exports(narration):
    """These four are the most common narrations in the 116k-row real bank
    dataset. Without a Transfer rule they counted as spending."""
    assert categorize(narration) == "Transfer"


def test_income_beats_transfer_because_transfer_is_declared_last():
    """`IMPS-CASHBACK CREDIT` and a NEFT salary line both look like transfers
    by prefix. Income is declared above Transfer so they are not misfiled —
    reordering CATEGORY_RULES silently breaks this."""
    assert categorize("NEFT-ACME SOFTWARE PVT LTD-SALARY CREDIT") == "Income"
    assert categorize("IMPS-CASHBACK CREDIT-123456") == "Income"


def test_transfer_rules_do_not_touch_the_samples_opaque_narrations():
    """The shipped sample keeps ~8% uncategorised on purpose as the
    rule-writing exercise. The Transfer rules must not quietly solve it."""
    assert categorize("NEFT-UTIB0000123-TRF-472731") == UNCATEGORIZED


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
