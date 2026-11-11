"""Refusing rather than guessing (feature 004, task T021; research R4, FR-012, FR-013)."""

from typing import Any

import pytest
from test_sign_off import EXAMPLES
from test_worked_examples import FIGURES, inputs_from

from app.tax.engine import calculate
from app.tax.rates import rates_for

BLOCKED = [e for e in EXAMPLES if e["expected"]["blocked_reason"] is not None]


@pytest.mark.parametrize("example", BLOCKED, ids=[e["id"] for e in BLOCKED])
def test_blocked_example_gives_its_reason_and_no_figures(example: dict[str, Any]) -> None:
    """Fails if a blocked case is calculated anyway, or the reason differs from the example."""
    result = calculate(inputs_from(example), rates_for("2025-26"))

    assert result.blocked_reason == example["expected"]["blocked_reason"]
    assert all(getattr(result, name) is None for name in FIGURES)
    assert not result.steps


def test_there_is_a_blocked_example_for_every_reason() -> None:
    """Fails if the blocked cases stop covering all five reasons in the contract."""
    assert len({e["expected"]["blocked_reason"] for e in BLOCKED}) == 5
