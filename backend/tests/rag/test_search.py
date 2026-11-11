"""Search over the corpus (feature 006, task T008; research R4).

The FakeEmbedder places texts that share words close together, so these tests run on the
migrated test database with no network.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed import FakeEmbedder
from app.rag.models import CorpusDocument, DocumentKind, Passage
from app.rag.search import search

pytestmark = pytest.mark.anyio

TEXTS = {
    "§149(1)": "Every employer paying salary shall deduct tax from the salary at the average rate.",
    "§151(1)": "A bank paying profit on debt shall deduct tax from the profit paid.",
    "§12(1)": "Salary received by an employee is chargeable to tax under the head salary.",
    "§13(1)": "Perquisites provided by an employer are valued and taxed with salary.",
    "§7B(1)": "Tax is imposed on profit on debt at the rate in the First Schedule.",
    "§12(2)": "Salary means any amount received by an employee from employment.",
    "ch. 14.3": "Reconciliation of net assets compares inflows with the increase in wealth.",
}


async def a_corpus(db: AsyncSession) -> None:
    """The passages above, embedded with the fake embedder."""
    now = datetime.now(UTC)
    db.add_all(
        [
            CorpusDocument(
                id="ito",
                title="Income Tax Ordinance, 2001",
                kind=DocumentKind.LAW,
                url="https://fbr.example/ito.pdf",
                sha256="a" * 64,
                built_at=now,
            ),
            CorpusDocument(
                id="manual",
                title="Return manual",
                kind=DocumentKind.GUIDANCE,
                url="https://fbr.example/manual.pdf",
                sha256="b" * 64,
                built_at=now,
            ),
        ]
    )
    await db.flush()
    vectors = await FakeEmbedder().embed_documents(list(TEXTS.values()))
    for (location, text), vector in zip(TEXTS.items(), vectors):
        db.add(
            Passage(
                document_id="manual" if location.startswith("ch.") else "ito",
                location=location,
                page=327,
                text=text,
                embedding=vector,
            )
        )
    await db.flush()


async def test_the_nearest_passages_come_first_with_their_citation(db: AsyncSession) -> None:
    """Fails if the best match isn't first, or a result lacks what a citation needs."""
    await a_corpus(db)

    result = await search(db, FakeEmbedder(), "Does my employer deduct tax from my salary?")

    assert result.covered
    best = result.passages[0]
    assert best.location == "§149(1)"
    assert (best.title, best.kind, best.page) == (
        "Income Tax Ordinance, 2001",
        DocumentKind.LAW,
        327,
    )
    assert best.text.startswith("Every employer")
    scores = [p.score for p in result.passages]
    assert scores == sorted(scores, reverse=True)


async def test_at_most_five_passages_are_returned(db: AsyncSession) -> None:
    """Fails if more than the top 5 reach the answer (research R4)."""
    await a_corpus(db)

    result = await search(db, FakeEmbedder(), "salary tax employer employee profit debt")

    assert len(result.passages) == 5


async def test_a_question_far_from_every_passage_is_not_covered(db: AsyncSession) -> None:
    """Fails if a question the corpus doesn't cover is answered from whatever is nearest."""
    await a_corpus(db)

    result = await search(db, FakeEmbedder(), "What is the sales tax on imported cars?", cutoff=0.5)

    assert not result.covered


async def test_an_empty_corpus_is_not_covered(db: AsyncSession) -> None:
    """Fails if a search before the first build raises instead of finding nothing."""
    result = await search(db, FakeEmbedder(), "Anything?")

    assert result.passages == [] and not result.covered
