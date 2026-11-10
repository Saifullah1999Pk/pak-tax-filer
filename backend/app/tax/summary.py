"""A short plain-language summary of the breakdown, checked before use (feature 004, T018; R8).

Gemini writes 2-3 sentences from the breakdown. Then plain code checks every number in them: any
number not in the breakdown, or any number word ("lakh", "1.8 million"), and the summary is
dropped (constitution Principle I, FR-011). It has 4 seconds; late, refused or failed means no
summary. The breakdown is always shown and never waits on it. No tax figure is produced here.
"""

import asyncio
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Protocol

import httpx2
from google import genai
from google.genai import errors, types

from app.documents.extraction.client import THINKING_LEVELS
from app.tax.engine import TaxResult

logger = logging.getLogger(__name__)

LIMIT_SECONDS = 4.0
# The deadline sent to Google. Gemini refuses anything under 10 s (400 INVALID_ARGUMENT), so the
# 4-second limit is enforced here, by verified_summary's wait_for, not by the request.
GOOGLE_DEADLINE_MS = 10_000
INSTRUCTIONS = """\
You explain an income tax result to the taxpayer in 2 or 3 short, plain sentences. Use only the \
numbers that appear in the breakdown you are given, written the same way (e.g. "Rs 72,000"). Do \
not calculate, round or add any new number, and never write numbers as words (no "lakh", \
"million", "thousand"). Do not give advice."""

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_NUMBER_WORDS = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|thousand|lakh|lakhs|lac|lacs|crore|crores|million|millions|"
    r"billion|billions)\b",
    re.IGNORECASE,
)


# The balance's direction, in the words a summary might use. "Refund" is never allowed: the app
# never promises one (FR-013), and an over-deduction isn't a refund until FBR says so.
_PAYABLE_WORDS = re.compile(r"\b(?:owe|owes|owed|owing|payable|outstanding)\b", re.IGNORECASE)
_OVERPAID_WORDS = re.compile(
    r"\b(?:over-?deducted|over-?withheld|overpaid|excess)\b", re.IGNORECASE
)
_REFUND = re.compile(r"\brefund", re.IGNORECASE)


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in digits, as a value: "Rs 72,000.00" and "72000" are the same."""
    found: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            found.add(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return found


def breakdown_text(result: TaxResult) -> str:
    """The breakdown as the model sees it: the tax year and each step."""
    lines = [f"Tax year {result.tax_year}."] + [f"- {step.description}" for step in result.steps]
    return "\n".join(lines)


def summary_is_safe(summary: str, result: TaxResult) -> bool:
    """True only if every number in the summary appears in the breakdown, none is a word, and
    it doesn't reverse a balance (payable vs over-deducted) or mention a refund.

    Known limit (research R8): a right number can still be attached to the wrong figure
    ("your tax is Rs 600,000"); the breakdown beside it is the authoritative answer."""
    if _NUMBER_WORDS.search(summary) or _REFUND.search(summary):
        return False
    balances = [b for b in (result.salary_balance, result.profit_balance) if b is not None]
    if _PAYABLE_WORDS.search(summary) and not any(b > 0 for b in balances):
        return False
    if _OVERPAID_WORDS.search(summary) and not any(b < 0 for b in balances):
        return False
    return numbers_in(summary) <= numbers_in(breakdown_text(result))


class Summariser(Protocol):  # pylint: disable=too-few-public-methods
    """Writes a short summary from the breakdown text, or None."""

    async def write(self, breakdown: str) -> str | None:
        """The model's summary, or None."""


class GeminiSummariser:  # pylint: disable=too-few-public-methods
    """Writes the summary with Gemini (free tier); any failure is None, never an error."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._effort = effort
        self._http_client = http_client

    async def write(self, breakdown: str) -> str | None:
        """Ask Gemini for 2-3 sentences; no retries (the 4-second budget doesn't allow them)."""
        if not self._api_key:
            return None
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                httpx_async_client=self._http_client,
            ),
        )
        try:
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=breakdown,
                config=types.GenerateContentConfig(
                    system_instruction=INSTRUCTIONS,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=THINKING_LEVELS[self._effort]
                    ),
                    max_output_tokens=300,
                    http_options=types.HttpOptions(timeout=GOOGLE_DEADLINE_MS),
                ),
            )
        except (errors.APIError, httpx2.HTTPError) as exc:
            logger.warning("Summary failed: %s", type(exc).__name__)
            return None
        candidates = response.candidates or []
        if not candidates or candidates[0].finish_reason != types.FinishReason.STOP:
            # Cut short (e.g. MAX_TOKENS) or blocked: a fragment like "For tax year 2025" passes
            # the number check, so it must never be used (004 quickstart 2.2, 2026-11-10).
            return None
        return response.text or None


class FakeSummariser:  # pylint: disable=too-few-public-methods
    """Returns a fixed answer (tests): text, an error to raise, and a delay in seconds."""

    def __init__(
        self, text: str | None = None, *, error: Exception | None = None, delay: float = 0
    ) -> None:
        self.text = text
        self.error = error
        self.delay = delay

    async def write(self, breakdown: str) -> str | None:
        """The fixed answer, after the delay."""
        del breakdown
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.text


async def verified_summary(
    result: TaxResult, summariser: Summariser, limit_seconds: float = LIMIT_SECONDS
) -> str | None:
    """The summary if it arrives in time and passes the number check; otherwise None."""
    if result.blocked_reason is not None or not result.steps:
        return None
    try:
        text = await asyncio.wait_for(summariser.write(breakdown_text(result)), limit_seconds)
    except TimeoutError:
        return None
    except Exception:  # pylint: disable=broad-exception-caught  # optional; must never break the result
        logger.warning("Summary failed")
        return None
    if text is None or not summary_is_safe(text, result):
        return None
    return text.strip()
