"""The command-line entry point.

This is the surface a new user touches first, so its failure modes matter
more than its formatting: a missing file must produce a readable instruction
rather than a traceback.
"""

import pytest

from expense_analyzer import cli


class TestParseArgs:
    def test_defaults_to_the_shipped_sample(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["expense-analyzer"])
        args = cli.parse_args()

        assert args.source == "sample"
        # None means "wherever this source normally lives"; load_frame
        # resolves it, so an explicit --statement can override any source.
        assert args.statement is None
        assert args.account is None
        assert args.reports == cli.DEFAULT_REPORTS
        assert args.top == 10

    def test_accepts_a_named_source_and_account(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv", ["expense-analyzer", "--source", "bank", "--account", "1196428"]
        )
        args = cli.parse_args()

        assert args.source == "bank"
        assert args.account == "1196428"

    def test_rejects_an_unknown_source_at_the_argument_layer(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["expense-analyzer", "--source", "nope"])

        with pytest.raises(SystemExit):
            cli.parse_args()

        assert "invalid choice" in capsys.readouterr().err

    def test_accepts_an_alternative_statement_and_report_directory(self, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["expense-analyzer", "--statement", "other.csv", "--reports", "out", "--top", "3"],
        )
        args = cli.parse_args()

        assert args.statement.name == "other.csv"
        assert args.reports.name == "out"
        assert args.top == 3


class TestMain:
    def test_explains_how_to_create_the_sample_when_the_statement_is_missing(
        self, monkeypatch, tmp_path
    ):
        """A new clone has no data/ contents. The message must say what to run
        next, not raise FileNotFoundError from deep inside pandas."""
        monkeypatch.setattr(
            "sys.argv", ["expense-analyzer", "--statement", str(tmp_path / "absent.csv")]
        )

        with pytest.raises(SystemExit) as exit_info:
            cli.main()

        assert "make_sample.py" in str(exit_info.value)

    def test_runs_end_to_end_and_writes_every_chart(self, monkeypatch, tmp_path, capsys):
        statement = tmp_path / "statement.csv"
        statement.write_text(
            "Date,Narration,Withdrawal Amt.,Deposit Amt.\n"
            "01/05/26,UPI-SWIGGY-order-111111,347.00,\n"
            "02/05/26,UPI-DMART READY-222222,1240.50,\n"
            "03/05/26,NEFT-ACME-SALARY CREDIT,,32000.00\n"
            "04/05/26,UPI-9876543210@ybl-PAYMENT-444444,88.00,\n"
            "10/06/26,UPI-SWIGGY-order-333333,412.00,\n",
            encoding="utf-8",
        )
        reports = tmp_path / "reports"
        monkeypatch.setattr(
            "sys.argv",
            ["expense-analyzer", "--statement", str(statement), "--reports", str(reports)],
        )

        cli.main()

        printed = capsys.readouterr().out
        assert "Statement" in printed
        assert "Spend by category" in printed
        assert len(list(reports.glob("*.png"))) == 4
        # The unmatched row must surface the instruction that drives the
        # rule-writing loop, not be silently swallowed.
        assert "add keywords to CATEGORY_RULES" in printed

    def test_omits_the_rule_writing_prompt_when_everything_is_categorized(
        self, monkeypatch, tmp_path, capsys
    ):
        """The prompt is guidance, not decoration — a statement the rules
        fully explain should not be told to go write more rules."""
        statement = tmp_path / "statement.csv"
        statement.write_text(
            "Date,Narration,Withdrawal Amt.,Deposit Amt.\n"
            "01/05/26,UPI-SWIGGY-order-111111,347.00,\n"
            "02/05/26,UPI-DMART READY-222222,1240.50,\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "expense-analyzer",
                "--statement",
                str(statement),
                "--reports",
                str(tmp_path / "reports"),
            ],
        )

        cli.main()

        assert "add keywords to CATEGORY_RULES" not in capsys.readouterr().out

    def test_lists_sources_and_stops_without_reading_any_data(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["expense-analyzer", "--list-sources"])

        cli.main()

        printed = capsys.readouterr().out
        assert "household" in printed
        assert "116,201" in printed
        assert "Statement" not in printed, "--list-sources must not run the pipeline"

    def test_refuses_a_multi_account_source_until_one_is_chosen(self, monkeypatch, tmp_path):
        """The real bank export holds ten unrelated accounts. Summing them
        would produce a confident, meaningless number."""
        path = tmp_path / "bank.csv"
        path.write_text(
            "Account No,DATE,TRANSACTION DETAILS,WITHDRAWAL AMT,DEPOSIT AMT\n"
            "111',2017-06-29,UPI-SWIGGY,347,\n"
            "222',2017-06-30,UPI-DMART,120,\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "sys.argv", ["expense-analyzer", "--source", "bank", "--statement", str(path)]
        )

        with pytest.raises(SystemExit) as exit_info:
            cli.main()

        assert "--account 111" in str(exit_info.value)

    def test_analyses_one_account_when_told_which(self, monkeypatch, tmp_path, capsys):
        path = tmp_path / "bank.csv"
        path.write_text(
            "Account No,DATE,TRANSACTION DETAILS,WITHDRAWAL AMT,DEPOSIT AMT\n"
            "111',2017-06-29,UPI-SWIGGY,347,\n"
            "222',2017-06-30,UPI-DMART,120,\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "sys.argv",
            [
                "expense-analyzer",
                "--source",
                "bank",
                "--statement",
                str(path),
                "--account",
                "111",
                "--reports",
                str(tmp_path / "reports"),
            ],
        )

        cli.main()

        assert "1 transactions" in capsys.readouterr().out

    def test_section_underlines_the_title_to_its_own_width(self, capsys):
        cli.section("Charts")
        assert capsys.readouterr().out == "\nCharts\n------\n"
