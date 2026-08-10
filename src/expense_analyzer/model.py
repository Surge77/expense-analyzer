"""A text classifier over transaction descriptions.

TF-IDF into logistic regression. Deliberately not a neural network:

- 1,455 training rows. A transformer would memorise them.
- The coefficients are readable. `top_features_for()` prints the words the
  model actually leans on, which is how you catch it learning something silly
  before it embarrasses you.
- It trains in under a second, so the whole experiment can be re-run while
  you are still thinking about it.

Two kinds of n-gram, unioned:

**Word n-grams** catch the obvious signal — "grocery", "mutual fund".

**Character n-grams** catch what word n-grams cannot. The notes are one
person's shorthand, with typos, abbreviations and transliterated Marathi
("Shengdane pav kg"). Character 2-5 grams match on fragments, so an unseen
spelling of a familiar word still lands near it.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

DEFAULT_MODEL_PATH = Path("models/categorizer.joblib")

# Small vocabularies, so no min_df filtering: a word appearing twice may be
# the only evidence for a small class.
WORD_NGRAMS = (1, 2)
CHAR_NGRAMS = (2, 5)
MAX_ITERATIONS = 2000
RANDOM_SEED = 42


def build_pipeline(balanced: bool = True) -> Pipeline:
    """Assemble the vectoriser and classifier.

    `class_weight="balanced"` by default. Food is 43% of the data, and an
    unweighted fit buys easy accuracy by leaning on it while ignoring
    everything small. Balancing costs a little accuracy and buys a lot of
    macro F1 — which is the number that reflects whether the small classes
    were learned at all.
    """
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=WORD_NGRAMS,
                    sublinear_tf=True,
                    lowercase=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=CHAR_NGRAMS,
                    sublinear_tf=True,
                    lowercase=True,
                ),
            ),
        ]
    )

    classifier = LogisticRegression(
        max_iter=MAX_ITERATIONS,
        class_weight="balanced" if balanced else None,
        random_state=RANDOM_SEED,
    )

    return Pipeline([("features", features), ("classifier", classifier)])


def train(train_frame: pd.DataFrame, balanced: bool = True) -> Pipeline:
    """Fit a pipeline on `narration` -> `label`."""
    pipeline = build_pipeline(balanced=balanced)
    pipeline.fit(train_frame["narration"], train_frame["label"])
    return pipeline


def predict(pipeline: Pipeline, frame: pd.DataFrame) -> pd.Series:
    """Predict labels for a frame carrying a `narration` column."""
    return pd.Series(pipeline.predict(frame["narration"]), index=frame.index)


def save(pipeline: Pipeline, path: Path = DEFAULT_MODEL_PATH) -> Path:
    """Persist a fitted pipeline. Models are gitignored, never committed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)
    return path


def load(path: Path = DEFAULT_MODEL_PATH) -> Pipeline:
    """Load a previously saved pipeline."""
    if not path.exists():
        raise FileNotFoundError(
            f"no model at {path}\nTrain one first:  python -m expense_analyzer --evaluate"
        )
    return joblib.load(path)


def top_features_for(pipeline: Pipeline, label: str, top: int = 12) -> pd.DataFrame:
    """The features pushing hardest toward one class.

    Worth reading before believing any score. A model leaning on a word that
    only makes sense in this one person's notes has memorised a quirk rather
    than learned a category.
    """
    classifier: LogisticRegression = pipeline.named_steps["classifier"]
    features: FeatureUnion = pipeline.named_steps["features"]

    classes = list(classifier.classes_)
    if label not in classes:
        raise ValueError(f"unknown label {label!r}; have: {', '.join(classes)}")

    names = features.get_feature_names_out()

    # A binary fit stores one shared coefficient row rather than one per
    # class: positive weights point at classes_[1], so classes_[0] is the
    # same row negated. Multi-class fits give a row each.
    if classifier.coef_.shape[0] == 1:
        weights = classifier.coef_[0]
        if classes.index(label) == 0:
            weights = -weights
    else:
        weights = classifier.coef_[classes.index(label)]

    frame = pd.DataFrame({"feature": names, "weight": weights})
    return frame.nlargest(top, "weight").reset_index(drop=True)


UNCERTAIN = "Uncertain"


def predict_with_confidence(
    pipeline: Pipeline,
    frame: pd.DataFrame,
    threshold: float = 0.0,
) -> pd.DataFrame:
    """Predict, but abstain when the model is not confident enough.

    Returns `prediction`, `confidence` and `answered`. Below the threshold the
    prediction becomes `Uncertain` rather than a guess.

    This is the shape a real tool wants. Categorising a statement is a
    suggestion a human corrects, and a wrong confident answer costs more than
    a blank one: a blank asks for two seconds of attention, a wrong label
    quietly corrupts a total nobody re-checks.

    Note the probabilities are uncalibrated — `0.8` does not mean "right 80%
    of the time". Use the threshold as a dial tuned on the coverage/accuracy
    curve, not as a probability.
    """
    probabilities = pipeline.predict_proba(frame["narration"])
    classes = pipeline.named_steps["classifier"].classes_

    confidence = probabilities.max(axis=1)
    predicted = [classes[index] for index in probabilities.argmax(axis=1)]
    answered = confidence >= threshold

    return pd.DataFrame(
        {
            "prediction": [
                label if ok else UNCERTAIN
                for label, ok in zip(predicted, answered, strict=True)
            ],
            "confidence": confidence,
            "answered": answered,
        },
        index=frame.index,
    )
