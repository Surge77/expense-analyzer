"""Bank statement to spending habits.

The pipeline runs in four stages, each in its own module, each depending only
on the one before it:

    clean      raw CSV        -> one tidy row per transaction
    categorize narration text -> a category label
    analyze    labelled rows  -> aggregates you could put in a sentence
    plots      aggregates     -> PNG charts

Import the stage you need:

    >>> from expense_analyzer import analyze, categorize
    >>> from expense_analyzer.clean import load_and_clean
"""

__version__ = "0.1.0"

# No `__all__` listing the submodules. They are not imported here on purpose:
# `plots` pulls in matplotlib, and paying that import cost just to call
# `clean.load_and_clean` would be rude to anyone using this as a library.
# `from expense_analyzer import analyze` still works — Python imports a
# submodule on demand.
