"""Tax rates, keyed by tax year (feature 004, task T008).

Every value here MUST come from FBR's own gazetted documents (the Income Tax Ordinance 2001 as
amended by the relevant Finance Act, and FBR's guides) and record its source document, section
and tax year. Third-party calculators, blogs and news articles are never a source
(constitution, Principle II).

This module is guarded: the Claude Code tax-rates hook asks for human approval before any change
here, and every change must be called out in review.

A new tax year is a new module (like ty2026.py) added to RATES; the engine doesn't change (FR-008).
"""

from app.tax.rates import ty2026
from app.tax.rates.model import TaxYearRates

RATES: dict[str, TaxYearRates] = {
    ty2026.RATES.tax_year: ty2026.RATES,
}


def rates_for(tax_year: str) -> TaxYearRates:
    """The rates for a tax year; KeyError if there are none (never another year's rates)."""
    return RATES[tax_year]
