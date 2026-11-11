"""The tax assistant's corpus and question records (feature 006, task T003; data-model.md).

The corpus holds only FBR's own texts, by URL and checksum (constitution, Principle II); it is
replaced as a whole on each build. Questions are counted, never stored: an ask_requests row has
only who and when (FR-009), for the per-user hourly limit and the whole-app daily cap (FR-009a,
FR-009b; MCP searches write one too).
"""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Gemini's gemini-embedding-001 at 768 dimensions (design addendum 2026-11-11, decision 1).
EMBEDDING_DIMENSIONS = 768


class DocumentKind(enum.StrEnum):
    """How a source is cited: the Ordinance as law, FBR's filing manual as guidance."""

    LAW = "law"
    GUIDANCE = "guidance"


class CorpusDocument(Base):
    """One FBR source file, as `app/rag/sources.yaml` names it."""

    __tablename__ = "corpus_documents"

    # From sources.yaml, e.g. "ito-2001-2025-07-31".
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    kind: Mapped[DocumentKind] = mapped_column(
        Enum(
            DocumentKind,
            name="corpus_document_kind",
            values_callable=lambda members: [m.value for m in members],
        )
    )
    url: Mapped[str] = mapped_column(String)
    # The downloaded file's SHA-256 (64 hex characters); a different file stops the build.
    sha256: Mapped[str] = mapped_column(String(64))
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Passage(Base):
    """A searchable piece of a source, with the exact place it comes from."""

    __tablename__ = "passages"
    __table_args__ = (
        # Nearest-first search by cosine distance (research R4).
        Index(
            "ix_passages_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("corpus_documents.id", ondelete="CASCADE"), index=True
    )
    # Stable and citable, e.g. "§149(1)" or "ch. 14.3".
    location: Mapped[str] = mapped_column(String)
    # 1-based page in the source PDF.
    page: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))


class AskRequest(Base):
    """One question asked (or one MCP search): who and when, never the text."""

    __tablename__ = "ask_requests"
    __table_args__ = (Index("ix_ask_requests_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
