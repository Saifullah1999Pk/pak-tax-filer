"""The shape of a tax year's rates (feature 004, task T005, specs/004-tax-engine/data-model.md).

Rates are data, one module per tax year, each value carrying the FBR document, location and
Finance Act it comes from (constitution Principle II). Every number is a Decimal built from a
string, never a float (Principle I). Adding a tax year means adding data, not changing the engine.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Source:
    """Where a rule comes from in FBR's own law text."""

    # e.g. "Income Tax Ordinance, 2001 (amended up to 31.07.2025)"
    document: str
    # e.g. "First Schedule, Part I, Division I, clause (2), row 3 (PDF page 493)"
    location: str
    # e.g. "Finance Act 2025"
    finance_act: str


@dataclass(frozen=True)
class Rule:
    """One rate or limit, with its source."""

    value: Decimal
    source: Source


@dataclass(frozen=True)
class Band:
    """A row of the salaried table: income over `lower` and not over `upper` (None: no limit)
    pays `fixed` plus `rate` times the amount over `lower`."""

    lower: Decimal
    upper: Decimal | None
    fixed: Decimal
    rate: Decimal
    source: Source


@dataclass(frozen=True)
class TaxYearRates:  # pylint: disable=too-many-instance-attributes  # one field per rule
    """Every rate the engine uses for one tax year."""

    tax_year: str
    salary_bands: tuple[Band, ...]
    # The salaried table applies where salary exceeds this share of taxable income.
    salary_share_threshold: Rule
    # The surcharge rate on salary tax, where taxable income exceeds the threshold.
    surcharge_rate: Rule
    surcharge_threshold: Rule
    # The tax on gross bank profit, and the profit above which it no longer applies.
    profit_rate: Rule
    profit_limit: Rule
    # Final amounts to the nearest rupee, 50 paisa or more up.
    rounding: Source
