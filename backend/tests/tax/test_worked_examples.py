"""The engine against the signed-off worked examples (feature 004, task T009; FR-015).

Each example was worked by hand from the Ordinance and signed off by Saifullah Khan before any
engine code existed. The engine must give exactly the same figures.
"""

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
