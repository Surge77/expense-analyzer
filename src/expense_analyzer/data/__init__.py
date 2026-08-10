"""Where the data comes from, and how each source's columns are named."""

from .loaders import SOURCES, Source, describe_sources, download, load_raw, read_file
from .schemas import (
    HDFC_SAMPLE,
    KAGGLE_BANK,
    KAGGLE_HOUSEHOLD,
    SCHEMAS,
    StatementSchema,
    get_schema,
)

__all__ = [
    "HDFC_SAMPLE",
    "KAGGLE_BANK",
    "KAGGLE_HOUSEHOLD",
    "SCHEMAS",
    "SOURCES",
    "Source",
    "StatementSchema",
    "describe_sources",
    "download",
    "get_schema",
    "load_raw",
    "read_file",
]
