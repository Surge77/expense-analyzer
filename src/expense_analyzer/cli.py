"""Run the whole pipeline and print the numbers you build findings from.

    python -m expense_analyzer
    python -m expense_analyzer --statement data/my_statement.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from . import analyze, categorize, plots
from .clean import load_and_clean

# Resolved against the working directory, not against the package location.
# Once installed the package sits in site-packages, which has no `data/`
# beside it, so anchoring to `__file__` would point at nothing.
DEFAULT_STATEMENT = Path("data/sample_statement.csv")
DEFAULT_REPORTS = Path("reports")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--statement",
        type=Path,
        default=DEFAULT_STATEMENT,
        help="Path to a bank statement CSV in HDFC export format.",
    )
    parser.add_argument(
        "--reports",
        type=Path,
        default=DEFAULT_REPORTS,
        help="Directory for the generated PNG charts.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="How many large transactions to list.",
    )
    return parser.parse_args()


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def main() -> None:
    args = parse_args()
    pd.set_option("display.width", 120)
    pd.set_option("display.max_colwidth", 46)

    if not args.statement.exists():
        raise SystemExit(
            f"No statement at {args.statement}\n"
            "Generate the sample first:  python scripts/make_sample.py"
        )

    frame = categorize.add_categories(load_and_clean(args.statement))
    spend = analyze.spending_only(frame)

    section("Statement")
    first, last = frame["date"].min(), frame["date"].max()
    print(f"{len(frame)} transactions, {first:%d %b %Y} to {last:%d %b %Y}")
    print(f"Total spent   {spend['amount'].sum():>12,.2f}")
    print(f"Total income  {frame[frame['amount'] > 0]['amount'].sum():>12,.2f}")
    print(f"Savings rate  {analyze.savings_rate(frame):>12.1%}")

    section("Rule coverage")
    for key, value in categorize.coverage(frame).items():
        print(f"{key:<28} {value:>10,.1f}")
    unmatched = categorize.unmatched_narrations(frame)
    if not unmatched.empty:
        print("\nRead these, then add keywords to CATEGORY_RULES:")
        print(unmatched.to_string())

    section("Spend by category")
    print(analyze.by_category(spend).round(2).to_string())

    section("Spend per month")
    print(analyze.monthly_totals(spend).round(2).to_string())

    section("Spend by day of week")
    print(analyze.weekday_split(spend).round(2).to_string())

    section(f"Top {args.top} transactions")
    print(analyze.top_transactions(spend, args.top).to_string(index=False))

    section("Recurring charges")
    recurring = analyze.recurring_candidates(spend)
    print(recurring.to_string() if not recurring.empty else "None detected.")

    section("Unusually large for their category")
    flagged = analyze.anomalies(spend)
    print(flagged.head(8).to_string(index=False) if not flagged.empty else "None flagged.")

    written = plots.plot_all(spend, args.reports)
    section("Charts")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
