"""Generate a fake bank statement in HDFC export format.

Exists so the repo ships runnable data without ever committing a real
statement. Seeded, so the CSV is reproducible.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 7
OPENING_BALANCE = 15_000.00
START = date(2026, 5, 1)
MONTHS = 3

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_statement.csv"

HEADERS = [
    "Date",
    "Narration",
    "Chq./Ref.No.",
    "Value Dt",
    "Withdrawal Amt.",
    "Deposit Amt.",
    "Closing Balance",
]

# (narration template, min amount, max amount, rough count per month)
SPEND_PATTERNS: list[tuple[str, int, int, int]] = [
    ("UPI-SWIGGY-swiggy@icici-{ref}-ORDER", 150, 620, 9),
    ("UPI-ZOMATO ONLINE-zomato@hdfcbank-{ref}", 160, 580, 6),
    ("UPI-DOMINOS PIZZA-jubilant@axisbank-{ref}", 240, 760, 2),
    ("UPI-UBER INDIA-uber@axisbank-{ref}", 70, 480, 5),
    ("UPI-OLA CABS-olacabs@ybl-{ref}", 60, 390, 3),
    ("UPI-RAPIDO BIKE-rapido@paytm-{ref}", 35, 140, 4),
    ("POS 4532XXXX8821 INDIANOIL PETROL PUMP", 300, 900, 2),
    ("UPI-DMART READY-dmart@hdfcbank-{ref}", 480, 1900, 2),
    ("UPI-BIGBASKET-bbdaily@icici-{ref}", 200, 900, 2),
    ("UPI-SHREE KIRANA STORES-q{ref}@ybl", 90, 480, 3),
    ("UPI-AMAZON PAY INDIA-amazon@apl-{ref}", 350, 2200, 1),
    ("UPI-FLIPKART INTERNET-flipkart@axisbank-{ref}", 400, 1800, 1),
    ("UPI-MYNTRA DESIGNS-myntra@ybl-{ref}", 600, 1600, 1),
    # Deliberately opaque. These stay Uncategorized until you add rules.
    ("UPI-9876543210@ybl-PAYMENT FROM PHONE-{ref}", 50, 700, 2),
    ("POS 4532XXXX8821 IN*RAZ*ORDERS", 120, 900, 2),
    ("NEFT-UTIB0000123-TRF-{ref}", 500, 1800, 1),
    ("UPI-BHARATPE098765-MERCHANT PAY-{ref}", 40, 350, 2),
]

# Same amount every month. Feeds the recurring-subscription stretch goal.
MONTHLY_FIXED: list[tuple[str, float, int]] = [
    ("UPI-NETFLIX ENTERTAINMENT-netflix@hdfcbank-AUTOPAY", 649.00, 4),
    ("UPI-SPOTIFY INDIA-spotify@icici-AUTOPAY", 119.00, 6),
    ("UPI-CULT FITNESS GYM-cultfit@ybl-AUTOPAY", 1_200.00, 3),
    ("UPI-AIRTEL PREPAID-airtel@axisbank-RECHARGE", 379.00, 8),
    ("BILLPAY MSEDCL ELECTRICITY MAHARASHTRA", 1_460.00, 11),
    ("UPI-ACT FIBERNET BROADBAND-act@icici", 799.00, 5),
    ("UPI-SANDEEP PATIL-sandeep1987@oksbi-HOUSE RENT", 8_500.00, 2),
]

MONTHLY_INCOME: list[tuple[str, float, int]] = [
    ("NEFT-ACME SOFTWARE PVT LTD-SALARY CREDIT", 46_000.00, 1),
]

OCCASIONAL_INCOME: list[tuple[str, int, int]] = [
    ("UPI-AMAZON REFUND-amazon@apl-{ref}", 200, 1800),
    ("IMPS-CASHBACK CREDIT-{ref}", 25, 300),
]

FOOTER_ROW = [
    "",
    "*** This is a computer generated statement. No signature required. ***",
    "",
    "",
    "",
    "",
    "",
]


def _rupees(value: float) -> str:
    """Format like a bank does: thousands separator, two decimals."""
    return f"{value:,.2f}"


def _month_start(index: int) -> date:
    year = START.year + (START.month - 1 + index) // 12
    month = (START.month - 1 + index) % 12 + 1
    return date(year, month, 1)


def _days_in_month(day: date) -> int:
    next_month = _month_start((day.year - START.year) * 12 + day.month - START.month + 1)
    return (next_month - day).days


def build_rows(rng: random.Random) -> list[tuple[date, str, float, float]]:
    """Return unsorted (date, narration, withdrawal, deposit) tuples."""
    rows: list[tuple[date, str, float, float]] = []

    for month_index in range(MONTHS):
        first = _month_start(month_index)
        last_day = _days_in_month(first)

        for narration, low, high, per_month in SPEND_PATTERNS:
            for _ in range(rng.randint(max(1, per_month - 1), per_month + 1)):
                day = first + timedelta(days=rng.randint(0, last_day - 1))
                amount = round(rng.uniform(low, high), 2)
                text = narration.format(ref=rng.randint(100_000, 999_999))
                rows.append((day, text, amount, 0.0))

        for narration, amount, day_of_month in MONTHLY_FIXED:
            day = first + timedelta(days=min(day_of_month, last_day) - 1)
            rows.append((day, narration, amount, 0.0))

        for narration, amount, day_of_month in MONTHLY_INCOME:
            day = first + timedelta(days=min(day_of_month, last_day) - 1)
            rows.append((day, narration, 0.0, amount))

        if rng.random() < 0.8:
            narration, low, high = rng.choice(OCCASIONAL_INCOME)
            day = first + timedelta(days=rng.randint(0, last_day - 1))
            text = narration.format(ref=rng.randint(100_000, 999_999))
            rows.append((day, text, 0.0, round(rng.uniform(low, high), 2)))

    return rows


def write_csv(rows: list[tuple[date, str, float, float]], path: Path) -> int:
    """Write rows in bank order (oldest first) with a running balance."""
    rows = sorted(rows, key=lambda row: row[0])
    balance = OPENING_BALANCE

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)

        for day, narration, withdrawal, deposit in rows:
            balance = balance - withdrawal + deposit
            writer.writerow(
                [
                    day.strftime("%d/%m/%y"),
                    narration,
                    str(random_ref(day)),
                    day.strftime("%d/%m/%y"),
                    _rupees(withdrawal) if withdrawal else "",
                    _rupees(deposit) if deposit else "",
                    _rupees(balance),
                ]
            )

        writer.writerow(FOOTER_ROW)

    return len(rows)


def random_ref(day: date) -> int:
    return int(day.strftime("%d%m%y")) * 7 % 1_000_000


def main() -> None:
    rng = random.Random(SEED)
    rows = build_rows(rng)
    count = write_csv(rows, OUTPUT_PATH)
    print(f"Wrote {count} transactions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
