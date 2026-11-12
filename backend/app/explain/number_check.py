"""An AI summary may only repeat numbers from the breakdown it was given (feature 005, T001).

Moved from 004's tax/summary.py so the tax and wealth summaries share one check (constitution
Principle I; 004 research R8, 005 research R9). Plain code: any number not in the source, or
any number written as a word ("lakh", "1.8 million"), and the summary must be dropped.
"""

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
NUMBER_WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|thousand|lakh|lakhs|lac|lacs|crore|crores|million|millions|"
    r"billion|billions)\b",
    re.IGNORECASE,
)


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in digits, as a value: "Rs 72,000.00" and "72000" are the same."""
    found: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return found


def uses_only_numbers_from(summary: str, source: str) -> bool:
    """True only if every number in the summary appears in the source and none is a word."""
    if NUMBER_WORDS.search(summary):
        return False
    return numbers_in(summary) <= numbers_in(source)
