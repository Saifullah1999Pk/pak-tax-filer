"""The tax result's summary, written by code (design 2026-11-16-plain-summary).

Fixed sentences filled with the result's own amounts: no AI, no new figures, and salary and bank
profit never added together.
"""

from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.tax.breakdown import tax_summary
from app.tax.engine import TaxResult


def result(**figures: str) -> TaxResult:
    """A calculated result: every figure 0 unless given."""
    names = (
        "salary_tax",
        "surcharge",
        "profit_tax",
        "salary_balance",
        "profit_balance",
        "salary_credit",
        "profit_credit",
    )
    amounts: dict[str, Any] = {name: Decimal(figures.get(name, "0")) for name in names}
    return replace(TaxResult(tax_year="2025-26"), **amounts)


def test_over_deducted_salary() -> None:
    """Fails if an over-deduction reads as a negative amount or the wording drifts."""
    summary = tax_summary(result(salary_tax="72000", salary_credit="75000", salary_balance="-3000"))

    assert summary == (
        "Your salary tax for 2025-26 is Rs 72,000. Your employers deducted Rs 75,000, so "
        "Rs 3,000 was deducted too much."
    )


def test_payable_with_surcharge_and_bank_profit() -> None:
    """Fails if a surcharge, a payable balance or the bank side is left out."""
    summary = tax_summary(
        result(
            salary_tax="3000000",
            surcharge="300000",
            salary_credit="3000000",
            salary_balance="300000",
            profit_tax="10000",
            profit_credit="8000",
            profit_balance="2000",
        )
    )

    assert summary == (
        "Your salary tax for 2025-26 is Rs 3,000,000 plus a surcharge of Rs 300,000. Your "
        "employers deducted Rs 3,000,000, so Rs 300,000 is still payable. Tax on your bank "
        "profit is Rs 10,000; after Rs 8,000 withheld by banks, Rs 2,000 is still payable."
    )


def test_balanced_sides_say_nothing_more_is_payable() -> None:
    """Fails if a zero balance reads as an amount, or an over-withholding as a negative."""
    summary = tax_summary(
        result(
            salary_tax="72000",
            salary_credit="72000",
            profit_tax="10000",
            profit_credit="12000",
            profit_balance="-2000",
        )
    )

    assert summary is not None
    # Names its side, so it never reads as an answer for both (review, 2026-11-16).
    assert "Rs 72,000, so nothing more is payable on your salary." in summary
    assert summary.endswith("Rs 2,000 was withheld too much.")


def test_no_bank_profit_has_no_bank_sentence() -> None:
    """Fails if a user without bank profit is told about it."""
    summary = tax_summary(result(salary_tax="72000", salary_credit="75000", salary_balance="-3000"))

    assert summary is not None and "bank" not in summary


def test_blocked_has_none() -> None:
    """Fails if a refused calculation gets a summary (its message already says why)."""
    assert tax_summary(TaxResult("2025-26", blocked_reason="needs_atl_answer")) is None


def test_off_the_atl_the_extra_withheld_stays_out() -> None:
    """Fails if the summary states the extra withheld off the ATL: whether it can be reclaimed
    needs confirmation, so only the page's own notice mentions it."""
    figures = result(
        salary_tax="72000", salary_credit="72000", profit_tax="10000", profit_credit="10000"
    )
    off_atl = replace(figures, non_atl_extra_withheld=Decimal("5000"))

    summary = tax_summary(off_atl)

    assert summary is not None and "5,000" not in summary
    # Banks withheld Rs 15,000: only the part counted against the tax is named, as such.
    assert summary.endswith(
        "counting Rs 10,000 of what banks withheld, nothing more is payable on your bank profit."
    )


def test_off_the_atl_with_withholding_below_the_tax() -> None:
    """Fails if an off-ATL user who still owes on bank profit isn't told so."""
    figures = result(
        salary_tax="72000",
        salary_credit="72000",
        profit_tax="15000",
        profit_credit="10000",
        profit_balance="5000",
    )
    off_atl = replace(figures, non_atl_extra_withheld=Decimal(0))

    summary = tax_summary(off_atl)

    assert summary is not None
    assert summary.endswith(
        "Tax on your bank profit is Rs 15,000; counting Rs 10,000 of what banks withheld, "
        "Rs 5,000 is still payable."
    )
