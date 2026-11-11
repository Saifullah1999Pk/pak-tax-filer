"""Rounding and amount wording edge cases (feature 004 review; section 219, research R7)."""

from decimal import Decimal

from app.tax.breakdown import money
from app.tax.engine import TaxInputs, calculate, rupees
from app.tax.rates import rates_for


def test_rounding_never_gives_minus_zero() -> None:
    """Fails if a balance under 50 paisa overpaid reaches the API as "-0"."""
    assert str(rupees(Decimal("-0.40"))) == "0"


def test_a_tiny_over_deduction_is_a_zero_balance() -> None:
    """Fails if 40 paisa over-deducted shows as "-0" in the result or its step."""
    inputs = TaxInputs(
        "2025-26", True, Decimal(1800000), Decimal("72000.40"), Decimal(0), Decimal(0), True
    )

    result = calculate(inputs, rates_for("2025-26"))

    assert str(result.salary_balance) == "0"
    assert str(result.steps[3].result) == "0"


def test_paisa_are_shown_rounded_half_up() -> None:
    """Fails if displayed paisa use banker's rounding (0.125 -> 0.12) instead of half up."""
    assert money(Decimal("0.125")) == "Rs 0.13"


def test_a_negative_amount_reads_minus_rs() -> None:
    """Fails if a negative amount reads "Rs -4,000"."""
    assert money(Decimal(-4000)) == "-Rs 4,000"
