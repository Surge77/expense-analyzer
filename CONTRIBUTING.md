# Contributing

Thanks for taking a look. This is a teaching repository as much as a working
one, so **a change that is harder to read is not an improvement**, even if it
is faster or shorter.

## Setup

```bash
git clone https://github.com/Surge77/expense-analyzer.git
cd expense-analyzer
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

`-e` installs the package in editable mode: your edits under `src/` take
effect immediately, with no reinstall and no `sys.path` juggling.

Check it worked:

```bash
python scripts/make_sample.py
python -m expense_analyzer
pytest
```

## Before you open a pull request

All four must pass. CI runs the same commands, so a green local run means a
green build.

```bash
ruff check .                            # lint
pyright                                 # types
pytest --cov --cov-fail-under=90        # tests and coverage
python -m expense_analyzer              # the pipeline still runs
```

Integration tests download real data and are opt-in:

```bash
pytest -m integration
```

## The rules of the codebase

**Write the failing test first.** Then the smallest change that passes it. If
you cannot write a test that fails without your change, it is worth asking
what the change is for.

**No file over 300 lines.** Split by responsibility instead. `analyze.py`
aggregates and never plots; `plots.py` draws and never aggregates. That
separation is why the aggregations are testable.

**Comment the *why*, never the *what*.** `frame.dropna(subset=["date"])` does
not need a comment saying it drops null dates. It needs one saying statement
footers have no parseable date, which is why coercing to NaT removes them
without a special case.

**Do not extract a helper until there are three callers.** Duplication is
cheaper to read than a premature abstraction.

**Warnings are errors.** If a dependency emits a `DeprecationWarning`, the
suite fails. Ignore it by message, named to the specific warning, with a
comment saying when it can be removed — never blanket-disable.

## Especially welcome

**New `CATEGORY_RULES` keywords.** The most useful contribution. Add to
`src/expense_analyzer/categorize.py` with a test case in
`tests/test_categorize.py` showing a real narration it matches.

Rules are checked top to bottom and **the first match wins**, so ordering is
load-bearing. `Transfer` sits below `Income` on purpose: `IMPS-CASHBACK
CREDIT` would otherwise be filed as a transfer. If you add a rule that could
collide with an existing one, pin the precedence with a test.

**A new bank's export format.** Add a `StatementSchema` in
`src/expense_analyzer/data/schemas.py`. Two shapes are supported: paired
withdrawal/deposit columns, or one amount column plus a direction flag. You
should not need to touch `clean.py`.

**Please redact real narrations** in tests and issues. Replace account
numbers and UPI handles — `UPI-9876543210@ybl` is somebody's phone number.

## Commits

[Conventional commits](https://www.conventionalcommits.org/):

```
feat(categorize): add rules for Zepto and Instamart
fix(clean): parse dates that arrive with a time component
docs(readme): correct the macro F1 figure
test(analyze): cover the zero-income savings rate guard
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`,
`ci`. One logical change per commit.

Explain *why* in the body, not what — the diff already shows what.

## Branches

Branch off `develop`, not `main`.

```
feature/<short-description>
fix/<short-description>
docs/<short-description>
```

## Reporting a bug

Please include the command you ran, what you expected, what happened, and
your Python version. **Never paste a real statement.** A redacted two-row CSV
that reproduces the problem is ideal.

## Questions

Open an issue with the question template. "The README was confusing here" is
a genuinely useful bug report for this project.
