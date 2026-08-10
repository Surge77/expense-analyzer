"""The plotting stage.

Charts are hard to assert on — nobody should test pixel colours. What is
worth pinning is the contract around them: the file lands where it was asked
to, the directory is created if missing, and every figure is closed. A
plotting module that leaks figures will exhaust memory partway through a long
run and the failure will look unrelated.
"""

import matplotlib.pyplot as plt
import pytest

from expense_analyzer import analyze, plots


@pytest.fixture
def spend(categorized):
    return analyze.spending_only(categorized)


@pytest.fixture(autouse=True)
def no_leaked_figures():
    """Fail any test that leaves a figure open."""
    plt.close("all")
    yield
    assert not plt.get_fignums(), "a figure was left open; _finish must close every one"


@pytest.mark.parametrize(
    "plot_function,expected_name",
    [
        (plots.plot_by_category, "01_spend_by_category.png"),
        (plots.plot_monthly_total, "02_monthly_total.png"),
        (plots.plot_category_by_month, "03_category_by_month.png"),
        (plots.plot_transaction_sizes, "04_transaction_sizes.png"),
    ],
)
def test_each_chart_writes_its_own_file(plot_function, expected_name, spend, tmp_path):
    written = plot_function(spend, tmp_path)

    assert written == tmp_path / expected_name
    assert written.exists()
    assert written.stat().st_size > 0, "an empty PNG means the figure never rendered"


def test_creates_the_output_directory_when_it_does_not_exist(spend, tmp_path):
    """`reports/` is gitignored, so a fresh clone has no such directory."""
    target = tmp_path / "does" / "not" / "exist"
    assert not target.exists()

    written = plots.plot_by_category(spend, target)

    assert written.exists()


def test_plot_all_writes_every_chart(spend, tmp_path):
    written = plots.plot_all(spend, tmp_path)

    assert len(written) == 4
    assert all(path.exists() for path in written)
    assert len({path.name for path in written}) == 4, "no chart may overwrite another"


def test_overwrites_an_existing_chart_rather_than_failing(spend, tmp_path):
    """Re-running the pipeline is the normal workflow, not an error."""
    first = plots.plot_by_category(spend, tmp_path)
    first.write_bytes(b"stale")

    second = plots.plot_by_category(spend, tmp_path)

    assert second.read_bytes() != b"stale"
