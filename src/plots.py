"""Stage 4 — four charts, saved as PNGs.

Kept apart from analyze.py so the aggregation functions stay testable and
free of any drawing side effects.
"""

from pathlib import Path

import matplotlib

# Non-interactive backend: this module is imported by a CLI script that has
# no display attached.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must follow the backend call)
import pandas as pd  # noqa: E402

from . import analyze  # noqa: E402

DPI = 150
FIGSIZE = (9, 5)


def _finish(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def plot_by_category(spend: pd.DataFrame, out_dir: Path) -> Path:
    """Where the money goes. Horizontal bars beat a pie for reading values."""
    totals = analyze.by_category(spend).sort_values()

    fig, axis = plt.subplots(figsize=FIGSIZE)
    axis.barh(totals.index, totals.values)
    axis.set_xlabel("Rupees spent")
    axis.set_title("Spend by category")
    for index, value in enumerate(totals.values):
        axis.text(value, index, f" {value:,.0f}", va="center", fontsize=9)

    return _finish(fig, out_dir / "01_spend_by_category.png")


def plot_monthly_total(spend: pd.DataFrame, out_dir: Path) -> Path:
    """Is it getting worse."""
    totals = analyze.monthly_totals(spend)

    fig, axis = plt.subplots(figsize=FIGSIZE)
    axis.plot(totals.index.astype(str), totals.values, marker="o")
    axis.set_ylabel("Rupees spent")
    axis.set_title("Total spend per month")
    axis.grid(alpha=0.3)

    return _finish(fig, out_dir / "02_monthly_total.png")


def plot_category_by_month(spend: pd.DataFrame, out_dir: Path) -> Path:
    """Which category is driving the change."""
    pivot = analyze.category_by_month(spend)

    fig, axis = plt.subplots(figsize=FIGSIZE)
    bottom = None
    for column in pivot.columns:
        axis.bar(pivot.index.astype(str), pivot[column], bottom=bottom, label=column)
        bottom = pivot[column] if bottom is None else bottom + pivot[column]

    axis.set_ylabel("Rupees spent")
    axis.set_title("Spend by category, per month")
    axis.legend(fontsize=8, ncol=2)

    return _finish(fig, out_dir / "03_category_by_month.png")


def plot_transaction_sizes(spend: pd.DataFrame, out_dir: Path) -> Path:
    """Bled by many small charges, or a few big ones."""
    fig, axis = plt.subplots(figsize=FIGSIZE)
    axis.hist(spend["amount"], bins=40)
    axis.axvline(
        spend["amount"].median(),
        linestyle="--",
        label=f"median {spend['amount'].median():,.0f}",
    )
    axis.set_xlabel("Transaction size (rupees)")
    axis.set_ylabel("Number of transactions")
    axis.set_title("Distribution of transaction sizes")
    axis.legend()

    return _finish(fig, out_dir / "04_transaction_sizes.png")


def plot_all(spend: pd.DataFrame, out_dir: Path) -> list[Path]:
    return [
        plot_by_category(spend, out_dir),
        plot_monthly_total(spend, out_dir),
        plot_category_by_month(spend, out_dir),
        plot_transaction_sizes(spend, out_dir),
    ]
