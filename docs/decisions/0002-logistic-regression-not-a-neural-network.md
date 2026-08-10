# 0002 — Logistic regression, not a neural network

**Status:** accepted

## Context

The classification task is short free text into 12 classes, with 1,455
training rows. A transformer fine-tune or a sentence-embedding model would be
the reflexive choice.

## Decision

TF-IDF features — word 1-2 grams unioned with character 2-5 grams — into
multinomial logistic regression with balanced class weights.

## Why

**1,455 rows.** A model with millions of parameters memorises a dataset this
size. The cross-validation spread would widen and the test score would stop
meaning anything.

**The weights are readable.** `model.top_features_for("Transportation")`
prints the features the model actually leans on. That is how you catch it
learning a quirk — a word that merely co-occurs in this one person's notes —
rather than a category. A neural network offers no comparable check without
extra tooling.

**It trains in under a second**, so the whole experiment can be re-run while
you are still thinking about it. For a teaching repository that matters more
than the last few points of accuracy.

**Character n-grams do the work a bigger model would be brought in for.** The
notes contain typos, abbreviations and transliterated Marathi. Matching on
fragments means an unseen spelling still lands near the familiar one, with no
pretrained embedding involved.

## Cost

A few points of accuracy, probably. A sentence-embedding model would likely
handle `Household` versus `Food` better, since that boundary is semantic
rather than lexical — and it is the single largest error in the confusion
matrix. Nobody has measured it here, so this is a belief rather than a
finding, and it is the obvious next experiment.
