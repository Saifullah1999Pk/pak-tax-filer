"""Extraction attempts, for the daily limit (feature 003 FR-017; 003 data-model.md, 2026-11-09).

Revision ID: 0005_extraction_attempts
Revises: 0004_documents
Create Date: 2026-11-09 13:00:00

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0005_extraction_attempts"
down_revision: str | Sequence[str] | None = "0004_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "extraction_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extraction_attempts_user_id_attempted_at",
        "extraction_attempts",
        ["user_id", "attempted_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_extraction_attempts_user_id_attempted_at", table_name="extraction_attempts")
    op.drop_table("extraction_attempts")
