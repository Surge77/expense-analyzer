# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-08-10

The headline number from 1.0.0 did not survive being interrogated. This
release reports what it actually measures, and the honest version turned out
to be more interesting.

### Added

- **Three split strategies** — `random`, `grouped` and `temporal` — reported
  side by side wherever a score appears. They differ by fifteen points of
  accuracy on identical data with an identical model.
- **Leakage breakdown.** 56.7% of the random test set is notes already present
  in training; the model scores 96.4% on those and 74.8% on genuinely unseen
  text. Both figures are published.
- **In-domain rule baseline.** Roughly thirty keywords written from the
  training split only. This is the fair comparison: the previous baseline used
  bank-narration rules on handwritten notes, which confounded "a model beats
  rules" with "in-domain beats out-of-domain".
- **Hybrid categoriser** — rules first, model where they abstain. On genuinely
  unseen text it beats both (73.9% / 0.567 against the model's 72.1% / 0.460).
- **Confidence thresholding.** `model.predict_with_confidence` abstains below
  a cutoff, and `evaluate.coverage_accuracy_curve` shows the trade: answering
  82% of rows raises accuracy from 87% to 94%.
- **`--categorizer {rules,model,hybrid}`** on the CLI, so the classifier is
  used and not merely measured. Warns when pointed outside its domain.
- **Property-based tests** (hypothesis) over the parsing functions, where the
  failure mode is a plausible wrong number rather than an exception.
- `py.typed`, Dependabot, CodeQL, `.editorconfig`, `CITATION.cff`, and a
  cached dataset download in CI.

### Changed

- **The finding inverted.** On genuinely unseen text, hand-written rules beat
  the classifier on macro F1. The model wins on accuracy, which the large
  classes dominate. The recommendation is now conditional and measured:
  rules-then-model for novel descriptions, model alone for recurring spending.
- Baselines moved from `benchmark.py` to `baselines.py`, keeping both files
  under the 300-line limit.
- README, MODEL_CARD and docs/results.md all lead with the split-dependent
  numbers rather than a single figure.

### Fixed

- **In-domain rule ordering.** `Transportation` matches the bare substring
  `place`, which swallowed `workplace` — the only `Salary` note in the data.
  Caught by a test; `Salary` now sits above it, pinned.
- pytest-cov's coverage-shortfall warning no longer becomes a pytest
  INTERNALERROR under `filterwarnings = ["error"]`.

## [1.0.0] - 2026-08-10

First public release. The pipeline existed before this; what is new is that
its central claim is now measured rather than asserted.

### Added

- **A measured comparison.** Keyword rules, a majority-class floor and a
  TF-IDF + logistic-regression classifier scored on 485 held-out rows of real
  hand-labelled spending. The classifier reaches 87.0% accuracy and 0.769
  macro F1; the rules reach 13.4%. See [docs/results.md](docs/results.md).
- **Real data.** Three sources behind one interface — the generated sample,
  a 2,461-row labelled benchmark, and a 116,201-row real bank export used as
  a parser stress test. Downloaded on demand, never committed.
- **Per-source schemas** (`data/schemas.py`), so a new bank's export format is
  a data change rather than a code change. Two amount shapes are supported.
- **`Transfer` category.** `spending_only` had always filtered it out, but no
  rule produced it, so self-transfers were counted as spending.
- **Multi-account handling.** `savings_rate` refuses to run across several
  accounts; `analyze.for_account` narrows first.
- **Evaluation module** — accuracy, macro F1, per-class report, confusion
  matrices, and the most frequent specific mistakes.
- **`--source`, `--account`, `--list-sources` and `--evaluate`** on the CLI.
- **Packaging.** Installable with `pip install -e .`, runnable as
  `python -m expense_analyzer`.
- **CI** on Python 3.11 and 3.12: lint, types, tests, coverage, an end-to-end
  smoke run and a job that parses the real datasets.
- Documentation: architecture, glossary, data dictionary, model card and
  architecture decision records.

### Fixed

- Date parsing for exports that arrive already typed with a time component
  (`2017-06-29 00:00:00`), which is the entire 116,201-row bank dataset.
- `Transfer` rules now match the truncated stem `internal fund transfe`. Real
  exports truncate mid-word, and the untruncated spelling matched nothing.
- Account numbers stripped of the stray quote Excel leaves behind
  (`409000611074'`).
- `top_features_for` on a two-class model, where scikit-learn stores one
  shared coefficient row rather than one per class.
- A pandas `FutureWarning` from comparing a Series against a plain list.

### Changed

- Layout moved to `src/expense_analyzer/`, removing the notebook's
  `sys.path.append("..")`.
- `pyproject.toml` replaces `requirements.txt` and `pytest.ini`.
- Test coverage went from 25% to 93%, gated at 90%. Warnings are now errors.
- pyright runs as a blocking gate, clean, with `pandas-stubs` doing the work.

### Security

- `.gitignore` extended to cover Kaggle credentials, `.env` files, model
  artifacts and coverage output.
- Download failures now identify a stale Kaggle token, which causes a request
  to fail where sending no credentials at all would have succeeded.

[1.1.0]: https://github.com/Surge77/expense-analyzer/releases/tag/v1.1.0
[1.0.0]: https://github.com/Surge77/expense-analyzer/releases/tag/v1.0.0
