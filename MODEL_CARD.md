# Model card — transaction categoriser

## Overview

A text classifier that assigns a spending category to a transaction
description. TF-IDF features (word 1–2 grams and character 2–5 grams) into
multinomial logistic regression with balanced class weights.

Trained and evaluated in this repository; the artifact is not distributed.
Rebuild it with `python scripts/run_benchmark.py`.

## Intended use

**Intended.** Suggesting a category for a personal transaction description,
inside a tool where a human sees and can correct the suggestion. Teaching how
a rule baseline compares against a learned model.

**Not intended.** Any automated decision about a person — creditworthiness,
fraud, eligibility, affordability. It was trained on one household's notes
and has no basis for judgments about anyone.

## Training data

`prasad22/daily-transactions-dataset` — 2,461 transactions one person
recorded and categorised by hand between January 2015 and September 2018.
Not redistributed here; it downloads on demand.

After preparation, 1,940 rows over 12 classes, split 1,455 train / 485 test,
stratified, seed 42.

Three preparation choices, each of which affects the numbers:

| Choice | Effect |
| --- | --- |
| Rows with an empty note dropped | 521 rows removed. Nothing to classify them from. |
| Classes under 20 examples folded into `Other` | 38 classes become 12. |
| Stratified split | Food is 43% of rows; an unstratified split can lose a small class entirely. |

## Metrics

On the 485-row held-out test set:

| approach | accuracy | macro F1 | weighted F1 |
| --- | ---: | ---: | ---: |
| majority class | 42.9% | 0.050 | 0.257 |
| keyword rules | 13.4% | 0.035 | 0.046 |
| this model | 87.0% | 0.769 | 0.864 |

5-fold cross-validation on the training split: macro F1 0.740 ± 0.034.

Macro F1 is the number to read. Accuracy rewards a model for getting the
largest class right, and Food alone is 43% of the data.

Per-class scores and confusion matrices: [docs/results.md](docs/results.md).

## Limitations

- **One household, one labeller.** The categories reflect one person's
  conventions. "Household" versus "Food" for groceries is their judgment.
- **Trained on human notes, not bank narrations.** The two are different kinds
  of text. This model should not be expected to categorise a raw bank
  statement, and the repository does not claim it can — the rules going the
  other way and scoring 13.4% is the evidence for how badly that transfers.
- **`Family` is never predicted.** 23 examples, no distinctive vocabulary.
- **`Household` and `Food` are confused in both directions** — the dominant
  error. Groceries to cook with and a ready-made meal use the same words.
- **485 test rows.** Two or three points of difference is noise.
- **Indian context.** Amounts in rupees; notes mix English, Marathi and
  transliteration. Character n-grams help, but nothing here shows it works on
  another language.
- **No calibration.** Predicted probabilities are not meaningful confidences.

## Ethical considerations

The training data is one person's complete spending history. It is not
redistributed here, and neither are derived artifacts that could reveal it.
Anyone applying this to their own statement should note that the resulting
categorised file is at least as sensitive as the statement itself.

## Maintenance

Regenerate with `python scripts/run_benchmark.py`, which rewrites
`docs/results.md` and both confusion matrices so documentation cannot drift
from the code. Pinned dependencies and seed 42 make the numbers reproducible.
