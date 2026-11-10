"""The reconciliation is plain arithmetic: no AI, database or network (feature 005, research R1;
FR-008, constitution Principle I)."""

import ast
from pathlib import Path

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
