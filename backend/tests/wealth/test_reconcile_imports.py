"""The reconciliation is plain arithmetic: no AI, database or network (feature 005, research R1;
FR-008, constitution Principle I)."""

import ast
import subprocess
import sys
from pathlib import Path

import app
import app.wealth.reconcile

FORBIDDEN = (
    "anthropic",
    "google",
    "httpx",
    "httpx2",
    "sqlalchemy",
    "app.db",
    "app.tax.summary",
    "app.wealth.summary",
    "app.wealth.service",
)


def test_reconcile_imports_nothing_that_could_compute_a_figure_elsewhere() -> None:
    """Fails if reconcile.py imports an AI client, the database or the network."""
    tree = ast.parse(Path(app.wealth.reconcile.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    for name in imported:
        assert not name.startswith(FORBIDDEN), name


def test_nothing_reconcile_pulls_in_indirectly_is_impure() -> None:
    """Fails if anything reconcile.py imports, at any depth, brings in the database, the
    network, an AI client, the clock's or randomness modules (research R1; backend review L2)."""
    probe = (
        "import sys, app.wealth.reconcile; "
        "bad = ('sqlalchemy', 'google', 'httpx', 'httpx2', 'anthropic', 'asyncpg', 'random', "
        "'app.db', 'app.wealth.service', 'app.wealth.summary', 'app.tax.summary'); "
        "print(sorted(m for m in sys.modules if m.split('.')[0] in bad or m in bad))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(app.__file__).parents[1],
    ).stdout.strip()

    assert loaded == "[]", loaded
