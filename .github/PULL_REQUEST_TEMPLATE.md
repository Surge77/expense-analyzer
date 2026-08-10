## What does this change?

<!-- One or two sentences. The diff shows what; explain why. -->

## Why?

<!-- What problem does this solve? Link an issue if there is one. -->

## How was it verified?

<!-- Paste the output, not a claim that it passed. -->

```
ruff check .
pyright
pytest --cov --cov-fail-under=90
python -m expense_analyzer
```

## Checklist

- [ ] A test fails without this change
- [ ] `ruff check .` and `pyright` are clean
- [ ] `pytest` passes and coverage is at or above 90%
- [ ] No file exceeds 300 lines
- [ ] Comments explain *why*, not *what*
- [ ] No real account numbers, UPI handles or narrations anywhere in the diff
- [ ] If categorisation changed, `python scripts/run_benchmark.py` was re-run
      and `docs/results.md` updated
