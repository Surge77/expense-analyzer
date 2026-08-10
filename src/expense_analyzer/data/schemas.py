"""How each source's columns map onto the tidy frame.

Every bank invents its own column names, and the two public datasets this
project uses are shaped differently again. Rather than teach `clean.py` about
each one, the differences live here as data and `clean.py` reads a schema.

Two shapes exist in the wild:

**Paired columns** — a `Withdrawal` column and a `Deposit` column, exactly one
of which is filled per row. Every bank export works this way.

**Signed amount** — one `Amount` column plus a separate flag saying whether
the row was income or expense. Personal expense trackers work this way,
because a human entering a row already knows which it was.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StatementSchema:
    """Column names for one source, plus how to read its amounts.

    Frozen because a schema is a fact about a file format, not state. Sharing
    one mutable schema between two loads is a bug waiting to happen.
    """

    name: str
    date: str
    narration: str

    # Paired shape: both must be set together.
    withdrawal: str | None = None
    deposit: str | None = None

    # Signed shape: both must be set together.
    amount: str | None = None
    direction: str | None = None
    expense_values: tuple[str, ...] = ("Expense",)

    # Optional extras, absent from most exports.
    account: str | None = None
    label: str | None = None

    # Indian statements print dd/mm/yy. Reading that month-first turns 05/07
    # into 5 May instead of 5 July — wrong totals, and no error.
    dayfirst: bool = True

    def __post_init__(self) -> None:
        has_pair = self.withdrawal is not None and self.deposit is not None
        has_signed = self.amount is not None and self.direction is not None

        if has_pair == has_signed:
            raise ValueError(
                f"schema {self.name!r} must set either withdrawal+deposit or "
                "amount+direction, and not both"
            )

    @property
    def is_paired(self) -> bool:
        """True when amounts arrive as separate withdrawal/deposit columns."""
        return self.withdrawal is not None

    def required_columns(self) -> list[str]:
        """Columns that must be present for the source to be readable."""
        columns = [self.date, self.narration]
        if self.is_paired:
            columns += [self.withdrawal, self.deposit]
        else:
            columns += [self.amount, self.direction]
        return [column for column in columns if column is not None]


# The format `scripts/make_sample.py` generates, matching an HDFC export.
HDFC_SAMPLE = StatementSchema(
    name="sample",
    date="Date",
    narration="Narration",
    withdrawal="Withdrawal Amt.",
    deposit="Deposit Amt.",
)

# apoorvwatsky/bank-transaction-data — 116,201 real rows across 10 accounts.
# Note the missing full stops: this export writes "WITHDRAWAL AMT", where the
# HDFC one writes "Withdrawal Amt.". Dates arrive already typed, with a time
# component, which is why `clean.parse_dates` needs its fallback path.
KAGGLE_BANK = StatementSchema(
    name="bank",
    date="DATE",
    narration="TRANSACTION DETAILS",
    withdrawal="WITHDRAWAL AMT",
    deposit="DEPOSIT AMT",
    account="Account No",
)

# prasad22/daily-transactions-dataset — 2,461 real rows from one household's
# expense tracker. The only source carrying a ground-truth `Category`, which
# is what makes measuring the rules possible at all.
KAGGLE_HOUSEHOLD = StatementSchema(
    name="household",
    date="Date",
    narration="Note",
    amount="Amount",
    direction="Income/Expense",
    expense_values=("Expense", "Transfer-Out"),
    label="Category",
)

SCHEMAS: dict[str, StatementSchema] = {
    schema.name: schema for schema in (HDFC_SAMPLE, KAGGLE_BANK, KAGGLE_HOUSEHOLD)
}


def get_schema(name: str) -> StatementSchema:
    """Look up a schema by source name, with a message that lists the options."""
    try:
        return SCHEMAS[name]
    except KeyError:
        options = ", ".join(sorted(SCHEMAS))
        raise KeyError(f"unknown source {name!r}; expected one of: {options}") from None
