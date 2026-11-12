"""The RAG and token tables (feature 006, task T003; specs/006-rag-mcp/data-model.md).

Run against the migrated test database, as the other features' table tests are.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import Base
from app.rag.models import EMBEDDING_DIMENSIONS, AskRequest, CorpusDocument, DocumentKind, Passage
from app.tokens.models import PersonalAccessToken

pytestmark = pytest.mark.anyio

NEW_TABLES = {"corpus_documents", "passages", "ask_requests", "personal_access_tokens"}


def vector(*first: float) -> list[float]:
    """A 768-number embedding: the given leading values, then zeros."""
    return [*first, *([0.0] * (EMBEDDING_DIMENSIONS - len(first)))]


async def a_user(db: AsyncSession, email: str = "rag@example.com") -> User:
    """A synthetic user to own tokens and question records."""
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    return user


async def a_document(db: AsyncSession) -> CorpusDocument:
    """A corpus document with a dummy checksum (no file is downloaded here)."""
    document = CorpusDocument(
        id="ito-2001-2025-07-31",
        title="Income Tax Ordinance, 2001",
        kind=DocumentKind.LAW,
        url="https://download1.fbr.gov.pk/Docs/example.pdf",
        sha256="a" * 64,
        built_at=datetime.now(UTC),
    )
    db.add(document)
    await db.flush()
    return document


async def test_the_tables_and_the_vector_index_exist(db: AsyncSession) -> None:
    """Fails if the migration is missing a table or the cosine index on the embeddings."""
    tables = set(
        (await db.execute(text("select tablename from pg_tables where schemaname = 'public'")))
        .scalars()
        .all()
    )
    index = (
        await db.execute(
            text(
                "select indexdef from pg_indexes"
                " where tablename = 'passages' and indexdef ilike '%hnsw%'"
            )
        )
    ).scalar_one()

    assert NEW_TABLES <= tables
    assert "vector_cosine_ops" in index


async def test_passages_are_found_nearest_first_and_deleted_with_their_document(
    db: AsyncSession,
) -> None:
    """Fails if a 768-number embedding isn't stored, cosine order is wrong, or a document's
    passages outlive it (the corpus is replaced as a whole on each build)."""
    document = await a_document(db)
    near = Passage(
        document_id=document.id,
        location="§149(1)",
        page=1,
        text="Near.",
        embedding=vector(1.0, 0.1),
    )
    far = Passage(
        document_id=document.id, location="§12(1)", page=2, text="Far.", embedding=vector(0.0, 1.0)
    )
    db.add_all([far, near])
    await db.flush()

    ordered = (
        await db.scalars(
            select(Passage.location).order_by(Passage.embedding.cosine_distance(vector(1.0, 0.0)))
        )
    ).all()
    assert ordered == ["§149(1)", "§12(1)"]

    await db.execute(delete(CorpusDocument).where(CorpusDocument.id == document.id))
    remaining = (await db.execute(text("select count(*) from passages"))).scalar_one()
    assert remaining == 0


async def test_tokens_and_question_records_are_deleted_with_their_user(db: AsyncSession) -> None:
    """Fails if a user's tokens or question records outlive the user."""
    user = await a_user(db)
    now = datetime.now(UTC)
    db.add(AskRequest(user_id=user.id, created_at=now))
    db.add(
        PersonalAccessToken(
            user_id=user.id,
            name="Claude Code",
            token_hash="b" * 64,
            prefix="ptx_abcd",
            created_at=now,
            expires_at=now + timedelta(days=90),
        )
    )
    await db.flush()

    await db.execute(delete(User).where(User.id == user.id))
    left = (
        await db.execute(
            text(
                "select (select count(*) from ask_requests)"
                " + (select count(*) from personal_access_tokens)"
            )
        )
    ).scalar_one()
    assert left == 0


async def test_a_token_hash_is_unique(db: AsyncSession) -> None:
    """Fails if two tokens could share a hash (the MCP server finds a token by its hash)."""
    user = await a_user(db)
    now = datetime.now(UTC)
    for _ in range(2):
        db.add(
            PersonalAccessToken(
                id=uuid.uuid4(),
                user_id=user.id,
                name="Gemini CLI",
                token_hash="c" * 64,
                prefix="ptx_efgh",
                created_at=now,
                expires_at=now + timedelta(days=90),
            )
        )
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_the_migration_matches_the_models(db: AsyncSession) -> None:
    """Fails if migration 0007 creates something different from what the models describe."""
    connection = await db.connection()

    def differences(sync_connection) -> list[object]:  # type: ignore[no-untyped-def]
        context = MigrationContext.configure(sync_connection)
        diff = compare_metadata(context, Base.metadata)
        return [d for d in diff if NEW_TABLES & set(_tables(d))]

    assert await connection.run_sync(differences) == []


def _tables(difference: object) -> list[str]:
    """The table names mentioned in one autogenerate difference (nested for column changes)."""
    if isinstance(difference, list):
        return [name for item in difference for name in _tables(item)]
    names = []
    for part in difference if isinstance(difference, tuple) else ():
        name = getattr(part, "name", None) if not isinstance(part, str) else None
        table = getattr(part, "table", None)
        if table is not None and getattr(table, "name", None):
            names.append(table.name)
        elif name and hasattr(part, "columns"):
            names.append(name)
        elif isinstance(part, str) and part in NEW_TABLES:
            names.append(part)
    return names
