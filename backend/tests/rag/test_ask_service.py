"""Asking a question (feature 006, tasks T010 and T016; research R5-R7, FR-004 to FR-009b).

A FakeAnswerer stands in for Gemini and the FakeEmbedder for embeddings, on the migrated test
database; nothing reaches the network.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from rag_helpers import QUESTION, SpyEmbedder, a_corpus, a_user, reply

from app.rag.answer import AnswerError, FakeAnswerer, ModelAnswer
from app.rag.embed import FakeEmbedder
from app.rag.models import AskRequest
from app.rag.service import (
    DAILY_LIMIT_MESSAGE,
    LABEL,
    LIMITED_MESSAGE,
    NOT_COVERED_MESSAGE,
    NOT_READY_MESSAGE,
    TAX_PAGE_LINE,
    UNAVAILABLE_MESSAGE,
    ask,
)

pytestmark = pytest.mark.anyio


async def questions_recorded(db: AsyncSession) -> int:
    """How many question records exist (who and when only)."""
    return (await db.execute(select(func.count()).select_from(AskRequest))).scalar_one()


# ---- User Story 1 (T010) ----


async def test_an_answer_comes_with_its_citations_and_the_label(db: AsyncSession) -> None:
    """Fails if an answer lacks what a citation needs (title, kind, location, page) or the
    practitioner label, or if anything about the question but who and when is stored."""
    await a_corpus(db)
    user = await a_user(db)
    answerer = FakeAnswerer(reply())

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), answerer)

    assert result.status == "answered"
    assert result.answer == reply().answer
    citation = result.citations[0]
    assert (citation.title, citation.kind, citation.location, citation.page) == (
        "Income Tax Ordinance, 2001",
        "law",
        "§149(1)",
        327,
    )
    assert result.label == LABEL
    assert result.tax_page_line is None
    assert await questions_recorded(db) == 1
    # The model saw the retrieved passages, labelled P1..P5, and the question.
    assert answerer.calls[0][0] == QUESTION
    assert [p.location for p in answerer.calls[0][1]][0] == "§149(1)"


# ---- User Story 2 (T016) ----


async def test_below_the_cut_off_it_is_not_covered_without_asking_the_ai(db: AsyncSession) -> None:
    """Fails if the AI is asked about a question the corpus doesn't cover (FR-006)."""
    await a_corpus(db)
    user = await a_user(db)
    answerer = FakeAnswerer(reply())

    result = await ask(
        db, user.id, "What is the sales tax on imported cars?", FakeEmbedder(), answerer
    )

    assert result.status == "not_covered"
    assert result.answer == NOT_COVERED_MESSAGE and result.citations == []
    assert not answerer.calls
    assert result.label == LABEL


async def test_a_question_in_urdu_is_not_covered(db: AsyncSession) -> None:
    """Fails if a question in Urdu reaches the embedder or the AI (spec: English questions only)."""
    await a_corpus(db)
    user = await a_user(db)
    answerer = FakeAnswerer(reply())

    embedder = SpyEmbedder()

    result = await ask(db, user.id, "کیا میری تنخواہ پر ٹیکس کٹتا ہے؟", embedder, answerer)

    assert result.status == "not_covered"
    assert not answerer.calls and not embedder.questions


@pytest.mark.parametrize(
    "model_reply",
    [
        reply(not_covered=True, citations=[]),  # the model says the passages don't cover it
        reply(citations=["P9"]),  # a passage nobody retrieved
        reply(answer="Employers deduct tax above Rs 600,000."),  # a number from nowhere
    ],
    ids=["model-says-not-covered", "unknown-citation", "number-not-in-passages"],
)
async def test_a_refusal_or_failed_check_is_not_covered(
    db: AsyncSession, model_reply: ModelAnswer
) -> None:
    """Fails if an answer the checks refuse could still be shown (FR-005)."""
    await a_corpus(db)
    user = await a_user(db)

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(model_reply))

    assert result.status == "not_covered"
    assert result.answer == NOT_COVERED_MESSAGE and result.citations == []


async def test_a_partial_answer_names_what_it_does_not_cover(db: AsyncSession) -> None:
    """Fails if the uncovered part of a mixed question is lost (spec clarification)."""
    await a_corpus(db)
    user = await a_user(db)
    model_reply = reply(uncovered_part="Rental income isn't covered by these sources.")

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(model_reply))

    assert result.status == "answered"
    assert result.uncovered_part == "Rental income isn't covered by these sources."


async def test_asking_for_ones_own_tax_adds_the_fixed_tax_page_line(db: AsyncSession) -> None:
    """Fails if the Tax page pointer is missing, or written by the AI rather than code (FR-007)."""
    await a_corpus(db)
    user = await a_user(db)

    result = await ask(
        db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(reply(asks_own_tax_figure=True))
    )

    assert result.tax_page_line == TAX_PAGE_LINE


@pytest.mark.parametrize(
    "failure",
    [AnswerError("down"), asyncio.TimeoutError()],
    ids=["api-error", "timeout"],
)
async def test_an_ai_failure_is_unavailable(db: AsyncSession, failure: Exception) -> None:
    """Fails if a Gemini error or timeout shows anything but "try again later"."""
    await a_corpus(db)
    user = await a_user(db)

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(failure))

    assert result.status == "unavailable"
    assert result.answer == UNAVAILABLE_MESSAGE and result.citations == []


async def test_the_31st_question_in_an_hour_is_limited_without_asking(db: AsyncSession) -> None:
    """Fails if one user can ask more than 30 questions an hour (FR-009a)."""
    await a_corpus(db)
    user = await a_user(db)
    now = datetime.now(UTC)
    db.add_all(
        AskRequest(user_id=user.id, created_at=now - timedelta(minutes=i)) for i in range(30)
    )
    await db.flush()
    answerer = FakeAnswerer(reply())

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), answerer)

    assert result.status == "limited" and result.answer == LIMITED_MESSAGE
    assert not answerer.calls


async def test_the_whole_app_daily_cap_stops_every_user(db: AsyncSession) -> None:
    """Fails if Ask (and MCP searches) could use up the shared free quota (FR-009b)."""
    await a_corpus(db)
    others = [await a_user(db, f"other{i}@example.com") for i in range(5)]
    now = datetime.now(UTC)
    db.add_all(
        AskRequest(user_id=others[i % 5].id, created_at=now - timedelta(minutes=i))
        for i in range(200)
    )
    await db.flush()
    user = await a_user(db)
    answerer = FakeAnswerer(reply())
    embedder = FakeEmbedder()

    result = await ask(db, user.id, QUESTION, embedder, answerer)

    assert result.status == "daily_limit" and result.answer == DAILY_LIMIT_MESSAGE
    assert not answerer.calls


async def test_before_the_first_build_it_is_not_ready(db: AsyncSession) -> None:
    """Fails if a question before the corpus exists gets anything but "not ready yet"."""
    user = await a_user(db)
    answerer = FakeAnswerer(reply())

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), answerer)

    assert result.status == "not_ready" and result.answer == NOT_READY_MESSAGE
    assert not answerer.calls


async def test_records_older_than_a_day_are_deleted(db: AsyncSession) -> None:
    """Fails if question records pile up beyond the day the limits need."""
    await a_corpus(db)
    user = await a_user(db)
    db.add(AskRequest(user_id=user.id, created_at=datetime.now(UTC) - timedelta(days=2)))
    await db.flush()

    await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(reply()))

    assert await questions_recorded(db) == 1


async def test_an_ai_failure_is_logged_without_the_question(
    db: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Fails if a Gemini failure leaves no trace for whoever runs the app, or if the log
    holds the question (only who asked and when may be kept, FR-009)."""
    await a_corpus(db)
    user = await a_user(db)

    with caplog.at_level(logging.WARNING, logger="app.rag.service"):
        await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(AnswerError("ServerError")))

    assert "ServerError" in caplog.text
    assert QUESTION not in caplog.text


async def test_a_refused_own_tax_question_still_points_to_the_tax_page(db: AsyncSession) -> None:
    """Fails if "How much tax do I owe?" gets only the not-covered message when the model says
    the passages don't cover it (seen live on 2026-11-11): the user must still be pointed to
    the Tax page, where their figure is (FR-007)."""
    await a_corpus(db)
    user = await a_user(db)
    model_reply = reply(not_covered=True, citations=[], answer="", asks_own_tax_figure=True)

    result = await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(model_reply))

    assert result.status == "not_covered" and result.answer == NOT_COVERED_MESSAGE
    assert result.tax_page_line == TAX_PAGE_LINE
