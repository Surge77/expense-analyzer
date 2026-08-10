"""Fetch the raw file for a source and hand back exactly what it contained.

No cleaning happens here — that is `clean.py`'s job, and keeping download
separate from parsing means a schema change never sends anything over the
network.

Nothing downloaded here is ever committed. Public Kaggle datasets carry their
own licences, and a repository is the wrong place to redistribute them. The
files land in kagglehub's cache outside the project.

No Kaggle credentials are required for these datasets. Verified by fetching
both with `HOME` redirected and `KAGGLE_API_TOKEN` blank.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .schemas import StatementSchema, get_schema

DEFAULT_SAMPLE_PATH = Path("data/sample_statement.csv")


@dataclass(frozen=True)
class Source:
    """Where one source's bytes come from.

    `slug` is None for the sample, which is generated locally rather than
    downloaded — that is the whole point of it, so the repo runs offline.
    """

    name: str
    slug: str | None
    pattern: str
    rows: str
    purpose: str


SOURCES: dict[str, Source] = {
    "sample": Source(
        name="sample",
        slug=None,
        pattern="*.csv",
        rows="180",
        purpose="Instant demo. Generated locally, safe to commit, no network.",
    ),
    "household": Source(
        name="household",
        slug="prasad22/daily-transactions-dataset",
        pattern="*.csv",
        rows="2,461",
        purpose="Labelled benchmark. The only source with ground-truth categories.",
    ),
    "bank": Source(
        name="bank",
        slug="apoorvwatsky/bank-transaction-data",
        pattern="*.xlsx",
        rows="116,201",
        purpose="Parser stress test. Real, messy, ten accounts, five years.",
    ),
}


def get_source(name: str) -> Source:
    """Look up a source by name, with a message that lists the options."""
    try:
        return SOURCES[name]
    except KeyError:
        options = ", ".join(sorted(SOURCES))
        raise KeyError(f"unknown source {name!r}; expected one of: {options}") from None


STALE_TOKEN_HINT = """\
Kaggle rejected the request while a credentials file is present.

These datasets are public and need no credentials at all, so the usual cause
is an expired or revoked token being sent instead of nothing. An invalid
token fails where no token would have succeeded.

Delete the credentials and try again:
    {locations}
"""


def _credential_locations() -> list[Path]:
    """Files kagglehub reads a token from, in the order it looks."""
    home = Path.home() / ".kaggle"
    return [home / "access_token", home / "kaggle.json"]


def _download_error(source: "Source", error: Exception) -> Exception:
    """Turn an opaque HTTP failure into something actionable."""
    present = [path for path in _credential_locations() if path.exists()]
    if present:
        locations = "\n    ".join(str(path) for path in present)
        return RuntimeError(
            f"could not download {source.slug!r}: {error}\n\n"
            + STALE_TOKEN_HINT.format(locations=locations)
        )
    return RuntimeError(
        f"could not download {source.slug!r}: {error}\n"
        "These datasets are public; check your network connection."
    )


def download(name: str) -> Path:
    """Download a source and return the file itself, not its directory.

    Imports kagglehub lazily so that running against the local sample never
    pays the import cost, and so a machine with no network can still use the
    pipeline end to end.
    """
    source = get_source(name)
    if source.slug is None:
        raise ValueError(
            f"source {name!r} is generated locally, not downloaded. "
            "Run: python scripts/make_sample.py"
        )

    import kagglehub

    try:
        directory = Path(kagglehub.dataset_download(source.slug))
    except Exception as error:
        raise _download_error(source, error) from error

    matches = sorted(directory.rglob(source.pattern))
    if not matches:
        raise FileNotFoundError(f"no {source.pattern} inside {directory} for source {name!r}")
    return matches[0]


def read_file(path: Path) -> pd.DataFrame:
    """Read a CSV or Excel file as text, with no type coercion at all.

    `dtype=str` is deliberate. Letting pandas infer here would silently parse
    `05/07/26` as a date using its own month-first rules, before `clean.py`
    has had the chance to apply the day-first rule that Indian statements
    need. Wrong dates, no error.
    """
    if path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str)
    else:
        frame = pd.read_csv(path, dtype=str)

    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def load_raw(name: str, path: Path | None = None) -> tuple[pd.DataFrame, StatementSchema]:
    """Return the raw frame for a source together with the schema that reads it.

    Pass `path` to point at your own export while still using a known schema —
    this is how `--statement my_statement.csv` works.
    """
    schema = get_schema(name)

    if path is None:
        path = DEFAULT_SAMPLE_PATH if name == "sample" else download(name)

    if not path.exists():
        raise FileNotFoundError(
            f"no file at {path}\n"
            "If you meant the bundled sample, generate it first:\n"
            "    python scripts/make_sample.py"
        )

    frame = read_file(path)
    missing = [column for column in schema.required_columns() if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing columns required by schema {schema.name!r}: "
            f"{', '.join(missing)}\nFound: {', '.join(frame.columns)}"
        )
    return frame, schema


def describe_sources() -> str:
    """A table of what each source is for. Used by `--list-sources`."""
    lines = [f"{'source':<12}{'rows':>9}  purpose"]
    lines.append("-" * 78)
    for source in SOURCES.values():
        lines.append(f"{source.name:<12}{source.rows:>9}  {source.purpose}")
    return "\n".join(lines)
