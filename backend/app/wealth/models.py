"""Wealth statement tables (feature 005, task T005; specs/005-wealth-statement/data-model.md).

Only the user's entries are stored; the reconciliation is recalculated on every view (FR-012).
MONEY is numeric(14,0): whole rupees, never a float (constitution, Principle I). Everything is
deleted with the user.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

MONEY = Numeric(14, 0)


class AssetCategory(enum.StrEnum):
    """The TY2026 IRIS asset categories (research R4; SRO 1495(I)/2026 PDF pp. 38-39)."""

    IMMOVABLE_PROPERTY = "immovable_property"
    INVESTMENTS = "investments"
    ADVANCES_RECEIVABLES = "advances_receivables"
    CASH_IN_HAND = "cash_in_hand"
    BANK_ACCOUNT = "bank_account"
    EQUIPMENT = "equipment"
    ANIMALS = "animals"
    MOTOR_VEHICLE = "motor_vehicle"
    PRECIOUS_POSSESSION = "precious_possession"
    HOUSEHOLD_EFFECTS = "household_effects"
    PERSONAL_ITEMS = "personal_items"
    ASSETS_IN_OTHERS_NAMES = "assets_in_others_names"
    OTHER_ASSET = "other_asset"


class ExpenseCategory(enum.StrEnum):
    """The IRIS personal-expense categories (research R3; their total is line 7089)."""

    RENT = "rent"
    RATES_TAXES = "rates_taxes"
    VEHICLE = "vehicle"
    ELECTRICITY = "electricity"
    WATER = "water"
    GAS = "gas"
    TELEPHONE = "telephone"
    ASSET_INSURANCE = "asset_insurance"
    MEDICAL = "medical"
    EDUCATIONAL = "educational"
    CLUB = "club"
    FUNCTIONS = "functions"
    DONATIONS_ZAKAT = "donations_zakat"
    OTHER_HOUSEHOLD = "other_household"
    FOREIGN_TRAVEL = "foreign_travel"
    LOCAL_TRAVEL = "local_travel"


def _pg_enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    """A PostgreSQL enum storing the members' values, not their names."""
    return Enum(enum_class, name=name, values_callable=lambda members: [m.value for m in members])


class WealthStatement(Base):
    """One user's statement for one tax year: their entries, never the result."""

    __tablename__ = "wealth_statements"
    __table_args__ = (UniqueConstraint("user_id", "tax_year"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tax_year: Mapped[str] = mapped_column(String)
    # None means not entered (the result is then not ready); may be negative.
    previous_net_assets: Mapped[Decimal | None] = mapped_column(MONEY)
    other_exempt_income: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    foreign_remittance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    inheritance: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    gifts_received: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    family_contribution: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    gifts_given: Mapped[Decimal] = mapped_column(MONEY, default=Decimal(0))
    # Sorted ids of the confirmed certificates used at the last save (research R7).
    certificate_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    assets: Mapped[list["WealthAsset"]] = relationship(
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="WealthAsset.position",
        lazy="selectin",
    )
    liabilities: Mapped[list["WealthLiability"]] = relationship(
        back_populates="statement",
        cascade="all, delete-orphan",
        order_by="WealthLiability.position",
        lazy="selectin",
    )
    expenses: Mapped[list["WealthExpense"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan", lazy="selectin"
    )


class WealthAsset(Base):
    """One asset row, valued at cost."""

    __tablename__ = "wealth_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wealth_statements.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    category: Mapped[AssetCategory] = mapped_column(_pg_enum(AssetCategory, "asset_category"))
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    statement: Mapped[WealthStatement] = relationship(back_populates="assets")


class WealthLiability(Base):
    """One liability row."""

    __tablename__ = "wealth_liabilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wealth_statements.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    description: Mapped[str] = mapped_column(String(200))
    creditor: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(MONEY)

    statement: Mapped[WealthStatement] = relationship(back_populates="liabilities")


class WealthExpense(Base):
    """One personal-expense category's amount; a missing category means zero."""

    __tablename__ = "wealth_expenses"

    statement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wealth_statements.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[ExpenseCategory] = mapped_column(
        _pg_enum(ExpenseCategory, "expense_category"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)

    statement: Mapped[WealthStatement] = relationship(back_populates="expenses")
