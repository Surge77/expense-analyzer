"""Everything the classifier has to beat.

Three baselines, deliberately in increasing order of effort, because a model
is only interesting relative to the cheapest thing that works.

1. **Majority class** — always answer the commonest label. The floor.
2. **Bank rules** — the project's own `CATEGORY_RULES`, built for bank
   narrations, applied here unchanged. Measures *domain transfer*.
3. **In-domain rules** — keywords written for this data, by reading the
   training split only. Measures what hand-written rules are actually worth
   when someone bothers to write them for the problem at hand.

Baseline 3 exists because baseline 2 is not a fair fight. Comparing rules
built for one kind of text against a model trained on another confounds
"model beats rules" with "in-domain beats out-of-domain". Separating those was
the point.
"""

from typing import TYPE_CHECKING

import pandas as pd

from .categorize import UNCATEGORIZED, categorize

if TYPE_CHECKING:
    from .benchmark import Benchmark
    from .evaluate import Scores

OTHER = "Other"

# The project's bank-narration categories translated into this dataset's
# vocabulary. Deliberately generous — a baseline is only meaningful if it is
# as strong as it can honestly be made.
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

# Keywords written by reading the *training split only*, the same way anyone
# would write rules for a new dataset. Never derived from the test split.
#
# First match wins, so specific sits above generic: "mutual fund" must beat
# nothing, and `subscription` must be tried before the generic `Other` terms
# that would otherwise swallow "mobile".
#
# `Family` gets no rule on purpose. Its 17 training rows share no vocabulary
# at all — ipad, scratch guard, shampoo, exam form. Some classes are not
# learnable, by rules or by anything else, and inventing keywords for it would
# only add false positives elsewhere.
HOUSEHOLD_RULES: dict[str, list[str]] = {
    "Investment": ["mutual fund", "prudential", "insurance", "sip ", "nifty", "elss"],
    "subscription": [
        "recharge",
        "tata play",
        "service provider",
        "data pack",
        "month pack",
        "subscription",
        "netflix",
        "prime",
    ],
    "Health": [
        "doctor",
        "hospital",
        "medicine",
        "consultation",
        "thyroid",
        "eye drop",
        "glasses",
        "tablet",
        "clinic",
    ],
    "Beauty": ["hair cut", "haircut", "shaving", "razor", "shampoo", "cream", "salon"],
    "Gift": ["gift", "birthday", "farewell", "rakshabandhan", "contribution"],
    "Apparel": [
        "clothes",
        "ironing",
        "undergarment",
        "jockey",
        "sandal",
        "shirt",
        "jeans",
        "footwear",
    ],
    # Salary must sit above Transportation: the only salary note is "From
    # workplace", and Transportation matches the bare substring "place", which
    # swallows it. A test pins this, because reordering fails silently.
    "Salary": ["workplace", "salary", "stipend"],
    "Transportation": [
        "place",
        "station",
        "residence",
        "auto ",
        "travels",
        "bus",
        "train",
        "petrol",
        "rickshaw",
        "cab",
        "ticket",
    ],
    "Household": [
        "supermart",
        "grocery",
        "groceries",
        "repair",
        "water can",
        "detergent",
        "atta",
        "rent",
        "electricity",
        "cylinder",
    ],
    "Food": [
        "milk",
        "tea",
        "pav",
        "chicken",
        "egg",
        "veg",
        "catering",
        "idli",
        "dosa",
        "vada",
        "snack",
        "lunch",
        "dinner",
        "breakfast",
        "biscuit",
        "fruit",
        "vegetable",
        "hotel",
        "restaurant",
        "juice",
        "coffee",
        "sweet",
        "rice",
        "oil",
    ],
}


def categorize_household(note: str) -> str:
    """First in-domain rule whose keyword appears in the note."""
    text = note.lower()
    for label, keywords in HOUSEHOLD_RULES.items():
        if any(keyword in text for keyword in keywords):
            return label
    return OTHER


def predict_majority(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    """Always answer with the commonest class in the training data.

    Any approach that cannot beat this has contributed nothing — and on this
    data it still scores about 43% accuracy, which is precisely why accuracy
    alone is a misleading headline.
    """
    commonest = train["label"].mode().iat[0]
    return pd.Series([commonest] * len(test), index=test.index)


def predict_bank_rules(test: pd.DataFrame) -> pd.Series:
    """The project's own rules, translated into this vocabulary."""
    return test["narration"].apply(lambda text: RULE_TO_BENCHMARK[categorize(text)])


def predict_household_rules(test: pd.DataFrame) -> pd.Series:
    """Rules written for this data, from the training split."""
    return test["narration"].apply(categorize_household)


def predict_hybrid(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
    """In-domain rules first; the model only where the rules abstain.

    Justified by measurement, not taste. On genuinely unseen text the two
    approaches fail in opposite directions: the model wins on accuracy because
    it handles the large classes, while the rules win on macro F1 because a
    keyword like "doctor" keeps working on text nobody has seen, whereas the
    model needs vocabulary it recognises.

    Taking the rule when it fires and the model when it does not should keep
    the rules' breadth over small classes and the model's coverage over
    everything else.
    """
    from .model import predict
    from .model import train as fit

    rules = predict_household_rules(test)
    pipeline = fit(train)
    learned = predict(pipeline, test)

    return rules.where(rules != OTHER, learned)


def compare_all(bench: "Benchmark") -> tuple[list["Scores"], pd.Series]:
    """Score every approach on the same test set, weakest first.

    Returns the scores and the model's predictions, so a caller can dig into
    its mistakes without paying to fit it twice.
    """
    from .evaluate import score
    from .model import predict, train

    truth = bench.test["label"]
    pipeline = train(bench.train)
    model_predictions = predict(pipeline, bench.test)

    rules = predict_household_rules(bench.test)
    hybrid = rules.where(rules != OTHER, model_predictions)

    scores = [
        score("majority class", truth, predict_majority(bench.train, bench.test)),
        score("bank rules (out of domain)", truth, predict_bank_rules(bench.test)),
        score("in-domain rules", truth, rules),
        score("TF-IDF + LogReg", truth, model_predictions),
        score("hybrid (rules, then model)", truth, hybrid),
    ]
    return scores, model_predictions
