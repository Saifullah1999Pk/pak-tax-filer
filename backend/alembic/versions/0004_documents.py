"""Documents and extracted fields (feature 003, specs/003-document-extraction/data-model.md).

Revision ID: 0004_documents
Revises: 0003_taxpayer_profiles
Create Date: 2026-11-05 16:37:45.990129

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa  # pylint: disable=unused-import
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_documents"
down_revision: str | Sequence[str] | None = "0003_taxpayer_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "doc_type",
            sa.Enum("salary_certificate", "bank_profit_certificate", name="doc_type"),
            nullable=False,
        ),
        sa.Column("tax_year", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "uploaded", "extracting", "needs_review", "confirmed", "failed", name="doc_status"
            ),
            nullable=False,
        ),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"], unique=False)
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "name",
            sa.Enum(
                "tax_year",
                "gross_salary",
                "taxable_salary",
                "tax_deducted",
                "profit_amount",
                "tax_withheld",
                name="field_name",
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("text_value", sa.String(), nullable=True),
        sa.Column(
            "confidence", sa.Enum("high", "medium", "low", name="confidence"), nullable=False
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_label", sa.String(), nullable=True),
        sa.Column("rule_reason", sa.String(), nullable=True),
        sa.Column("user_edited", sa.Boolean(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("extracted_fields")
    op.drop_index(op.f("ix_documents_user_id"), table_name="documents")
    op.drop_table("documents")
    # Dropping the tables leaves their enum types behind; drop them so upgrade works again.
    for enum_name in ("confidence", "field_name", "doc_status", "doc_type"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
