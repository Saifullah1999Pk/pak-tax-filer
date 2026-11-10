"""The wealth page's optional AI summary (feature 005, task T014; research R9, FR-010).

Same rules as the tax page, and the same shared number check (app.explain.number_check): only
the breakdown's numbers, no number words, 4 seconds at most, and the breakdown never waits on it.
"""

import asyncio

import pytest
from wealth_examples import EXAMPLES, run

from app.tax.summary import FakeSummariser
from app.wealth.summary import WEALTH_INSTRUCTIONS, verified_wealth_summary, wealth_breakdown_text

pytestmark = pytest.mark.anyio

GAP = run(next(e for e in EXAMPLES if e["id"] == "growth-exceeds-inflows"))
NOT_READY = run(next(e for e in EXAMPLES if e["id"] == "not-ready-no-previous-net-assets"))
SAFE = "Your assets grew Rs 50,000 more than your inflows of Rs 2,050,000 explain."


async def test_a_summary_using_only_breakdown_numbers_is_shown() -> None:
    """Fails if a faithful summary is thrown away."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(SAFE)) == SAFE


@pytest.mark.parametrize(
    "summary",
    [
        "Your assets grew Rs 60,000 more than your inflows explain.",  # a wrong amount
        "Add Rs 50,001 of gifts to reconcile.",  # a suggested amount not in the breakdown
        "Your assets grew fifty thousand rupees more than explained.",  # number words
    ],
)
async def test_a_summary_with_any_other_number_is_dropped(summary: str) -> None:
    """Fails if the summary could introduce a figure (FR-010, constitution Principle I)."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(summary)) is None


async def test_an_error_a_refusal_or_a_slow_answer_gives_no_summary() -> None:
    """Fails if the AI being down, refusing or slow breaks or delays the result."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(None)) is None
    failing = FakeSummariser(error=RuntimeError("down"))
    assert await verified_wealth_summary(GAP, "2025-26", failing) is None

    started = asyncio.get_running_loop().time()
    slow = FakeSummariser(SAFE, delay=60)
    assert await verified_wealth_summary(GAP, "2025-26", slow, limit_seconds=0.2) is None
    assert asyncio.get_running_loop().time() - started < 2


async def test_a_not_ready_statement_gets_no_summary() -> None:
    """Fails if a statement with no figures is "summarised"."""
    assert await verified_wealth_summary(NOT_READY, "2025-26", FakeSummariser(SAFE)) is None


def test_the_model_sees_the_steps_and_the_message_but_never_the_checklist() -> None:
    """Fails if the breakdown text omits a step or the result, or offers the checklist for the
    model to rephrase (the checklist is code-written only, FR-007)."""
    text = wealth_breakdown_text(GAP, "2025-26")

    assert "2025-26" in text
    assert all(step.description in text for step in GAP.steps)
    assert GAP.message is not None and GAP.message in text
    assert not any(item in text for item in GAP.where_to_look)


def test_the_instructions_forbid_new_numbers_and_advice() -> None:
    """Fails if the model isn't told to use only the breakdown's numbers and not to advise."""
    lowered = WEALTH_INSTRUCTIONS.lower()

    assert "only the numbers" in lowered and "advice" in lowered and "words" in lowered
