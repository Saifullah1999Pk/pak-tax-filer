"""Tax assistant tables (feature 006, task T003; specs/006-rag-mcp/data-model.md).

The corpus (FBR texts with 768-number Gemini embeddings and a cosine index), question records
(who and when only) and personal access tokens (hashes only). The vector extension is already
on (0001_enable_vector).

Revision ID: 0007_rag_mcp
Revises: 0006_wealth
Create Date: 2026-11-11 17:10:35.373387

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "0007_rag_mcp"
down_revision: str | Sequence[str] | None = "0006_wealth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "corpus_documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("kind", sa.Enum("law", "guidance", name="corpus_document_kind"), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ask_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ask_requests_created_at"), "ask_requests", ["created_at"], unique=False
    )
    op.create_index(
        "ix_ask_requests_user_created", "ask_requests", ["user_id", "created_at"], unique=False
    )
    op.create_table(
        "passages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["corpus_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_passages_document_id"), "passages", ["document_id"], unique=False)
    op.create_index(
        "ix_passages_embedding",
        "passages",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "personal_access_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_personal_access_tokens_user_id"),
        "personal_access_tokens",
        ["user_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_personal_access_tokens_user_id"), table_name="personal_access_tokens")
    op.drop_table("personal_access_tokens")
    op.drop_index(
        "ix_passages_embedding",
        table_name="passages",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_passages_document_id"), table_name="passages")
    op.drop_table("passages")
    op.drop_index("ix_ask_requests_user_created", table_name="ask_requests")
    op.drop_index(op.f("ix_ask_requests_created_at"), table_name="ask_requests")
    op.drop_table("ask_requests")
    op.drop_table("corpus_documents")
    sa.Enum(name="corpus_document_kind").drop(op.get_bind(), checkfirst=True)
