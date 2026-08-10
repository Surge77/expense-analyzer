# 0006 — Report three splits, not one

**Status:** accepted

## Context

The first version of this project reported one number: 87.0% accuracy on a
stratified random split. That figure was arrived at honestly and is not wrong,
but it was never interrogated.

Checking afterwards showed that **56.7% of the test set consisted of notes
whose exact text also appeared in training**. Someone tracking their own
spending writes "grocery" hundreds of times, so a random split scatters
identical strings across both halves.

Splitting the test set on that basis:

| test subset | n | accuracy |
| --- | ---: | ---: |
| note also appears in training | 275 | 96.4% |
| genuinely unseen text | 210 | 74.8% |

## Decision

Report three splits everywhere a score appears — `random`, `grouped` and
`temporal` — and state the overlap percentage alongside each.

## Why

**One number here is a choice about which story to tell.** The three differ by
fifteen points of accuracy on identical data with an identical model.

**None of them is the "true" score.** They answer different questions:

- `random` — how well does this categorise *my* recurring spending? Repeats
  are the reality of that job, so recognising them is a feature.
- `grouped` — how well does it handle a description it has never seen? Every
  copy of a note stays on one side.
- `temporal` — how would it have done deployed, trained on the past?

**Calling the overlap "leakage" and deleting it would also be wrong.** For the
actual use case, seeing "grocery" again is exactly what happens. The mistake
was never checking, not the split itself.

## Cost

The results document is longer and there is no single headline figure, which
is a real cost for a portfolio project — a reader wanting one number has to
read a paragraph instead.

Accepted because the alternative is a number that does not survive the first
question an informed reader would ask.

## Consequence

Reporting `grouped` exposed a second finding that the random split had hidden
entirely: on genuinely unseen text, in-domain **rules beat the model on macro
F1** (0.502 against 0.460), and a hybrid beats both. That result would not
exist without this decision.
