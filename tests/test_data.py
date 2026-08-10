"""Schemas and loaders.

Nothing here touches the network. The download path is exercised with a stub
so the suite stays fast and works offline; the real fetch is covered by the
integration tests.
"""

from pathlib import Path

import pandas as pd
import pytest

from expense_analyzer.data import loaders, schemas


class TestStatementSchema:
    def test_rejects_a_schema_that_declares_neither_amount_shape(self):
        with pytest.raises(ValueError, match="withdrawal\\+deposit or amount\\+direction"):
            schemas.StatementSchema(name="broken", date="Date", narration="Note")

    def test_rejects_a_schema_that_declares_both_amount_shapes(self):
        """Both set means the reader has to guess which one is authoritative."""
        with pytest.raises(ValueError):
            schemas.StatementSchema(
                name="broken",
                date="Date",
                narration="Note",
                withdrawal="W",
                deposit="D",
                amount="A",
                direction="Dir",
            )

    def test_paired_and_signed_schemas_report_their_shape(self):
        assert schemas.HDFC_SAMPLE.is_paired is True
        assert schemas.KAGGLE_HOUSEHOLD.is_paired is False

    def test_required_columns_cover_the_declared_shape(self):
        assert schemas.HDFC_SAMPLE.required_columns() == [
            "Date",
            "Narration",
            "Withdrawal Amt.",
            "Deposit Amt.",
        ]
        assert schemas.KAGGLE_HOUSEHOLD.required_columns() == [
            "Date",
            "Note",
            "Amount",
            "Income/Expense",
        ]

    def test_is_frozen_so_one_load_cannot_reconfigure_another(self):
        with pytest.raises(Exception):  # noqa: B017 - dataclasses raises FrozenInstanceError
            schemas.HDFC_SAMPLE.date = "Something Else"  # type: ignore[misc]

    def test_get_schema_names_the_alternatives_when_asked_for_a_bad_one(self):
        with pytest.raises(KeyError, match="bank, household, sample"):
            schemas.get_schema("nope")


class TestSources:
    def test_every_schema_has_a_matching_source(self):
        """The two registries are keyed by the same names on purpose; a
        mismatch would fail only at runtime, on the one path that downloads."""
        assert set(loaders.SOURCES) == set(schemas.SCHEMAS)

    def test_get_source_names_the_alternatives_when_asked_for_a_bad_one(self):
        with pytest.raises(KeyError, match="bank, household, sample"):
            loaders.get_source("nope")

    def test_refuses_to_download_the_locally_generated_sample(self):
        with pytest.raises(ValueError, match=r"make_sample\.py"):
            loaders.download("sample")

    def test_describe_sources_lists_every_source(self):
        described = loaders.describe_sources()
        for name in loaders.SOURCES:
            assert name in described


class TestReadFile:
    def test_reads_csv_without_coercing_types(self, tmp_path):
        """Everything must arrive as text. If pandas infers here it applies
        its own month-first date rule before clean.py can say otherwise."""
        path = tmp_path / "s.csv"
        path.write_text("Date,Amount\n05/07/26,1234\n", encoding="utf-8")

        frame = loaders.read_file(path)

        assert frame["Date"].iloc[0] == "05/07/26"
        assert frame["Amount"].iloc[0] == "1234"

    def test_strips_whitespace_from_column_names(self, tmp_path):
        path = tmp_path / "s.csv"
        path.write_text("  Date ,Amount\n05/07/26,1\n", encoding="utf-8")

        assert list(loaders.read_file(path).columns) == ["Date", "Amount"]

    def test_reads_excel_for_xlsx_sources(self, tmp_path):
        path = tmp_path / "s.xlsx"
        pd.DataFrame({"DATE": ["2017-06-29"], "X": ["1"]}).to_excel(path, index=False)

        assert list(loaders.read_file(path).columns) == ["DATE", "X"]


class TestLoadRaw:
    def test_explains_how_to_generate_the_sample_when_it_is_absent(self, tmp_path):
        with pytest.raises(FileNotFoundError, match=r"make_sample\.py"):
            loaders.load_raw("sample", tmp_path / "absent.csv")

    def test_rejects_a_file_missing_columns_the_schema_needs(self, tmp_path):
        """A silently wrong column name would produce an empty frame and a
        confident zero, so this fails loudly and says which column is gone."""
        path = tmp_path / "s.csv"
        path.write_text("Date,Narration\n05/07/26,UPI-SWIGGY\n", encoding="utf-8")

        with pytest.raises(ValueError, match=r"Withdrawal Amt\."):
            loaders.load_raw("sample", path)

    def test_returns_the_frame_with_the_schema_that_reads_it(self, tmp_path):
        path = tmp_path / "s.csv"
        path.write_text(
            "Date,Narration,Withdrawal Amt.,Deposit Amt.\n05/07/26,UPI-SWIGGY,347.00,\n",
            encoding="utf-8",
        )

        frame, schema = loaders.load_raw("sample", path)

        assert len(frame) == 1
        assert schema is schemas.HDFC_SAMPLE

    def test_downloads_when_no_path_is_given_for_a_remote_source(self, tmp_path, monkeypatch):
        path = tmp_path / "household.csv"
        path.write_text(
            "Date,Mode,Category,Subcategory,Note,Amount,Income/Expense,Currency\n"
            "20/09/2018,Cash,Food,snacks,Idli,60,Expense,INR\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(loaders, "download", lambda name: path)

        frame, schema = loaders.load_raw("household")

        assert schema is schemas.KAGGLE_HOUSEHOLD
        assert frame["Note"].iloc[0] == "Idli"


class TestDownload:
    def test_picks_the_matching_file_out_of_the_downloaded_directory(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
        wanted = tmp_path / "data.csv"
        wanted.write_text("a,b\n1,2\n", encoding="utf-8")

        fake = type("FakeHub", (), {"dataset_download": staticmethod(lambda slug: str(tmp_path))})
        monkeypatch.setitem(__import__("sys").modules, "kagglehub", fake)

        assert loaders.download("household") == wanted

    def test_reports_clearly_when_the_download_holds_no_matching_file(
        self, tmp_path, monkeypatch
    ):
        (tmp_path / "readme.txt").write_text("nothing useful", encoding="utf-8")
        fake = type("FakeHub", (), {"dataset_download": staticmethod(lambda slug: str(tmp_path))})
        monkeypatch.setitem(__import__("sys").modules, "kagglehub", fake)

        with pytest.raises(FileNotFoundError, match=r"no \*\.csv"):
            loaders.download("household")


class TestDownloadFailureGuidance:
    """A stale token is worse than no token: Kaggle rejects the request that
    would have succeeded anonymously. The error has to say so, because the
    raw failure is an opaque 400."""

    @staticmethod
    def _failing_kagglehub(monkeypatch):
        def explode(slug):
            raise RuntimeError("400 Client Error: Bad Request")

        fake = type("FakeHub", (), {"dataset_download": staticmethod(explode)})
        monkeypatch.setitem(__import__("sys").modules, "kagglehub", fake)

    def test_points_at_the_credentials_file_when_one_exists(self, tmp_path, monkeypatch):
        credentials = tmp_path / ".kaggle"
        credentials.mkdir()
        (credentials / "access_token").write_text("KGAT_dead", encoding="utf-8")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        self._failing_kagglehub(monkeypatch)

        with pytest.raises(RuntimeError, match="expired or revoked"):
            loaders.download("household")

    def test_suggests_the_network_when_no_credentials_are_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        self._failing_kagglehub(monkeypatch)

        with pytest.raises(RuntimeError, match="check your network"):
            loaders.download("household")


class TestSignedAmountShape:
    """The household source has one Amount column plus a direction flag."""

    def test_direction_flag_decides_the_sign_not_the_magnitude(self):
        from expense_analyzer.clean import clean_statement

        raw = pd.DataFrame(
            {
                "Date": ["20/09/2018", "21/09/2018", "22/09/2018"],
                "Note": ["Idli", "Salary", "Moved to savings"],
                "Amount": ["60", "46000", "5000"],
                "Income/Expense": ["Expense", "Income", "Transfer-Out"],
                "Category": ["Food", "Salary", "Money transfer"],
            }
        )

        tidy = clean_statement(raw, schemas.KAGGLE_HOUSEHOLD)

        by_note = dict(zip(tidy["narration"], tidy["amount"], strict=True))
        assert by_note["Idli"] == -60.0
        assert by_note["Salary"] == 46000.0
        # Transfer-Out is money leaving, so it signs negative like an expense.
        assert by_note["Moved to savings"] == -5000.0

    def test_carries_the_ground_truth_label_through(self):
        from expense_analyzer.clean import clean_statement

        raw = pd.DataFrame(
            {
                "Date": ["20/09/2018"],
                "Note": ["Idli"],
                "Amount": ["60"],
                "Income/Expense": ["Expense"],
                "Category": ["Food"],
            }
        )

        tidy = clean_statement(raw, schemas.KAGGLE_HOUSEHOLD)

        assert tidy["label"].iloc[0] == "Food"


class TestAccountHandling:
    def test_strips_the_stray_quote_excel_leaves_on_account_numbers(self):
        from expense_analyzer.clean import clean_statement

        raw = pd.DataFrame(
            {
                "Account No": ["409000611074'"],
                "DATE": ["2017-06-29 00:00:00"],
                "TRANSACTION DETAILS": ["TRF FROM  Indiaforensic SERVICES"],
                "WITHDRAWAL AMT": [None],
                "DEPOSIT AMT": ["1000000"],
            }
        )

        tidy = clean_statement(raw, schemas.KAGGLE_BANK)

        assert tidy["account"].iloc[0] == "409000611074"


def test_default_sample_path_is_relative_to_the_working_directory():
    """Anchoring to __file__ would point into site-packages once installed."""
    assert not Path(loaders.DEFAULT_SAMPLE_PATH).is_absolute()
