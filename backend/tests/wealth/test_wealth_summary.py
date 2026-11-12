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


# Backend review H1: the number check alone can't stop a summary suggesting the amount that
# forces a zero (it is always in the breakdown), reversing the direction, or claiming a
# reconciliation that isn't there.
RECONCILED = run(next(e for e in EXAMPLES if e["id"] == "reconciled"))


@pytest.mark.parametrize(
    "summary",
    [
        "Add Rs 50,000 of gifts received to reconcile.",  # a suggested amount
        "You should declare Rs 50,000 more inflows.",
        "Enter Rs 50,000 as a gift to make it zero.",
        "Your inflows exceed the growth in your assets by Rs 50,000.",  # the other direction
        "Your wealth statement reconciles.",  # not reconciled
        "Your statement is balanced at Rs 2,050,000 of inflows.",
    ],
)
async def test_a_summary_that_advises_or_contradicts_the_result_is_dropped(summary: str) -> None:
    """Fails if a summary can nudge the user towards a number that merely forces a zero, or say
    the opposite of the result (spec User Story 2; FR-007, FR-010)."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(summary)) is None


async def test_a_reconciled_statement_may_say_so() -> None:
    """Fails if the guard throws away a faithful summary of a reconciled statement."""
    text = "Your wealth statement reconciles: inflows of Rs 2,050,000 explain the change."

    assert await verified_wealth_summary(RECONCILED, "2025-26", FakeSummariser(text)) == text


async def test_a_gap_summary_may_not_claim_the_other_direction_for_growth() -> None:
    """Fails if, when inflows exceed growth, a summary saying assets grew more is shown."""
    gap = run(next(e for e in EXAMPLES if e["id"] == "inflows-exceed-growth"))
    wrong = "Your assets grew Rs 100,000 more than your inflows explain."
    right = "Your inflows exceed the growth in your assets by Rs 100,000."

    assert await verified_wealth_summary(gap, "2025-26", FakeSummariser(wrong)) is None
    assert await verified_wealth_summary(gap, "2025-26", FakeSummariser(right)) == right


# Second backend review: inflections, synonyms and the gap amount tied to a checklist category
# must be caught; harmless wording ("reconciliation", "unreconciled", "inflows exceed outflows",
# "include") must not be.
INFLOWS_GAP = run(next(e for e in EXAMPLES if e["id"] == "inflows-exceed-growth"))


@pytest.mark.parametrize(
    "summary",
    [
        "Adding Rs 50,000 of gifts received would balance it.",
        "Entering Rs 50,000 as a gift clears the gap.",
        "Listing Rs 50,000 as a gift would clear the gap.",
        "A gift of Rs 50,000 you received may be missing.",
        "Your inflows are Rs 50,000 more than the growth in your assets.",
    ],
)
async def test_softer_advice_and_the_other_direction_are_dropped(summary: str) -> None:
    """Fails if a summary can still tie the gap amount to something to enter, or say inflows
    exceed growth when growth exceeds inflows (FR-007, FR-010)."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(summary)) is None


@pytest.mark.parametrize(
    "summary",
    [
        "Growth exceeds your inflows by Rs 100,000.",
        "Your assets increased more than your inflows.",
        "Your inflows fall short of the growth by Rs 100,000.",
    ],
)
async def test_growth_wording_is_dropped_when_inflows_exceed_growth(summary: str) -> None:
    """Fails if a summary says the opposite of an inflows-exceed-growth result."""
    assert await verified_wealth_summary(INFLOWS_GAP, "2025-26", FakeSummariser(summary)) is None


@pytest.mark.parametrize(
    "summary",
    [
        "Your wealth reconciliation shows an unreconciled amount of -Rs 50,000.",
        "Your inflows of Rs 2,050,000 include your taxable salary of Rs 1,800,000.",
        "Your inflows of Rs 2,050,000 exceed your outflows of Rs 1,600,000.",
        "Your net assets this year are Rs 2,600,000, an increase of Rs 500,000 compared to "
        "Rs 2,100,000. Your inflows are Rs 2,050,000 and outflows Rs 1,600,000, leaving an "
        "unreconciled amount of -Rs 50,000.",
    ],
)
async def test_harmless_wording_is_kept(summary: str) -> None:
    """Fails if a faithful summary of a gap is thrown away for innocent words."""
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(summary)) == summary


async def test_repeating_the_apps_own_message_is_kept() -> None:
    """Fails if a summary that repeats the result message the app itself wrote is dropped."""
    assert GAP.message is not None
    assert await verified_wealth_summary(GAP, "2025-26", FakeSummariser(GAP.message)) == GAP.message
