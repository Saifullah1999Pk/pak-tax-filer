"""Search over the corpus (feature 006, task T008; research R4).

The FakeEmbedder places texts that share words close together, so these tests run on the
migrated test database with no network.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from rag_helpers import a_corpus

from app.rag.embed import FakeEmbedder
from app.rag.models import DocumentKind
from app.rag.search import search

pytestmark = pytest.mark.anyio


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
