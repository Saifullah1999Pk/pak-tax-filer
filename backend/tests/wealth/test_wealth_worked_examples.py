"""The reconciliation against the signed-off worked examples (feature 005, task T007; FR-015).

Each example's inputs go through build_inputs (the same summing and s.219 rounding the service
uses, research R5) and the pure reconcile(); every figure must equal the hand-worked one.
Not-ready examples are covered by test_wealth_not_ready.py (T019).
"""

from decimal import Decimal
from typing import Any

import pytest
from wealth_examples import READY, run


@pytest.mark.parametrize("example", READY, ids=[e["id"] for e in READY])
def test_the_reconciliation_matches_the_worked_example(example: dict[str, Any]) -> None:
    """Fails if any figure or the direction differs from the signed-off hand working."""
    result = run(example)
    expected = example["expected"]

    assert result.not_ready_reason is None
    for figure in ("net_assets", "increase", "inflows", "outflows", "unreconciled"):
        assert getattr(result, figure) == Decimal(expected[figure]), figure
    assert result.direction == expected["direction"]


def test_figures_are_exact_whole_rupees() -> None:
    """Fails if a figure is a float, or carries paisa the user can't enter in IRIS."""
    result = run(next(e for e in READY if e["id"] == "several-certificates-paisa"))

    for figure in ("net_assets", "increase", "inflows", "outflows", "unreconciled"):
        value = getattr(result, figure)
        assert isinstance(value, Decimal) and value == value.to_integral_value(), figure
