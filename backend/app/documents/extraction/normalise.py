"""Turning printed text into exact values (feature 003, research R2).

Plain code on Decimal; the model only reports what is printed (constitution Principle I).
"""

import re
from decimal import Decimal

# The largest value numeric(14,2) can hold.
_MAX_AMOUNT = Decimal("999999999999.99")
_CURRENCY = re.compile(r"^(rs\.?|pkr)\s*", re.IGNORECASE)
_DIGITS = re.compile(r"\d+(\.\d{1,2})?")
# "2025-26", "2025-2026", "2025/26", "2025–26" (en dash).
_YEAR_RANGE = re.compile(r"(\d{4})\s*[-/–—]\s*(\d{4}|\d{2})")
# "2026", "TY 2026", "Tax Year 2026": the tax year that ends on 30 June of that year.
_YEAR_ENDING = re.compile(r"(?:(?:tax\s*year|ty)\s*)?(\d{4})", re.IGNORECASE)


def parse_amount(printed: str) -> Decimal:
    """An amount as printed ("Rs. 1,800,000/-", "(5,000)") as a Decimal with 2 places.

    Brackets or a minus sign give a negative value, which the rule checks then flag.
    Raises ValueError for anything that isn't plainly a number of rupees.
    """
    text = printed.strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    text = _CURRENCY.sub("", text)
    text = text.removesuffix("/-")
    text = re.sub(r"[\s,]", "", text)
    if text.startswith("-"):
        negative, text = not negative, text[1:]
    if not _DIGITS.fullmatch(text):
        raise ValueError(f"Not a valid amount: {printed!r}.")
    value = Decimal(text)
    if value > _MAX_AMOUNT:
        raise ValueError(f"Amount too large: {printed!r}.")
    value = value.quantize(Decimal("0.01"))
    return -value if negative else value


def parse_tax_year(printed: str) -> str:
    """A tax year as printed, in the "2025-26" form when it is clearly one tax year.

    Anything unclear is returned as printed (trimmed), never guessed, so the rule check flags it.
    """
    text = printed.strip()
    if match := _YEAR_RANGE.fullmatch(text):
        start, end = int(match[1]), match[2]
        end_year = int(end) if len(end) == 4 else start // 100 * 100 + int(end)
        return f"{start}-{end_year % 100:02d}" if end_year == start + 1 else text
    if match := _YEAR_ENDING.fullmatch(text):
        end_year = int(match[1])
        return f"{end_year - 1}-{end_year % 100:02d}"
    return text
