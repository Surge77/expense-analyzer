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

The score depends on how the data is split, so all three are reported.

| split | notes seen in training | accuracy | macro F1 |
| --- | ---: | ---: | ---: |
| `random` | 56.7% | 87.0% | 0.769 |
| `grouped` | 0% | 72.1% | 0.460 |
| `temporal` | 58.6% | 87.2% | 0.784 |

**`grouped` is the number to quote for generalisation.** The `random` split
lets an identical note appear in both halves; on the 275 test rows whose note
also appears in training the model scores 96.4%, and on the 210 genuinely
unseen rows it scores 74.8%.

Against every baseline, on genuinely unseen text (`grouped`):

| approach | accuracy | macro F1 |
| --- | ---: | ---: |
| majority class | 43.7% | 0.055 |
| bank rules (out of domain) | 13.4% | 0.029 |
| in-domain rules | 56.9% | 0.502 |
| this model | 72.1% | 0.460 |
| hybrid (rules, then model) | 73.9% | 0.567 |

Note the model **loses to hand-written rules on macro F1** here. It wins on
accuracy, which the large classes dominate; the rules generalise better across
small classes. The hybrid beats both, and is what this model should be
deployed as when novel descriptions are expected.

5-fold cross-validation on the `random` training split: macro F1 0.740 ± 0.034.

Macro F1 is the number to read. Accuracy rewards getting the largest class
right, and Food alone is 43% of the data.

### Abstention

With a confidence threshold the model can decline to answer:

| threshold | coverage | accuracy when answered |
| --- | ---: | ---: |
| 0.0 | 100% | 87.0% |
| 0.3 | 82.1% | 94.2% |
| 0.5 | 57.3% | 97.8% |

Probabilities are **uncalibrated** — treat the threshold as a dial tuned on
this curve, not as a probability.

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
- **A few hundred test rows.** Two or three points of difference is noise.
- **Uncalibrated probabilities.** See the abstention note above.
- **Indian context.** Amounts in rupees; notes mix English, Marathi and
  transliteration. Character n-grams help, but nothing here shows it works on
  another language.

## Ethical considerations

The training data is one person's complete spending history. It is not
redistributed here, and neither are derived artifacts that could reveal it.
Anyone applying this to their own statement should note that the resulting
categorised file is at least as sensitive as the statement itself.

## Maintenance

Regenerate with `python scripts/run_benchmark.py`, which rewrites
`docs/results.md` and both confusion matrices so documentation cannot drift
from the code. Pinned dependencies and seed 42 make the numbers reproducible.
