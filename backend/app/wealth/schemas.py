"""The wealth statement's request shapes (feature 005, task T006; contracts/wealth-api.md).

Money arrives as decimal strings of whole rupees (docs/api-conventions.md), never JSON numbers,
and becomes Decimal at once (Principle I). Nothing may be negative except last year's net
assets (FR-003). Response shapes come with the endpoint (T010).
"""

import re
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field

from app.wealth.models import AssetCategory, ExpenseCategory

_WHOLE_RUPEES = re.compile(r"-?\d{1,14}")


def _rupees(value: object) -> Decimal:
    """A decimal string of whole rupees (up to 14 digits), as an exact Decimal."""
    if not isinstance(value, str) or not _WHOLE_RUPEES.fullmatch(value.strip()):
        raise ValueError("must be whole rupees, written as a string of digits")
    return Decimal(value.strip())


def _not_negative(value: Decimal) -> Decimal:
    if value < 0:
        raise ValueError("must not be negative")
    return value


# Any sign (only last year's net assets), and the usual non-negative amount.
SignedRupees = Annotated[Decimal, BeforeValidator(_rupees)]
Rupees = Annotated[Decimal, BeforeValidator(_rupees), AfterValidator(_not_negative)]


class AssetIn(BaseModel):
    """One asset row: an IRIS category, a description, its value at cost."""

    model_config = ConfigDict(extra="forbid")

    category: AssetCategory
    description: str = Field(min_length=1, max_length=200)
    amount: Rupees


class LiabilityIn(BaseModel):
    """One liability row."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=200)
    creditor: str | None = Field(default=None, max_length=200)
    amount: Rupees


class StatementIn(BaseModel):
    """The whole statement, replaced on every save (research R8)."""

    model_config = ConfigDict(extra="forbid")

    previous_net_assets: SignedRupees | None
    assets: list[AssetIn] = Field(default_factory=list, max_length=200)
    liabilities: list[LiabilityIn] = Field(default_factory=list, max_length=200)
    other_exempt_income: Rupees = Decimal(0)
    foreign_remittance: Rupees = Decimal(0)
    inheritance: Rupees = Decimal(0)
    gifts_received: Rupees = Decimal(0)
    family_contribution: Rupees = Decimal(0)
    gifts_given: Rupees = Decimal(0)
    # A missing category means zero (data model).
    expenses: dict[ExpenseCategory, Rupees] = Field(default_factory=dict)
