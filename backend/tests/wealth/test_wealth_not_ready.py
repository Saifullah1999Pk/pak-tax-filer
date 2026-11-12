"""Not ready: a reason and no figures at all (feature 005, task T019; research R6, FR-011).

Driven by the signed-off not-ready worked examples, which include their check order.
"""

from decimal import Decimal
from typing import Any

import pytest
from wealth_examples import EXAMPLES, run

from app.tax.engine import TaxInputs, calculate
from app.tax.rates import rates_for
from app.wealth.reconcile import (
    CertificateFigures,
    UserEntries,
    WealthInputs,
    build_inputs,
    reconcile,
)

RATES = rates_for("2025-26")

NOT_READY = [e for e in EXAMPLES if e["expected"]["not_ready_reason"] is not None]
FIGURES = ("net_assets", "increase", "inflows", "outflows", "unreconciled", "direction")


@pytest.mark.parametrize("example", NOT_READY, ids=[e["id"] for e in NOT_READY])
def test_a_not_ready_statement_gives_its_reason_and_no_figures(example: dict[str, Any]) -> None:
    """Fails if a statement that can't be reconciled shows any figure, or the wrong reason."""
    result = run(example)

    assert result.not_ready_reason == example["expected"]["not_ready_reason"]
    assert all(getattr(result, figure) is None for figure in FIGURES)
    assert result.certificate == example["expected"].get("certificate")
    assert result.message  # what to do, in words (FR-011)
    if result.certificate:
        assert result.message.startswith(result.certificate)  # the certificate is named
    assert not result.steps and not result.where_to_look


def _inputs(salary: list[CertificateFigures], bank: list[CertificateFigures]) -> WealthInputs:
    return build_inputs(UserEntries(previous_net_assets=Decimal(0)), salary, bank, RATES)


SALARY = CertificateFigures(
    name="s", gross_salary=Decimal(1000000), taxable_salary=Decimal(1000000)
)


def test_the_profit_limit_uses_the_unrounded_sum_like_the_tax_page() -> None:
    """Fails if Rs 5,000,000.40 of bank profit passes here while the tax page (004, which
    compares the unrounded sum) refuses it: the two pages must agree (research R6)."""
    bank = [CertificateFigures(name="b", profit_amount=Decimal("5000000.40"))]

    assert reconcile(_inputs([SALARY], bank)).not_ready_reason == "profit_over_limit"
    tax = calculate(
        TaxInputs(
            "2025-26", True, Decimal(1000000), Decimal(0), Decimal("5000000.40"), Decimal(0), True
        ),
        RATES,
    )
    assert tax.blocked_reason == "profit_over_limit"


def test_profit_over_the_limit_is_checked_before_a_wrong_certificate() -> None:
    """Fails if the last two not-ready checks swap order (research R6)."""
    wrong = CertificateFigures(
        name="wrong", gross_salary=Decimal(900000), taxable_salary=Decimal(1000000)
    )
    bank = [CertificateFigures(name="b", profit_amount=Decimal(5000001))]

    assert reconcile(_inputs([wrong], bank)).not_ready_reason == "profit_over_limit"
