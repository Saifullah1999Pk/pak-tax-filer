"""The AI summary may only repeat the breakdown's numbers (feature 004, T016; research R8, FR-011).

The check is plain code (Principle I): any number not in the breakdown, or any number word, and
the summary is dropped. The breakdown is always returned, with or without a summary.
"""

import asyncio
from collections.abc import Callable
from decimal import Decimal

import pytest

from app.tax.engine import TaxInputs, TaxResult, calculate
from app.tax.rates import rates_for
from app.tax.summary import INSTRUCTIONS, FakeSummariser, summary_is_safe, verified_summary

pytestmark = pytest.mark.anyio


def band_3() -> TaxResult:
    """Taxable salary 1,800,000, tax deducted 60,000, no bank profit: tax 72,000, 12,000 due."""
    inputs = TaxInputs(
        "2025-26", True, Decimal(1800000), Decimal(60000), Decimal(0), Decimal(0), True
    )
    return calculate(inputs, rates_for("2025-26"))


@pytest.mark.parametrize(
    "summary",
    [
        "Your salary tax is Rs 72,000 at 11% above Rs 1,200,000. You owe Rs 12,000.",
        "Tax of 72000 on a salary of Rs 1,800,000; 12,000 is payable.",
        "Your employers deducted Rs 60,000 of the Rs 72,000.00 due, so Rs 12,000 remains.",
    ],
)
def test_a_summary_using_only_breakdown_numbers_is_kept(summary: str) -> None:
    """Fails if a faithful summary (in any number format) is thrown away."""
    assert summary_is_safe(summary, band_3())


@pytest.mark.parametrize(
    "summary",
    [
        "Your salary tax is Rs 75,000.",  # a wrong amount
        "You pay 12% on income over Rs 1,200,000.",  # a wrong percentage
        "Your tax is Rs 72,001.",  # a wrong value formatted like a right one
        "You earn about 1.8 million rupees.",  # a number word
        "You earn 18 lakh a year.",  # a number word
        "Your tax is seventy two thousand rupees.",  # written-out numbers
    ],
)
def test_a_summary_with_any_other_number_is_dropped(summary: str) -> None:
    """Fails if a summary could introduce a figure the breakdown doesn't have (FR-011)."""
    assert not summary_is_safe(summary, band_3())


async def test_a_safe_summary_is_returned() -> None:
    """Fails if a checked, faithful summary isn't passed on."""
    text = "Your salary tax is Rs 72,000; Rs 12,000 is payable."

    assert await verified_summary(band_3(), FakeSummariser(text)) == text


async def test_an_unsafe_summary_is_dropped() -> None:
    """Fails if a summary with a wrong number reaches the user."""
    assert await verified_summary(band_3(), FakeSummariser("Your tax is Rs 75,000.")) is None


async def test_an_error_or_no_answer_gives_no_summary() -> None:
    """Fails if the AI being unavailable or refusing breaks the result."""
    assert await verified_summary(band_3(), FakeSummariser(None)) is None
    assert await verified_summary(band_3(), FakeSummariser(error=RuntimeError("down"))) is None


async def test_a_slow_answer_is_abandoned_after_four_seconds() -> None:
    """Fails if a late summary holds up the result (research R8: 4-second limit)."""
    slow = FakeSummariser("Your tax is Rs 72,000.", delay=60)

    started = asyncio.get_running_loop().time()
    result = await verified_summary(band_3(), slow, limit_seconds=0.2)

    assert result is None
    assert asyncio.get_running_loop().time() - started < 2


async def test_a_blocked_result_gets_no_summary() -> None:
    """Fails if a refused calculation is "summarised" (there are no figures to summarise)."""
    blocked = TaxResult(tax_year="2025-26", blocked_reason="needs_atl_answer")

    assert await verified_summary(blocked, FakeSummariser("Anything.")) is None


def over_deducted() -> TaxResult:
    """Taxable salary 1,800,000, tax deducted 76,000: tax 72,000, Rs 4,000 over-deducted."""
    inputs = TaxInputs(
        "2025-26", True, Decimal(1800000), Decimal(76000), Decimal(0), Decimal(0), True
    )
    return calculate(inputs, rates_for("2025-26"))


@pytest.mark.parametrize(
    ("summary", "result", "kept"),
    [
        ("Rs 4,000 was over-deducted by your employers.", over_deducted, True),
        ("You owe Rs 4,000.", over_deducted, False),  # the direction is wrong
        ("Rs 4,000 is payable.", over_deducted, False),
        ("Your employers over-deducted Rs 12,000.", band_3, False),
        ("You will get a refund of Rs 12,000.", band_3, False),  # the app never says refund
        ("You will get a refund of Rs 4,000.", over_deducted, False),
    ],
)
def test_a_summary_must_not_reverse_the_balance(
    summary: str, result: Callable[[], TaxResult], kept: bool
) -> None:
    """Fails if a summary with the right number says payable where it's over-deducted, or the
    reverse, or promises a refund (spec: the summary never contradicts the steps)."""
    assert summary_is_safe(summary, result()) is kept


# Feature 001, User Story 6: with the summary loaded on its own it finally arrived, and one live
# summary tied the right numbers together the wrong way ("salary tax Rs 1,666,193 after
# accounting for Rs 213,016 deducted"), though every number was in the breakdown. Salary tax is
# before anything is taken off; a sentence that says otherwise is dropped.


def top_band() -> TaxResult:
    """The demo user's figures: tax 1,666,192.50 (Rs 1,666,193), deducted 213,016, 1,453,177 due."""
    inputs = TaxInputs(
        "2025-26", True, Decimal("7100550"), Decimal("213016"), Decimal(0), Decimal(0), True
    )
    return calculate(inputs, rates_for("2025-26"))


@pytest.mark.parametrize(
    "summary",
    [
        # Live, 2026-11-11: says the deduction is already inside the tax.
        "Your salary tax is calculated as Rs 1,666,193 after accounting for Rs 213,016 of tax "
        "deducted by employers. This leaves a final amount of Rs 1,453,177 payable on the "
        "salary side. Meanwhile, the profit side results in nothing to pay.",
        "Your salary tax, net of the Rs 213,016 your employers deducted, is Rs 1,666,193.",
        "Taking into account Rs 213,016 deducted by employers, your salary tax is Rs 1,666,192.50.",
    ],
)
def test_a_summary_putting_the_deduction_inside_the_tax_is_dropped(summary: str) -> None:
    """Fails if a summary that calls the salary tax "after" the deduction reaches the user."""
    assert not summary_is_safe(summary, top_band())


@pytest.mark.parametrize(
    "summary",
    [
        # Both live, 2026-11-11, and right.
        "Your salary tax of Rs 1,666,193, after subtracting tax deducted by employers of "
        "Rs 213,016, results in Rs 1,453,177 payable. On the profit side, tax on bank profit "
        "of Rs 0 and tax withheld by banks of Rs 0 means there is nothing to pay, and the "
        "surcharge is Rs 0.",
        "Your total salary tax for the tax year 2025-26 is Rs 1,666,193 after accounting for "
        "your taxable salary of Rs 7,100,550. After subtracting Rs 213,016 for tax deducted by "
        "employers, your final salary side amount is Rs 1,453,177 payable.",
    ],
)
def test_a_summary_subtracting_the_deduction_from_the_tax_is_kept(summary: str) -> None:
    """Fails if a faithful summary is thrown away because it mentions the deduction."""
    assert summary_is_safe(summary, top_band())


def test_the_model_is_told_the_tax_comes_before_the_deduction() -> None:
    """Fails if the instructions stop saying how the figures relate."""
    assert "before" in INSTRUCTIONS and "never" in INSTRUCTIONS.lower()
