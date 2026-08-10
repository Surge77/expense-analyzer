# Architecture decision records

Short notes on decisions that are not obvious from the code, written at the
time so the reasoning survives.

Each records the situation, what was chosen, and what it cost. A decision with
no downside listed is usually one that was not thought about hard enough.

| # | Decision |
| --- | --- |
| [0001](0001-rules-before-a-model.md) | Build keyword rules first, and measure them before reaching for a model |
| [0002](0002-logistic-regression-not-a-neural-network.md) | TF-IDF and logistic regression rather than a neural network |
| [0003](0003-datasets-are-not-committed.md) | Download datasets on demand instead of committing them |
| [0004](0004-lint-but-do-not-format.md) | Lint with ruff, but do not enforce `ruff format` |
| [0005](0005-drop-rows-without-a-note.md) | Exclude unlabellable rows from the benchmark rather than scoring them |
| [0006](0006-report-three-splits.md) | Report three split strategies instead of one headline number |
