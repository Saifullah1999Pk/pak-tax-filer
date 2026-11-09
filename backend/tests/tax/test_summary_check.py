"""The AI summary may only repeat the breakdown's numbers (feature 004, T016; research R8, FR-011).

The check is plain code (Principle I): any number not in the breakdown, or any number word, and
the summary is dropped. The breakdown is always returned, with or without a summary.
"""

import asyncio
from decimal import Decimal

import pytest

from app.tax.engine import TaxInputs, TaxResult, calculate
from app.tax.rates import rates_for
from app.tax.summary import FakeSummariser, summary_is_safe, verified_summary

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
