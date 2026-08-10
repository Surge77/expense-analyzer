# 0005 — Rows with no note are excluded from the benchmark

**Status:** accepted

## Context

521 of the labelled dataset's 2,461 rows have an empty `Note`. They still
carry a ground-truth `Category`, so they could be scored.

## Decision

Drop them. The benchmark is 1,940 rows, and both the module docstring and
`docs/results.md` state the exclusion and its size.

## Why

**There is nothing to classify them from.** The model's only input is the
note. Scoring a model on rows with no input measures how well it guesses the
prior — which is exactly what the majority-class baseline already measures,
deliberately and separately.

**It would dilute the comparison rather than sharpen it.** Rules and model
would both fall back to their default answer on those rows, so 21% of the
benchmark would become the same coin flip for every approach.

**Silently keeping them would be worse than either.** A reader seeing a lower
number deserves to know that a fifth of the data was unclassifiable, not to
have it folded invisibly into the average.

## Cost

The headline number is measured on a friendlier subset than the raw dataset,
and it is not the number you would get by pointing this at all 2,461 rows.
That is precisely why the exclusion is restated everywhere the score appears,
including the model card.

An alternative worth trying: use `Mode` — cash, or which bank account — as a
weak feature, so noteless rows become classifiable after all. That would turn
a text-classification task into a mixed-feature one, which is a different
project from the one being taught here.
