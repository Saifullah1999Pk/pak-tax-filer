"""The local answers script, with fakes on the test database (feature 006, task T024).

The real run uses the API key and the built corpus and isn't run in CI; this checks that each
question is put down to the step that refused it, the same steps ask() takes.
"""

import pytest
from rag_helpers import QUESTION, a_corpus, reply
from sqlalchemy.ext.asyncio import AsyncSession

from evals.answers.run import ask_one, render

from app.rag.answer import AnswerError, FakeAnswerer
from app.rag.embed import FakeEmbedder

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("question", "model_reply", "outcome"),
    [
        (QUESTION, reply(), "answered"),
        ("کیا مجھے ٹیکس دینا ہوگا؟", reply(), "refused: not English"),
        ("What is the sales tax on imported cars?", reply(), "refused: cut-off"),
        (QUESTION, reply(not_covered=True, citations=[], answer=""), "refused: model"),
        (QUESTION, reply(citations=["P9"]), "refused: checks"),
        (QUESTION, AnswerError("ServerError"), "unavailable"),
    ],
)
async def test_each_question_is_put_down_to_its_step(
    db: AsyncSession, question: str, model_reply: object, outcome: str
) -> None:
    """Fails if a refusal is reported at the wrong step, so a check failure looks like the
    model's own refusal (or the other way round)."""
    await a_corpus(db)

    row = await ask_one(db, FakeEmbedder(), FakeAnswerer(model_reply), question, expected=None)  # type: ignore[arg-type]

    assert row.outcome == outcome


async def test_the_report_counts_answers_and_refusals(db: AsyncSession) -> None:
    """Fails if the report doesn't say how many in-corpus questions were answered and how many
    out-of-corpus ones refused."""
    await a_corpus(db)
    answered = await ask_one(db, FakeEmbedder(), FakeAnswerer(reply()), QUESTION, ("§149",))
    refused = await ask_one(
        db, FakeEmbedder(), FakeAnswerer(reply()), "What is the sales tax on cars?", None
    )

    report = render([answered, refused], model="gemini-test")

    assert "In-corpus answered: 1 of 1" in report
    assert "Out-of-corpus refused: 1 of 1" in report
