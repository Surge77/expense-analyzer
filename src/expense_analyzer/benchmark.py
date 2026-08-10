"""The labelled benchmark, and the three ways of splitting it.

Built from `prasad22/daily-transactions-dataset`: 2,461 transactions a real
person tagged by hand while tracking their own spending. It is the only source
here with a correct answer attached, which is what makes measurement possible.

Three preparation decisions, all arguable, all declared:

**Rows without a note are dropped.** 521 of 2,461 carry no text at all. There
is nothing to classify them from, so keeping them would measure guessing.
1,940 rows remain. See `docs/decisions/0005`.

**Classes with fewer than 20 examples become `Other`.** 38 classes over 1,940
rows leaves a long tail — `Interest` has 12 rows, so a split gives the model
three examples to learn from and three to be judged on. That is noise. The cut
leaves 12 classes.

**The split strategy changes the answer, so all three are reported.**

| strategy | question it answers |
| --- | --- |
| `random` | How well does this categorise *my* recurring spending? |
| `grouped` | How well does it handle a description it has never seen? |
| `temporal` | How well would it have worked deployed, predicting forward? |

`random` is stratified but lets an identical note land in both halves. That is
not a mistake — someone tracking expenses writes "grocery" hundreds of times,
and re-recognising it is the real use case. But **56.7% of the test set is
notes already present in training**, so the random score is substantially
recognition rather than generalisation. `grouped` keeps every copy of a note
on one side of the split and is the honest generalisation number.
"""

import re
from dataclasses import dataclass
from typing import Literal, cast

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from .clean import clean_statement
from .data import load_raw

# Below this many examples a class cannot be learned or fairly judged.
MIN_EXAMPLES_PER_CLASS = 20
OTHER = "Other"

TEST_SIZE = 0.25
# Fixed so the numbers in docs/results.md reproduce exactly.
RANDOM_SEED = 42

Strategy = Literal["random", "grouped", "temporal"]
STRATEGIES: tuple[Strategy, ...] = ("random", "grouped", "temporal")

# Anything that is not a letter or digit. Two notes differing only by
# punctuation or capitalisation are the same note for grouping purposes.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_note(text: str) -> str:
    """Collapse a note to its comparable form, for grouping duplicates."""
    return _NON_ALNUM.sub(" ", str(text).lower()).strip()


@dataclass(frozen=True)
class Benchmark:
    """A prepared train/test split, plus what was done to build it."""

    train: pd.DataFrame
    test: pd.DataFrame
    classes: list[str]
    strategy: Strategy
    dropped_without_note: int
    collapsed_to_other: int

    @property
    def total(self) -> int:
        return len(self.train) + len(self.test)

    @property
    def seen_in_train(self) -> pd.Series:
        """Per test row: is this exact note already present in training?

        The share of `True` here is how much of a score is recognition rather
        than generalisation. It is 0% by construction for the grouped split.
        """
        known = {normalise_note(note) for note in self.train["narration"]}
        return self.test["narration"].apply(lambda note: normalise_note(note) in known)

    def summary(self) -> str:
        overlap = self.seen_in_train.mean()
        return (
            f"{self.total:,} labelled rows over {len(self.classes)} classes "
            f"({len(self.train):,} train / {len(self.test):,} test), "
            f"split: {self.strategy}\n"
            f"{self.dropped_without_note:,} rows dropped for having no note\n"
            f"{self.collapsed_to_other:,} rows moved to {OTHER!r} "
            f"(class had under {MIN_EXAMPLES_PER_CLASS} examples)\n"
            f"{overlap:.1%} of test notes also appear in training"
        )


def collapse_rare_classes(labels: pd.Series, minimum: int = MIN_EXAMPLES_PER_CLASS) -> pd.Series:
    """Fold classes with too few examples into `Other`."""
    counts = labels.value_counts()
    rare = set(counts[counts < minimum].index)
    return labels.where(~labels.isin(rare), OTHER)


def prepare(minimum: int = MIN_EXAMPLES_PER_CLASS) -> tuple[pd.DataFrame, int, int]:
    """Download, clean and filter — everything before the split."""
    raw, schema = load_raw("household")
    frame = clean_statement(raw, schema)

    with_note = frame[frame["narration"].str.strip() != ""].copy()
    dropped = len(frame) - len(with_note)

    collapsed = collapse_rare_classes(with_note["label"], minimum)
    moved = int((collapsed != with_note["label"]).sum())
    with_note["label"] = collapsed

    return with_note.reset_index(drop=True), dropped, moved


def _split_random(
    frame: pd.DataFrame, test_size: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified, so every class keeps its proportion in both halves."""
    parts = train_test_split(
        frame, test_size=test_size, random_state=seed, stratify=frame["label"]
    )
    return cast(pd.DataFrame, parts[0]), cast(pd.DataFrame, parts[1])


def _split_grouped(frame: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep every copy of an identical note on one side of the split.

    `StratifiedGroupKFold` rather than `GroupShuffleSplit`, so class balance
    survives the grouping. Four folds gives a 75/25 split; the first is taken.
    """
    groups = frame["narration"].apply(normalise_note)
    splitter = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=seed)
    train_index, test_index = next(splitter.split(frame, frame["label"], groups))
    return frame.iloc[train_index], frame.iloc[test_index]


def _split_temporal(frame: pd.DataFrame, test_size: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on the past, test on the future — the deployment situation.

    Cannot be stratified: which classes appear late is a property of the data,
    not something to correct for. A class absent from training simply scores
    zero, which is what would really happen.
    """
    ordered = frame.sort_values("date")
    cut = int(len(ordered) * (1 - test_size))
    return ordered.iloc[:cut], ordered.iloc[cut:]


def load_benchmark(
    strategy: Strategy = "random",
    minimum: int = MIN_EXAMPLES_PER_CLASS,
    test_size: float = TEST_SIZE,
    seed: int = RANDOM_SEED,
) -> Benchmark:
    """Build the benchmark under one of the three split strategies."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; expected one of: {', '.join(STRATEGIES)}")

    frame, dropped, moved = prepare(minimum)

    if strategy == "random":
        train, test = _split_random(frame, test_size, seed)
    elif strategy == "grouped":
        train, test = _split_grouped(frame, seed)
    else:
        train, test = _split_temporal(frame, test_size)

    return Benchmark(
        train=train.reset_index(drop=True),
        test=test.reset_index(drop=True),
        classes=sorted(frame["label"].unique()),
        strategy=strategy,
        dropped_without_note=dropped,
        collapsed_to_other=moved,
    )
