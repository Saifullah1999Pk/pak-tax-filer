"""The wealth result's summary, written by code (design 2026-11-16-plain-summary).

Fixed sentences filled with the result's own amounts: no AI and no new figures.
"""

from decimal import Decimal

from app.wealth.breakdown import wealth_summary
from app.wealth.reconcile import ReconciliationResult


def result(increase: str) -> ReconciliationResult:
    """A reconciled result like the contract's example, with the increase given."""
    return ReconciliationResult(
        net_assets=Decimal("2565000"),
        increase=Decimal(increase),
        inflows=Decimal("2050000"),
        outflows=Decimal("1585000"),
        unreconciled=Decimal(0),
        direction="reconciled",
    )


def test_growth() -> None:
    """Fails if the contract example's summary drifts from its figures."""
    assert wealth_summary(result("465000"), "2025-26") == (
        "Your net assets at the end of 2025-26 are Rs 2,565,000, Rs 465,000 more than last "
        "year. Your inflows were Rs 2,050,000 and your outflows Rs 1,585,000."
    )


def test_fall_and_no_change() -> None:
    """Fails if a fall reads as a negative amount, or no change as 'Rs 0 more'."""
    fall = wealth_summary(result("-100000"), "2025-26")
    same = wealth_summary(result("0"), "2025-26")

    assert fall is not None and "Rs 2,565,000, Rs 100,000 less than last year." in fall
    assert same is not None and "Rs 2,565,000, the same as last year." in same


def test_not_ready_has_none() -> None:
    """Fails if a result that can't be reconciled gets a summary (its message says why)."""
    not_ready = ReconciliationResult(not_ready_reason="needs_previous_net_assets")

    assert wealth_summary(not_ready, "2025-26") is None


def test_debts_larger_than_assets_read_in_words() -> None:
    """Fails if negative net assets read as "-Rs 50,000" rather than in words."""
    owing = ReconciliationResult(
        net_assets=Decimal("-50000"),
        increase=Decimal("-100000"),
        inflows=Decimal("900000"),
        outflows=Decimal("1000000"),
        unreconciled=Decimal(0),
        direction="reconciled",
    )

    assert wealth_summary(owing, "2025-26") == (
        "At the end of 2025-26 your liabilities exceed your assets by Rs 50,000; your net "
        "assets are Rs 100,000 less than last year. Your inflows were Rs 900,000 and your "
        "outflows Rs 1,000,000."
    )
