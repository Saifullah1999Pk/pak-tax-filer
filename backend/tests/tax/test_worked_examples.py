"""The engine against the signed-off worked examples (feature 004, task T009; FR-015).

Each example was worked by hand from the Ordinance and signed off by Saifullah Khan before any
engine code existed. The engine must give exactly the same figures.
"""

import re
from decimal import Decimal
from typing import Any

import pytest
from test_sign_off import EXAMPLES

from app.tax.engine import TaxInputs, TaxResult, calculate
from app.tax.rates import rates_for

FIGURES = (
    "salary_tax",
    "surcharge",
    "profit_tax",
    "salary_balance",
    "profit_balance",
    "non_atl_extra_withheld",
)
CALCULATED = [e for e in EXAMPLES if e["expected"]["blocked_reason"] is None]


def inputs_from(example: dict[str, Any]) -> TaxInputs:
    """The engine's inputs for an example: its certificates summed per type (research R5)."""
    salary = example["inputs"]["salary_certificates"]
    bank = example["inputs"]["bank_certificates"]
    return TaxInputs(
        tax_year="2025-26",
        atl=example["inputs"]["atl"],
        taxable_salary=sum((Decimal(c["taxable_salary"]) for c in salary), Decimal(0)),
        tax_deducted=sum((Decimal(c["tax_deducted"]) for c in salary), Decimal(0)),
        gross_profit=sum((Decimal(c["profit_amount"]) for c in bank), Decimal(0)),
        tax_withheld=sum((Decimal(c["tax_withheld"]) for c in bank), Decimal(0)),
        has_salary_certificate=bool(salary),
    )


def figures(result: TaxResult) -> dict[str, str | None]:
    """The result's figures as the examples write them (whole rupees, or None)."""
    values = {name: getattr(result, name) for name in FIGURES}
    return {name: None if value is None else str(value) for name, value in values.items()}


@pytest.mark.parametrize("example", CALCULATED, ids=[e["id"] for e in CALCULATED])
def test_engine_matches_the_signed_off_example(example: dict[str, Any]) -> None:
    """Fails if any figure differs from the hand-worked, signed-off example by even a rupee."""
    result = calculate(inputs_from(example), rates_for("2025-26"))

    expected = {name: example["expected"][name] for name in FIGURES}
    assert result.blocked_reason is None
    assert figures(result) == expected


def test_there_are_calculated_examples_to_check() -> None:
    """Fails if the examples file were emptied (the parametrised test would pass vacuously)."""
    assert len(CALCULATED) >= 15


# Task T015: the breakdown (research R7, FR-010).

STEP_ORDER = ("Salary tax", "Surcharge", "Tax on bank profit", "Salary side", "Profit side")


@pytest.mark.parametrize("example", CALCULATED, ids=[e["id"] for e in CALCULATED])
def test_breakdown_has_every_step_in_order_each_citing_its_rule(example: dict[str, Any]) -> None:
    """Fails if a step is missing, out of order, uncited, or disagrees with the figures."""
    result = calculate(inputs_from(example), rates_for("2025-26"))

    assert [step.description.split(":")[0] for step in result.steps] == list(STEP_ORDER)
    assert all("Ordinance" in step.rule_location for step in result.steps)
    salary_tax, surcharge, profit_tax, salary_side, profit_side = result.steps
    assert salary_tax.result == result.salary_tax
    assert surcharge.result == result.surcharge
    assert profit_tax.result == result.profit_tax
    assert salary_side.result == result.salary_balance
    assert profit_side.result == result.profit_balance


@pytest.mark.parametrize("example", CALCULATED, ids=[e["id"] for e in CALCULATED])
def test_salary_step_cites_the_row_the_signed_off_working_used(example: dict[str, Any]) -> None:
    """Fails if the breakdown cites a different row of the table than the hand working did."""
    working = " ".join(example["working"])
    row = re.search(r"row (\d)", working)
    assert row is not None, "every calculated example names its row"

    salary_step = calculate(inputs_from(example), rates_for("2025-26")).steps[0]

    assert f"row {row.group(1)} " in salary_step.rule_location + " "


def test_amounts_and_rates_read_like_the_contract() -> None:
    """Fails if the wording drifts from research R7 ("Rs 1,800,000", "11%")."""
    example = next(e for e in CALCULATED if e["id"] == "band-3-inside")

    first = calculate(inputs_from(example), rates_for("2025-26")).steps[0].description

    assert "Rs 1,800,000" in first
    assert "Rs 6,000 + 11% of Rs 600,000" in first
    assert first.endswith("= Rs 72,000")


def test_non_atl_extra_withholding_is_never_called_a_refund() -> None:
    """Fails if the non-ATL step implies the extra withholding comes back (FR-013)."""
    example = next(e for e in CALCULATED if e["id"] == "non-atl-40-percent-withheld")

    profit_side = calculate(inputs_from(example), rates_for("2025-26")).steps[-1].description

    assert "needs confirmation" in profit_side
    assert "refund" not in profit_side.lower()
