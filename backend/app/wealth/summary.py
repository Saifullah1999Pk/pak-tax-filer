"""A short plain-language summary of the reconciliation, checked before use (feature 005, T016).

The same pattern as the tax page (004): Gemini writes 2-3 sentences from the breakdown, then the
shared plain-code check (app.explain.number_check) drops it if any number isn't in the
breakdown or is written as a word (FR-010, constitution Principle I). It has 4 seconds; late,
failed or refused means no summary, and the breakdown never waits on it. The "where to look"
checklist is code-written only, so it is never shown to the model to rephrase (FR-007).
"""

import asyncio
import logging

from app.explain.number_check import uses_only_numbers_from
from app.tax.summary import LIMIT_SECONDS, Summariser
from app.wealth.reconcile import ReconciliationResult

logger = logging.getLogger(__name__)

WEALTH_INSTRUCTIONS = """\
You explain a wealth reconciliation to the taxpayer in 2 or 3 short, plain sentences. Use only \
the numbers that appear in the breakdown you are given, written the same way (e.g. \
"Rs 50,000"). Do not calculate, round or add any new number, never write numbers as words (no \
"lakh", "million", "thousand"), and never suggest an amount to enter. Do not give advice."""


def wealth_breakdown_text(result: ReconciliationResult, tax_year: str) -> str:
    """What the model sees: the tax year, each step and the result in words."""
    lines = [f"Wealth statement for tax year {tax_year}."]
    lines += [f"- {step.description}" for step in result.steps]
    lines.append(f"Result: {result.message}")
    return "\n".join(lines)


async def verified_wealth_summary(
    result: ReconciliationResult,
    tax_year: str,
    summariser: Summariser,
    limit_seconds: float = LIMIT_SECONDS,
) -> str | None:
    """The summary if it arrives in time and uses only the breakdown's numbers; else None."""
    if result.not_ready_reason is not None or not result.steps:
        return None
    source = wealth_breakdown_text(result, tax_year)
    try:
        text = await asyncio.wait_for(summariser.write(source), limit_seconds)
    except TimeoutError:
        return None
    except Exception:  # pylint: disable=broad-exception-caught  # optional; never breaks the result
        logger.warning("Wealth summary failed")
        return None
    if text is None or not uses_only_numbers_from(text, source):
        return None
    return text.strip()
