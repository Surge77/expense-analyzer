# expense-analyzer

Turns a bank statement into five sentences about your spending habits.

The bank already tells you *who you paid* — one row at a time, hundreds of
times. It never tells you *what your habits are*. Going from 400 facts to 5
conclusions is the whole project.

```
raw CSV  ->  clean  ->  categorize  ->  aggregate  ->  charts + findings
(messy)      (typed)    (labelled)      (summarised)   (answers)
```

No machine learning. The skill on show is data handling, which every later
project silently depends on.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts/make_sample.py      # writes data/sample_statement.csv
python run.py                      # prints every number, saves 4 charts
pytest                             # 17 tests
```

Then swap in your own statement:

```powershell
python run.py --statement data/my_statement.csv
```

## Your data stays local

`data/` is gitignored except the generated sample. A real statement carries
your account number, running balance and complete transaction history —
pushing it to a public repo puts it in git history permanently, and deleting
the file later does not remove it. The committed sample is fabricated by
`scripts/make_sample.py`, so the repo is safe to share as-is.

## Layout

| Path | Does |
|------|------|
| `scripts/make_sample.py` | Generates fake HDFC-format data. Seeded, reproducible |
| `src/clean.py` | Stage 1. Parses rupee strings, day-first dates, drops footers |
| `src/categorize.py` | Stage 2. Keyword rules, coverage reporting |
| `src/analyze.py` | Stage 3. Aggregations only, no plotting |
| `src/plots.py` | Stage 4. Four PNGs into `reports/` |
| `run.py` | Whole pipeline, one command |
| `tests/` | Pins the two decisions that fail silently |

## The three problems this actually solves

**1. The numbers are text.** Banks print `1,347.00`, so the column arrives
as a string. `parse_amount` strips separators and treats blanks as zero.

**2. The dates are ambiguous.** `05/07/26` is 5 July in India and 7 May to
pandas' default parser. Getting this wrong produces wrong monthly totals and
**no error message**. `dayfirst=True` is pinned by a test.

**3. The merchant is not the category.** `UPI-SWIGGY-swiggy@icici-512334`
has to become `Food`. That mapping is domain knowledge that exists nowhere
in the data, so it is hand-written in `CATEGORY_RULES` — and it is a
judgment call. Is Amazon `Shopping` or `Groceries`? Is a transfer to a
friend `Food` because you split dinner, or `Transfer`? Decide, then defend
the decision.

## The loop that is the project

```powershell
python run.py
```

Read the "Rule coverage" block, then the unmatched narrations under it. Add
keywords to `CATEGORY_RULES` in `src/categorize.py`. Re-run. Repeat until
uncategorised is under ~5% **by value**.

The sample ships with roughly 8% unmatched on purpose — a mix of raw UPI
phone numbers, payment-gateway codes (`IN*RAZ*` is Razorpay, the processor,
not the shop) and bare NEFT references. Real statements look exactly like
this. Closing that gap is the exercise.

Coverage is reported by row count **and** by rupees, because 5% of rows can
easily be 40% of the money.

## Findings template

Fill this in from your own statement and put it at the top of the notebook.
This is what you present — not the code.

1. `<Category>` is Rs `<x>`/month, `<y>`% of spend — more than `<comparison>`.
2. `<z>`% of `<category>` spending happens at weekends, suggesting `<habit>`.
3. Spend rose `<n>`% from `<month>` to `<month>`, driven by `<category>`.
4. Median transaction is Rs `<m>` — bled by frequency, not by large purchases.
5. Savings rate is `<a>`%; cutting `<category>` alone would take it to `<b>`%.

Two rules that matter more than the charts:

- **One number and one trade-off you can defend.** "I put Amazon under
  Shopping, not Groceries, because I could not separate Fresh orders from
  the rest without order-level data" is worth more than another chart.
- **Show one thing that failed.** A section titled "what did not work" makes
  everything else more believable.

## Known limits

- **No time of day.** Statements carry a date, not a clock time. Day-of-week
  and weekend/weekday are derivable; "spending after 9pm" is not.
- **Cash is invisible.** An ATM withdrawal shows as one lump. Where that
  cash went is unknowable from this data.
- **Split payments look like one merchant.** Paying a friend back for a
  shared dinner reads as a person-to-person transfer, not as food.
- **Rules are brittle by design.** A merchant renaming itself breaks a rule
  silently. That is the argument for the classifier in stretch goal 3.

## Stretch goals, in difficulty order

1. **Recurring subscription detector** — already in `analyze.recurring_candidates`.
   Extend it to flag charges you have not used.
2. **Anomaly flagging** — already in `analyze.anomalies` at 3x the category
   median. Justify the threshold, or replace it with a z-score.
3. **Replace rules with a classifier** — hand-label 200 narrations, train
   Naive Bayes on the text, compare accuracy against the rule baseline. You
   can only tell whether the model is worth it because you measured the
   rules first. This is the bridge to the spam-classifier project.
4. **Streamlit UI** — upload a CSV, see the charts. Demoable in 30 seconds.
