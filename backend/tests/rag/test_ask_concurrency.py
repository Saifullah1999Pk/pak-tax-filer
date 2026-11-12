"""The question limits hold under questions sent together (feature 006, FR-009a, backend review M4).

Unlike the other tests, each question here needs its own database connection so they truly run
at the same time; rows are committed to the test database and removed afterwards.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from rag_helpers import QUESTION, a_corpus, reply
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import User
from app.rag.answer import FakeAnswerer
from app.rag.embed import FakeEmbedder
from app.rag.models import AskRequest, CorpusDocument
from app.rag.service import ask

pytestmark = pytest.mark.anyio

EMAIL = "ask-race@example.com"


async def test_questions_sent_together_cannot_get_past_the_hourly_limit(
    test_database_url: str,
) -> None:
    """Fails if questions sent at the same moment all read the count before any is recorded,
    so one user gets more than 30 an hour (the app-wide advisory lock in use_question)."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as setup:
        user = User(email=EMAIL, password_hash="not-a-real-hash")
        setup.add(user)
        await a_corpus(setup)
        now = datetime.now(UTC)
        # One short of the limit.
        setup.add_all(
            AskRequest(user_id=user.id, created_at=now - timedelta(minutes=i)) for i in range(29)
        )
        await setup.commit()

    async def one_question() -> str:
        async with sessions() as db:
            result = await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(reply()))
            return result.status

    try:
        statuses = await asyncio.gather(*(one_question() for _ in range(5)))
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(AskRequest).where(AskRequest.user_id == user.id))
            await cleanup.execute(delete(CorpusDocument))
            await cleanup.execute(delete(User).where(User.email == EMAIL))
            await cleanup.commit()
        await engine.dispose()

    assert sorted(statuses) == ["answered", "limited", "limited", "limited", "limited"], statuses
