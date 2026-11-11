"""The engine is plain arithmetic: no AI, database or network (feature 004, T010; Principle I)."""

import ast
from pathlib import Path

import app.tax.engine

FORBIDDEN = ("anthropic", "google", "httpx", "httpx2", "sqlalchemy", "app.db", "app.tax.summary")


def test_engine_imports_nothing_that_could_compute_a_figure_elsewhere() -> None:
    """Fails if engine.py imports an AI client, the database or the network (FR-007)."""
    tree = ast.parse(Path(app.tax.engine.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    for name in imported:
        assert not name.startswith(FORBIDDEN), name
