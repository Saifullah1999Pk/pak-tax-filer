"""The wealth statement's request shapes (feature 005, task T006; contracts/wealth-api.md).

Money arrives as decimal strings of whole rupees (docs/api-conventions.md), never JSON numbers,
and becomes Decimal at once (Principle I). Nothing may be negative except last year's net
assets (FR-003).
"""

import re
from datetime import datetime
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


# Response shapes (task T010). Money goes out as decimal strings, never JSON numbers.


class AssetOut(BaseModel):
    """A saved asset row."""

    category: AssetCategory
    description: str
    amount: str


class LiabilityOut(BaseModel):
    """A saved liability row."""

    description: str
    creditor: str | None
    amount: str


class StatementOut(BaseModel):  # pylint: disable=too-many-instance-attributes
    """What the user saved; empty, with saved_at null, if never saved."""

    previous_net_assets: str | None
    assets: list[AssetOut]
    liabilities: list[LiabilityOut]
    other_exempt_income: str
    foreign_remittance: str
    inheritance: str
    gifts_received: str
    family_contribution: str
    gifts_given: str
    expenses: dict[str, str]
    saved_at: datetime | None


class AutoFilledLine(BaseModel):
    """A line filled in from confirmed certificates, read-only, naming them (FR-004)."""

    line: str | None
    label: str
    amount: str
    certificates: list[str]
    provisional: bool = False


class StepOut(BaseModel):
    """One breakdown step with its TY2026 form line (FR-009)."""

    description: str
    form_line: str
    result: str


class ResultOut(BaseModel):  # pylint: disable=too-many-instance-attributes
    """The reconciliation, recalculated on every request (FR-012); figures null if not ready."""

    not_ready_reason: str | None
    message: str | None
    net_assets: str | None
    increase: str | None
    inflows: str | None
    outflows: str | None
    unreconciled: str | None
    direction: str | None
    where_to_look: list[str]
    steps: list[StepOut]
    summary: str | None


class WealthOut(BaseModel):
    """GET and PUT /api/wealth/{tax_year} (contracts/wealth-api.md)."""

    tax_year: str
    statement: StatementOut
    auto_filled: list[AutoFilledLine]
    certificates_changed: bool
    result: ResultOut
    label: str
