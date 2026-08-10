"""The labelled benchmark, and the baselines any model has to beat.

Built from `prasad22/daily-transactions-dataset`: 2,461 rows a real person
tagged by hand while tracking their own spending. It is the only source here
with a correct answer attached, which is what makes measurement possible.

Three decisions shape it, all of them arguable, all of them declared:

**Rows without a note are dropped.** 521 of 2,461 carry no text at all. There
is nothing to classify them from, so keeping them would measure guessing.
1,940 rows remain.

**Classes with fewer than 20 examples become `Other`.** 38 classes over 1,940
rows leaves a long tail — `Interest` has 12 rows, so a train/test split gives
the model three examples to learn from and three to be judged on. That is
noise, not signal. The cut leaves 12 classes.

**The split is stratified.** Food is 43% of rows; an unstratified split can
easily hand the test set a class the training set never saw.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pandas as pd
from sklearn.model_selection import train_test_split

if TYPE_CHECKING:
    from .evaluate import Scores

from .categorize import UNCATEGORIZED, categorize
from .clean import clean_statement
from .data import load_raw

# Below this many examples a class cannot be learned or fairly judged.
MIN_EXAMPLES_PER_CLASS = 20
OTHER = "Other"

TEST_SIZE = 0.25
# Fixed so the numbers in docs/results.md can be reproduced exactly.
RANDOM_SEED = 42

# The rules were written for bank narrations ("UPI-SWIGGY-...") and this
# benchmark holds a human's shorthand ("Idli medu Vada mix 2 plates"). The
# two also name their categories differently, so rule output is translated
# into the benchmark's vocabulary before scoring.
#
# This mapping is generous to the rules on purpose. Making the baseline as
# strong as it can honestly be is the only way the comparison means anything.
RULE_TO_BENCHMARK: dict[str, str] = {
    "Food": "Food",
    "Groceries": "Household",
    "Transport": "Transportation",
    "Subscriptions": "subscription",
    "Bills": "Household",
    "Rent": "Household",
    "Shopping": "Apparel",
    "Income": "Salary",
    "Transfer": OTHER,
    UNCATEGORIZED: OTHER,
}


@dataclass(frozen=True)
class Benchmark:
    """A prepared train/test split, plus what was done to build it."""

    train: pd.DataFrame
    test: pd.DataFrame
    classes: list[str]
    dropped_without_note: int
    collapsed_to_other: int

    @property
    def total(self) -> int:
        return len(self.train) + len(self.test)

    def summary(self) -> str:
        return (
            f"{self.total:,} labelled rows over {len(self.classes)} classes "
            f"({len(self.train):,} train / {len(self.test):,} test)\n"
            f"{self.dropped_without_note:,} rows dropped for having no note\n"
            f"{self.collapsed_to_other:,} rows moved to {OTHER!r} "
            f"(class had under {MIN_EXAMPLES_PER_CLASS} examples)"
        )


def collapse_rare_classes(labels: pd.Series, minimum: int = MIN_EXAMPLES_PER_CLASS) -> pd.Series:
    """Fold classes with too few examples into `Other`."""
    counts = labels.value_counts()
    rare = set(counts[counts < minimum].index)
    return labels.where(~labels.isin(rare), OTHER)


def load_benchmark(
    minimum: int = MIN_EXAMPLES_PER_CLASS,
    test_size: float = TEST_SIZE,
    seed: int = RANDOM_SEED,
) -> Benchmark:
    """Download, clean, filter and split the labelled dataset."""
    raw, schema = load_raw("household")
    frame = clean_statement(raw, schema)

    with_note = frame[frame["narration"].str.strip() != ""].copy()
    dropped = len(frame) - len(with_note)

    collapsed = collapse_rare_classes(with_note["label"], minimum)
    moved = int((collapsed != with_note["label"]).sum())
    with_note["label"] = collapsed

    # train_test_split is typed as returning a bare list, so the two
    # halves need naming before pandas methods are visible on them.
    split = train_test_split(
        with_note,
        test_size=test_size,
        random_state=seed,
        stratify=with_note["label"],
    )
    train = cast(pd.DataFrame, split[0])
    test = cast(pd.DataFrame, split[1])

    return Benchmark(
        train=train.reset_index(drop=True),
        test=test.reset_index(drop=True),
        classes=sorted(with_note["label"].unique()),
        dropped_without_note=dropped,
        collapsed_to_other=moved,
    )


def predict_majority(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    """Always answer with the commonest class in the training data.

    The floor. Any approach that cannot beat this has contributed nothing,
    and on this data it still scores about 43% accuracy — which is exactly
    why accuracy alone is a misleading headline.
    """
    commonest = train["label"].mode().iat[0]
    return pd.Series([commonest] * len(test), index=test.index)


def predict_rules(test: pd.DataFrame) -> pd.Series:
    """Apply the keyword rules, translated into the benchmark's vocabulary."""
    return test["narration"].apply(lambda text: RULE_TO_BENCHMARK[categorize(text)])


def compare_all(bench: Benchmark) -> tuple[list["Scores"], pd.Series]:
    """Score every approach on the same test set, weakest first.

    Returns the scores and the trained model's predictions, so callers can
    dig into its mistakes without paying to fit it twice.
    """
    from .evaluate import score
    from .model import predict, train

    truth = bench.test["label"]
    pipeline = train(bench.train)
    model_predictions = predict(pipeline, bench.test)

    scores = [
        score("majority class", truth, predict_majority(bench.train, bench.test)),
        score("keyword rules", truth, predict_rules(bench.test)),
        score("TF-IDF + LogReg", truth, model_predictions),
    ]
    return scores, model_predictions
