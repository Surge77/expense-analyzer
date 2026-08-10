"""Run the whole pipeline and print the numbers you build findings from.

    python -m expense_analyzer
    python -m expense_analyzer --list-sources
    python -m expense_analyzer --source household
    python -m expense_analyzer --source bank --account 1196428
    python -m expense_analyzer --statement data/my_statement.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from . import analyze, categorize, plots
from .clean import clean_statement
from .data import SOURCES, describe_sources, load_raw

# Resolved against the working directory, not against the package location.
# Once installed the package sits in site-packages, which has no `data/`
# beside it, so anchoring to `__file__` would point at nothing.
DEFAULT_STATEMENT = Path("data/sample_statement.csv")
DEFAULT_REPORTS = Path("reports")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES),
        default="sample",
        help="Which dataset to read. Remote sources download on first use.",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Describe each available source and exit.",
    )
    parser.add_argument(
        "--categorizer",
        choices=("rules", "model", "hybrid"),
        default="rules",
        help=(
            "How to assign categories. 'rules' is keyword matching and needs no "
            "training. 'model' and 'hybrid' train on the labelled household data, "
            "so they are only sound for --source household."
        ),
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Score the rules and the classifier on the labelled benchmark, then exit.",
    )
    parser.add_argument(
        "--account",
        default=None,
        help="Narrow a multi-account export to one account before analysing.",
    )
    parser.add_argument(
        "--statement",
        type=Path,
        default=None,
        help="Read this file instead of the source's default location.",
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


def load_frame(args: argparse.Namespace) -> pd.DataFrame:
    """Read the chosen source and return a categorized frame.

    Kept apart from `main` so the loading rules — which source, which file,
    which account — can be read without wading through the printing.
    """
    path = args.statement
    if path is None and args.source == "sample":
        path = DEFAULT_STATEMENT

    if path is not None and not path.exists():
        raise SystemExit(
            f"No statement at {path}\nGenerate the sample first:  python scripts/make_sample.py"
        )

    try:
        raw, schema = load_raw(args.source, path)
    except (RuntimeError, FileNotFoundError) as error:
        raise SystemExit(str(error)) from error

    frame = clean_statement(raw, schema)

    present = analyze.accounts(frame)
    if args.account is not None:
        frame = analyze.for_account(frame, args.account)
    elif len(present) > 1:
        raise SystemExit(
            f"{args.source!r} holds {len(present)} accounts, which cannot be summed together.\n"
            f"Choose one:  --account {present[0]}\n"
            f"Available:   {', '.join(present)}"
        )

    return apply_categorizer(frame, args.source, args.categorizer)


def apply_categorizer(frame: pd.DataFrame, source: str, choice: str) -> pd.DataFrame:
    """Attach a `category` column using the requested approach.

    The model is trained on one household's handwritten notes. Applying it to
    bank narrations is out of domain and measurably bad — the reverse
    direction scores 13.4% — so it warns rather than pretending otherwise.
    """
    if choice == "rules":
        return categorize.add_categories(frame)

    if source != "household":
        print(
            f"warning: --categorizer {choice} is trained on household notes, "
            f"but --source is {source!r}.\n"
            "         Those are different kinds of text and the result will be "
            "poor. See docs/results.md.\n"
        )

    from . import baselines, benchmark

    bench = benchmark.load_benchmark()
    predicted = (
        baselines.predict_hybrid(bench.train, frame)
        if choice == "hybrid"
        else _model_predictions(bench.train, frame)
    )

    frame = frame.copy()
    frame["category"] = predicted
    return frame


def _model_predictions(train: pd.DataFrame, frame: pd.DataFrame) -> pd.Series:
    from .model import predict
    from .model import train as fit

    return predict(fit(train), frame)


def run_evaluation() -> None:
    """Print the baseline-versus-model comparison on the labelled benchmark.

    Imported lazily: this is the only path that needs scikit-learn, and
    someone running the ordinary pipeline should not pay for it.
    """
    from . import baselines, benchmark, evaluate

    bench = benchmark.load_benchmark()
    section("Benchmark")
    print(bench.summary())

    scores, model_predictions = baselines.compare_all(bench)
    section("How well does each approach do")
    print(evaluate.comparison_table(scores))

    truth = bench.test["label"]
    section("Per class, classifier, worst recall first")
    print(evaluate.per_class_report(truth, model_predictions).to_string())

    section("Most frequent mistakes")
    print(evaluate.worst_confusions(truth, model_predictions).to_string(index=False))


def main() -> None:
    args = parse_args()
    pd.set_option("display.width", 120)
    pd.set_option("display.max_colwidth", 46)

    if args.list_sources:
        print(describe_sources())
        return

    if args.evaluate:
        run_evaluation()
        return

    frame = load_frame(args)
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
