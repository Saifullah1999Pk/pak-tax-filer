"""The reconciliation against the signed-off worked examples (feature 005, task T007; FR-015).

Each example's inputs go through build_inputs (the same summing and s.219 rounding the service
uses, research R5) and the pure reconcile(); every figure must equal the hand-worked one.
Not-ready examples are covered by test_wealth_not_ready.py (T019).
"""

from decimal import Decimal
from typing import Any

import pytest
from wealth_examples import READY, run

from app.tax.breakdown import money
from app.wealth.breakdown import WHERE_TO_LOOK


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


# Task T013 (User Story 2): the breakdown, the message and where to look.
STEP_LINES = ["7019", "7029", "703001", "703003", "7049", "7099", "703000"]
STEP_FIGURES = [None, None, "net_assets", "increase", "inflows", "outflows", "unreconciled"]


@pytest.mark.parametrize("example", READY, ids=[e["id"] for e in READY])
def test_the_breakdown_shows_every_step_with_its_form_line(example: dict[str, Any]) -> None:
    """Fails if a step is missing, out of order, lacks its form line, or shows another figure
    than the result (FR-009)."""
    result = run(example)

    assert [step.form_line for step in result.steps] == STEP_LINES
    for step, figure in zip(result.steps, STEP_FIGURES, strict=True):
        if figure is not None:
            assert step.result == getattr(result, figure), step.form_line
        assert step.description.endswith(money(step.result)), step.description
    assert result.steps[0].result - result.steps[1].result == result.net_assets


@pytest.mark.parametrize("example", READY, ids=[e["id"] for e in READY])
def test_the_message_states_the_amount_and_direction_in_words(example: dict[str, Any]) -> None:
    """Fails if a gap is shown only as a signed number, or "reconciled" isn't said plainly
    (FR-007)."""
    result = run(example)
    gap = abs(result.unreconciled or Decimal(0))
    assert result.message is not None

    if result.direction == "reconciled":
        assert result.message == "Your wealth statement reconciles."
    elif result.direction == "inflows_exceed_growth":
        assert f"inflows exceed the growth in your assets by {money(gap)}" in result.message
    else:
        assert f"assets grew {money(gap)} more than your inflows explain" in result.message
    assert "-Rs" not in result.message


@pytest.mark.parametrize("example", READY, ids=[e["id"] for e in READY])
def test_where_to_look_is_the_fixed_list_and_never_an_amount(example: dict[str, Any]) -> None:
    """Fails if the checklist suggests an amount, isn't the direction's fixed list, or appears
    for a reconciled statement (FR-007, SC-003)."""
    result = run(example)

    if result.direction == "reconciled":
        assert not result.where_to_look
        return
    assert result.direction is not None
    assert result.where_to_look == WHERE_TO_LOOK[result.direction]
    assert not any(char.isdigit() for item in result.where_to_look for char in item)


def test_a_missing_inflow_list_and_a_missing_asset_list_differ() -> None:
    """Fails if both directions point the user to the same places."""
    missing_inflow = " ".join(WHERE_TO_LOOK["growth_exceeds_inflows"]).lower()
    missing_asset = " ".join(WHERE_TO_LOOK["inflows_exceed_growth"]).lower()

    assert "gift" in missing_inflow and "inheritance" in missing_inflow
    assert "remittance" in missing_inflow and "family" in missing_inflow
    assert "bank account" in missing_asset and "expense" in missing_asset
