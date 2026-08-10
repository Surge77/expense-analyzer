# Data dictionary

## The tidy frame

What every source becomes after `clean.clean_statement`. This is the only
shape the rest of the codebase knows about.

| column | type | meaning |
| --- | --- | --- |
| `date` | `datetime64` | Transaction date. Never null — unparseable rows are dropped. |
| `month` | `Period[M]` | Derived. Used for monthly grouping. |
| `day_name` | `str` | Derived, e.g. `Monday`. The finest time signal available. |
| `is_weekend` | `bool` | Derived. Saturday or Sunday. |
| `narration` | `str` | Whatever the source printed. May be empty. |
| `amount` | `float` | **Signed**: spending negative, income positive. Never zero. |
| `category` | `str` | Added by `categorize.add_categories`. |
| `account` | `str` | Only when the source has several accounts. Quote stripped. |
| `label` | `str` | Ground-truth category. Only the `household` source. |

Rows with `amount == 0` are dropped: a zero-value row is a statement artefact,
not a transaction.

## Source formats

### `sample` — generated locally

HDFC export format, produced by `scripts/make_sample.py`. Seeded, so it is
byte-identical on every machine.

| column | notes |
| --- | --- |
| `Date` | `dd/mm/yy`. **Day first** — `05/07/26` is 5 July, not 7 May. |
| `Narration` | e.g. `UPI-SWIGGY-swiggy@icici-512334-ORDER` |
| `Withdrawal Amt.` | Text, thousands-separated. Blank when the row is a credit. |
| `Deposit Amt.` | Text, thousands-separated. Blank when the row is a debit. |
| `Chq./Ref.No.`, `Value Dt`, `Closing Balance` | Present, unused. |

### `household` — the labelled benchmark

[prasad22/daily-transactions-dataset](https://www.kaggle.com/datasets/prasad22/daily-transactions-dataset).
2,461 rows, January 2015 to September 2018. Not redistributed here.

| column | notes |
| --- | --- |
| `Date` | `dd/mm/yyyy`, sometimes carrying a time. |
| `Note` | Free text a human wrote for themselves. **521 rows are empty.** |
| `Amount` | Always positive; direction comes from the next column. |
| `Income/Expense` | `Expense` (2,176), `Transfer-Out` (160), `Income` (125). |
| `Category` | **Ground truth.** 50 distinct values before preparation. |
| `Subcategory` | Present, unused — using it would leak the label. |
| `Mode` | 12 values, e.g. `Cash`. Present, unused. |
| `Currency` | Always `INR`. |

### `bank` — the parser stress test

[apoorvwatsky/bank-transaction-data](https://www.kaggle.com/datasets/apoorvwatsky/bank-transaction-data).
116,201 rows, 10 accounts, January 2015 to March 2019. Not redistributed here.

| column | notes |
| --- | --- |
| `Account No` | **Carries a trailing quote**, e.g. `409000611074` followed by an apostrophe. Stripped on clean. |
| `DATE` | Already typed, with a time component: `2017-06-29 00:00:00`. |
| `TRANSACTION DETAILS` | **Truncated mid-word**: `FDRL/INTERNAL FUND TRANSFE`. 2,499 rows are blank. |
| `WITHDRAWAL AMT` | No full stop, unlike the HDFC export's `Withdrawal Amt.` |
| `DEPOSIT AMT` | Ranges over seven orders of magnitude. |
| `.` | A junk column. Ignored. |

This is corporate accounting data, not personal spending — the median debit is
around 47,000 rupees and the largest is 459 million. The keyword rules match
**1.2%** of it, which is why it is used to test the parser rather than the
categoriser.

## Benchmark preparation

`benchmark.load_benchmark` turns the household source into a scored split.

| step | effect |
| --- | --- |
| Drop rows with an empty note | 2,461 to 1,940 |
| Fold classes under 20 examples into `Other` | 38 classes to 12 |
| Stratified split, seed 42 | 1,455 train / 485 test |

Final classes: `Apparel`, `Beauty`, `Family`, `Food`, `Gift`, `Health`,
`Household`, `Investment`, `Other`, `Salary`, `Transportation`,
`subscription`.
