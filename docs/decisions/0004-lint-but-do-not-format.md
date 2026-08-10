# 0004 — Lint with ruff, but do not enforce ruff format

**Status:** accepted

## Context

`ruff format` is the obvious companion to `ruff check`, and enforcing a
formatter removes style arguments from code review entirely.

## Decision

Run `ruff check` in CI as a blocking gate. Do not run `ruff format --check`.

## Why

The formatter reformats the command samples inside module docstrings:

```python
"""Run the whole pipeline and print the numbers you build findings from.

    python -m expense_analyzer
    python -m expense_analyzer --source household
"""
```

`ruff format` de-indents those lines, removing the visual cue that they are
commands rather than prose. In a repository whose purpose is being read, that
is a real loss for no correctness gain.

It also rejoins some deliberately-broken conditions onto a single
100-character line, which is legal and less readable.

## Cost

Style is not mechanically enforced, so review has to mention it occasionally
and contributors have less certainty about house style. Partly mitigated by
`ruff check` covering what actually matters — import order, unused names, line
length — and by `line-length = 100` being set explicitly.

Worth revisiting if the contributor count ever makes this a real friction. At
that point, restructuring the docstrings to survive the formatter would be a
smaller cost than the arguments.
