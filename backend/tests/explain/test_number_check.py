"""The shared "only the breakdown's numbers" check (feature 005, task T001; 004 research R8).

Used by both the tax summary (004) and the wealth summary (005), so a fix reaches both.
"""

from decimal import Decimal

import pytest

from app.explain.number_check import numbers_in, uses_only_numbers_from

SOURCE = "Net assets this year: Rs 2,765,000 - Rs 200,000 = Rs 2,565,000. Tax year 2025-26."


def test_numbers_are_read_as_values() -> None:
    """Fails if "Rs 72,000.00" and "72000" aren't the same number."""
    assert numbers_in("Rs 72,000.00 and 72000 and 11%") == {Decimal(72000), Decimal(11)}


@pytest.mark.parametrize(
    ("summary", "safe"),
    [
        ("Your net assets are Rs 2,565,000.", True),
        ("Net assets 2565000 after Rs 200,000 owed.", True),
        ("Your net assets are Rs 2,566,000.", False),  # a number not in the source
        ("About 25 lakh in net assets.", False),  # a number word
        ("Two hundred thousand is owed.", False),
        # A scale glued to digits or abbreviated, around a number that IS in the source (26):
        ("Net assets of Rs 26m.", False),
        ("Net assets of Rs 26million.", False),
        ("Net assets of 26lakh.", False),
        ("Net assets of Rs 26 mn.", False),
        ("Net assets of Rs 26 cr.", False),
        ("Tax year 2025-26 covers 26 months of records.", True),  # a word starting like "m"
    ],
)
def test_only_the_sources_numbers_and_no_number_words(summary: str, safe: bool) -> None:
    """Fails if a summary could add a figure, or write one in words that can't be checked."""
    assert uses_only_numbers_from(summary, SOURCE) is safe
