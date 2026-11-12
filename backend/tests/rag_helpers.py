"""Shared test data for feature 006: a small corpus, a user and a faithful model reply."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.rag.answer import ModelAnswer
from app.rag.embed import FakeEmbedder
from app.rag.models import CorpusDocument, DocumentKind, Passage

TEXTS = {
    "§149(1)": "Every employer paying salary shall deduct tax from the salary at the average rate.",
    "§151(1)": "A bank paying profit on debt shall deduct tax from the profit paid.",
    "§12(1)": "Salary received by an employee is chargeable to tax under the head salary.",
    "§13(1)": "Perquisites provided by an employer are valued and taxed with salary.",
    "§7B(1)": "Tax is imposed on profit on debt at the rate in the First Schedule.",
    "§12(2)": "Salary means any amount received by an employee from employment.",
    "ch. 14.3": "Reconciliation of net assets compares inflows with the increase in wealth.",
}

QUESTION = "Does my employer deduct tax from my salary?"


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


async def a_user(db: AsyncSession, email: str = "asker@example.com") -> User:
    """A synthetic user (no login needed for service tests)."""
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    return user


def reply(**changes: object) -> ModelAnswer:
    """A faithful model reply citing the best passage (§149(1)), with any changes."""
    values: dict[str, object] = {
        "answer": "Yes: every employer paying salary deducts tax at the average rate.",
        "citations": ["P1"],
        "not_covered": False,
        "uncovered_part": None,
        "asks_own_tax_figure": False,
    }
    values.update(changes)
    return ModelAnswer(**values)  # type: ignore[arg-type]


class SpyEmbedder(FakeEmbedder):
    """The fake embedder, recording every question it embeds."""

    def __init__(self) -> None:
        self.questions: list[str] = []

    async def embed_query(self, text: str) -> list[float]:
        """Record the question, then embed it as the fake does."""
        self.questions.append(text)
        return await super().embed_query(text)


def sessions_of(db: AsyncSession) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """A session factory that always hands out the test's own (rolled-back) session, for code
    that opens its own sessions (007's agent tools)."""

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield db

    return sessions
