"""Wealth statement tables (feature 005, task T005; specs/005-wealth-statement/data-model.md).

Revision ID: 0006_wealth
Revises: 0005_extraction_attempts
Create Date: 2026-11-10 14:00:00

"""
# Alembic requires these lowercase names and numbered file names, and fills in `op` at run time.
# pylint: disable=invalid-name,no-member

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_wealth"
down_revision: str | Sequence[str] | None = "0005_extraction_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASSET_CATEGORIES = (
    "immovable_property",
    "investments",
    "advances_receivables",
    "cash_in_hand",
    "bank_account",
    "equipment",
    "animals",
    "motor_vehicle",
    "precious_possession",
    "household_effects",
    "personal_items",
    "assets_in_others_names",
    "other_asset",
)
EXPENSE_CATEGORIES = (
    "rent",
    "rates_taxes",
    "vehicle",
    "electricity",
    "water",
    "gas",
    "telephone",
    "asset_insurance",
    "medical",
    "educational",
    "club",
    "functions",
    "donations_zakat",
    "other_household",
    "foreign_travel",
    "local_travel",
)


def _money(name: str, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.Numeric(14, 0), nullable=nullable)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "wealth_statements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tax_year", sa.String(), nullable=False),
        _money("previous_net_assets", nullable=True),
        _money("other_exempt_income"),
        _money("foreign_remittance"),
        _money("inheritance"),
        _money("gifts_received"),
        _money("family_contribution"),
        _money("gifts_given"),
        sa.Column("certificate_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tax_year"),
    )
    op.create_table(
        "wealth_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.Enum(*ASSET_CATEGORIES, name="asset_category"), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        _money("amount"),
        sa.ForeignKeyConstraint(["statement_id"], ["wealth_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wealth_assets_statement_id", "wealth_assets", ["statement_id"])
    op.create_table(
        "wealth_liabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("creditor", sa.String(length=200), nullable=True),
        _money("amount"),
        sa.ForeignKeyConstraint(["statement_id"], ["wealth_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wealth_liabilities_statement_id", "wealth_liabilities", ["statement_id"])
    op.create_table(
        "wealth_expenses",
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "category", sa.Enum(*EXPENSE_CATEGORIES, name="expense_category"), nullable=False
        ),
        _money("amount"),
        sa.ForeignKeyConstraint(["statement_id"], ["wealth_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("statement_id", "category"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("wealth_expenses")
    op.drop_index("ix_wealth_liabilities_statement_id", table_name="wealth_liabilities")
    op.drop_table("wealth_liabilities")
    op.drop_index("ix_wealth_assets_statement_id", table_name="wealth_assets")
    op.drop_table("wealth_assets")
    op.drop_table("wealth_statements")
    sa.Enum(name="expense_category").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="asset_category").drop(op.get_bind(), checkfirst=True)
