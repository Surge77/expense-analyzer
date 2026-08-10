# Architecture

## The shape

Four stages, each depending only on the one before it.

```
 data/loaders.py     download or read a file, coerce nothing
        |
        v
 data/schemas.py     which columns this source uses
        |
        v
   clean.py          one tidy row per transaction, signed amounts
        |
        v
 categorize.py       narration text -> a category label
        |
        +--------------------------+
        v                          v
  analyze.py                  benchmark.py     the labelled split
  aggregations                     |
        |                          v
        v                     model.py         TF-IDF + logistic regression
   plots.py                        |
   four PNGs                       v
        |                     evaluate.py      scores, confusion matrices
        +--------------------------+
                    |
                    v
                 cli.py
```

## Why the stages are separate

**`analyze` never plots and `plots` never aggregates.** This is the most
useful boundary in the codebase. Aggregation is arithmetic that must be
correct; plotting is drawing that mostly cannot be asserted on. Keeping them
apart is why every aggregation has a test with a hand-checkable number, while
the plotting tests only check that files appear and figures get closed.

**Nothing downstream re-parses anything.** Everything a bank export gets wrong
is fixed in `clean.py` and nowhere else. Later stages may assume dates are
dates and amounts are floats. When a number looks wrong, there is exactly one
file to look in.

**Loading is separate from parsing.** `loaders.py` fetches bytes and reads
them as text with no type coercion at all. That is deliberate: letting pandas
infer types on read would apply its own month-first date rule before
`clean.py` gets the chance to apply the day-first rule Indian statements need.
Wrong dates, and no error to tell you.

## The two central data decisions

**Amounts are signed.** Spending negative, income positive, in one column. The
alternative — separate withdrawal and deposit columns — forces every
downstream function to handle direction. With one signed column, net position
is a single `.sum()`, and `spending_only()` is three lines.

**Schemas are data, not code.** Every bank names its columns differently, and
two structurally different shapes exist in the wild: paired withdrawal/deposit
columns, or one amount column plus a direction flag. `StatementSchema`
describes both, so supporting a new bank means adding a frozen dataclass, not
editing the parser.

## Rule ordering is load-bearing

`CATEGORY_RULES` is a dict, Python preserves insertion order, and **the first
match wins**. That makes ordering a real design decision:

- `Subscriptions` sits above `Bills`, so Netflix autopay is a subscription.
- `Transfer` sits below `Income`, so `IMPS-CASHBACK CREDIT` and
  `NEFT-...-SALARY CREDIT` are income rather than transfers.

Both orderings are pinned by tests, because reordering the dict changes
results silently and no exception is ever raised.

## Where the machine learning fits

`benchmark.py` is deliberately not part of the pipeline. The pipeline
categorises *your* statement using rules; the benchmark answers a different
question — how good is any categoriser — and needs labelled data the pipeline
never has.

They meet at exactly one place: `benchmark.predict_rules` runs the same
`categorize()` the pipeline uses, translated into the benchmark's vocabulary.
That translation lives in `RULE_TO_BENCHMARK` and is deliberately generous to
the rules, because a baseline is only meaningful if it is as strong as it can
honestly be made.

## Testing strategy

| Layer | Approach |
| --- | --- |
| `clean` | Hand-built frames with known-wrong inputs: footers, blanks, ambiguous dates |
| `categorize` | Real narrations, with rule precedence pinned explicitly |
| `analyze` | Fixtures whose totals can be checked mentally |
| `plots` | Files appear; an autouse fixture fails any test leaking a figure |
| `cli` | Argument parsing, and the error messages a new user hits first |
| `data` | Network stubbed, so the suite is offline and fast |
| real data | Marked `integration`, opt-in, parses all 116,201 rows |

Unit tests never touch the network. The integration suite exists because 180
synthetic rows cannot exercise what a real export does to a parser — and every
assertion in it corresponds to something that was actually wrong.
