# 0001 — Rules before a model

**Status:** accepted

## Context

The task is turning `UPI-SWIGGY-swiggy@icici-512334` into `Food`. That mapping
is domain knowledge which exists nowhere in the data, so something has to
supply it. A classifier is the obvious modern answer.

## Decision

Write keyword rules first. Measure them against ground truth. Only then train
a model, and report both side by side.

## Why

**A model with nothing to beat is unfalsifiable.** "87% accuracy" means
nothing on its own. Against a majority-class floor of 42.9% it means
something, and against rules scoring 13.4% it means something else again.

**Rules are the correct answer in their own domain.** On bank narrations they
are precise, instant, need no training data, and can be explained to a
non-technical person line by line. Reaching for a model first would have
skipped that entirely.

**The comparison turned out to be the actual finding.** The rules score
*below* the majority baseline on the benchmark — not because rules are bad,
but because they were built for bank narrations and the benchmark holds a
human's private shorthand. That measures transfer between two text
distributions. It is a more interesting and more honest result than "the model
won".

## Cost

Two systems to maintain instead of one, and a translation table
(`RULE_TO_BENCHMARK`) between two category vocabularies that would not exist
otherwise. The table is a judgment call, and a different mapping would move
the rules' score by a few points.
