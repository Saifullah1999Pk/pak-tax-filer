"""The reconciliation against the signed-off worked examples (feature 005, task T007; FR-015).

Each example's inputs go through build_inputs (the same summing and s.219 rounding the service
uses, research R5) and the pure reconcile(); every figure must equal the hand-worked one.
Not-ready examples are covered by test_wealth_not_ready.py (T019).
"""

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.tax.rates import rates_for
from app.wealth.reconcile import CertificateFigures, UserEntries, build_inputs, reconcile

EXAMPLES = yaml.safe_load(
    Path(__file__).with_name("worked_examples.yaml").read_text(encoding="utf-8")
)["examples"]
READY = [e for e in EXAMPLES if e["expected"]["not_ready_reason"] is None]


def run(example: dict[str, Any]):  # type: ignore[no-untyped-def]
    """The example's inputs through build_inputs and reconcile."""
    i = example["inputs"]
    salary = [
        CertificateFigures(
            name=c["file"],
            gross_salary=Decimal(c["gross_salary"]),
            taxable_salary=Decimal(c["taxable_salary"]),
            tax_deducted=Decimal(c["tax_deducted"]),
        )
        for c in i["salary_certificates"]
    ]
    bank = [
        CertificateFigures(
            name=b["file"],
            profit_amount=Decimal(b["profit_amount"]),
            tax_withheld=Decimal(b["tax_withheld"]),
        )
        for b in i["bank_certificates"]
    ]

    def amount(name: str) -> Decimal:
        return Decimal(i.get(name, "0"))

    entries = UserEntries(
        previous_net_assets=(
            None if i["previous_net_assets"] is None else Decimal(i["previous_net_assets"])
        ),
        assets=tuple(Decimal(a["amount"]) for a in i["assets"]),
        liabilities=tuple(Decimal(liability["amount"]) for liability in i["liabilities"]),
        other_exempt_income=amount("other_exempt_income"),
        foreign_remittance=amount("foreign_remittance"),
        inheritance=amount("inheritance"),
        gifts_received=amount("gifts_received"),
        family_contribution=amount("family_contribution"),
        personal_expenses=tuple(Decimal(v) for v in i["personal_expenses"].values()),
        gifts_given=amount("gifts_given"),
    )
    return reconcile(build_inputs(entries, salary, bank, rates_for("2025-26")))


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
