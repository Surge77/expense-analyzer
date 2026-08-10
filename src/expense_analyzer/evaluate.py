"""Scoring. How good is a categoriser, and good compared to what.

`categorize.coverage` answers "how much did the rules match". It cannot
answer "how much did they match *correctly*", because the sample has no
correct answer to compare against. This module needs ground-truth labels,
which is why it only works on the household benchmark.

Accuracy alone is not enough here. With 43% of rows labelled Food, a
classifier that only ever says "Food" scores 43% and has learned nothing.
Macro F1 averages the score across classes, giving the small classes the same
vote as the big one, so that model scores near zero where it belongs.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

# scikit-learn accepts 0, 1, "warn" or nan here, but its type stub declares
# only `str`. Naming the value once keeps the workaround in one place.
ZERO_DIVISION: Any = 0


@dataclass(frozen=True)
class Scores:
    """One row of the comparison table."""

    name: str
    accuracy: float
    macro_f1: float
    weighted_f1: float
    n: int

    def as_row(self) -> str:
        return (
            f"{self.name:<26}{self.accuracy:>9.1%}{self.macro_f1:>11.3f}"
            f"{self.weighted_f1:>13.3f}{self.n:>8,}"
        )


def score(name: str, y_true: pd.Series, y_pred: pd.Series) -> Scores:
    """Score one set of predictions.

    `zero_division=0` matters: a categoriser that never predicts a class has
    undefined precision for it. Treating that as zero is the honest reading —
    it found none of them.
    """
    return Scores(
        name=name,
        accuracy=float(accuracy_score(y_true, y_pred)),
        macro_f1=float(f1_score(y_true, y_pred, average="macro", zero_division=ZERO_DIVISION)),
        weighted_f1=float(
            f1_score(y_true, y_pred, average="weighted", zero_division=ZERO_DIVISION)
        ),
        n=len(y_true),
    )


def comparison_table(scores: list[Scores]) -> str:
    """The table that belongs at the top of the README."""
    header = f"{'approach':<26}{'accuracy':>9}{'macro F1':>11}{'weighted F1':>13}{'n':>8}"
    lines = [header, "-" * len(header)]
    lines += [item.as_row() for item in scores]
    return "\n".join(lines)


def per_class_report(y_true: pd.Series, y_pred: pd.Series) -> pd.DataFrame:
    """Precision, recall and F1 for every class, worst recall first.

    Sorted by recall because the interesting question is which categories the
    model is *missing*, not which it gets right.
    """
    report = classification_report(
        y_true, y_pred, output_dict=True, zero_division=ZERO_DIVISION
    )
    rows = {
        label: values
        for label, values in cast(dict[str, Any], report).items()
        if isinstance(values, dict) and label not in {"accuracy"}
    }
    frame = pd.DataFrame(rows).T
    frame["support"] = frame["support"].astype(int)
    summary = frame.loc[frame.index.isin({"macro avg", "weighted avg"})]
    classes = frame.drop(index=summary.index).sort_values("recall")
    return pd.concat([classes, summary]).round(3)


def confusion(y_true: pd.Series, y_pred: pd.Series) -> pd.DataFrame:
    """Confusion matrix as a labelled frame: rows are truth, columns guesses."""
    labels = sorted(set(y_true) | set(y_pred))
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    return pd.DataFrame(matrix, index=pd.Index(labels, name="actual"), columns=labels)


def worst_confusions(y_true: pd.Series, y_pred: pd.Series, top: int = 10) -> pd.DataFrame:
    """The most frequent specific mistakes, biggest first.

    More useful than the full matrix for writing up findings: it names the
    pairs a reader should care about instead of asking them to scan a grid.
    """
    matrix = confusion(y_true, y_pred)
    stacked = cast(pd.Series, matrix.stack())

    is_mistake = pd.Series(
        [actual != predicted for actual, predicted in stacked.index],
        index=stacked.index,
    )
    mistakes = stacked[is_mistake & (stacked > 0)]
    frame = mistakes.sort_values(ascending=False).head(top).reset_index()
    frame.columns = pd.Index(["actual", "predicted", "count"])
    return frame


def plot_confusion(y_true: pd.Series, y_pred: pd.Series, path: Path, title: str) -> Path:
    """Save a confusion matrix as a PNG.

    Normalised by row, so each cell reads "of the things that really were X,
    what share were called Y". Raw counts would make Food's 43% share drown
    out every other row.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matrix = confusion(y_true, y_pred)
    # A class predicted but never actually present has a zero row total;
    # replacing the divisor with 1 keeps the row at zero instead of NaN.
    shares = matrix.div(matrix.sum(axis=1).replace(0, 1), axis=0)
    grid = shares.to_numpy(dtype=float)

    fig, axis = plt.subplots(figsize=(9, 8))
    image = axis.imshow(grid, cmap="Blues", vmin=0, vmax=1)

    axis.set_xticks(range(len(shares.columns)))
    axis.set_xticklabels(shares.columns, rotation=45, ha="right", fontsize=8)
    axis.set_yticks(range(len(shares.index)))
    axis.set_yticklabels(shares.index, fontsize=8)
    axis.set_xlabel("predicted")
    axis.set_ylabel("actual")
    axis.set_title(title)

    for row in range(len(shares.index)):
        for column in range(len(shares.columns)):
            value = float(grid[row, column])
            if value >= 0.01:
                axis.text(
                    column,
                    row,
                    f"{value:.0%}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if value > 0.5 else "black",
                )

    fig.colorbar(image, ax=axis, fraction=0.046, label="share of actual class")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
