"""The rates module: every rule sourced, the salary table self-consistent (feature 004, T006).

Research R10: each band's fixed amount must equal the tax at the top of the band below. This
would have caught FBR Circular 01 of 2025-26's two wrong amounts (345,000 and 615,000).
"""

from dataclasses import fields
from decimal import Decimal

import pytest

from app.tax.rates import RATES, rates_for
from app.tax.rates.model import Band, Rule, Source, TaxYearRates

YEARS = sorted(RATES)


def sources_of(rates: TaxYearRates) -> list[tuple[str, Source]]:
    """Every source in a year's rates, labelled by the rule it belongs to."""
    found: list[tuple[str, Source]] = []
    for field in fields(rates):
        value = getattr(rates, field.name)
        if isinstance(value, Source):
            found.append((field.name, value))
        elif isinstance(value, Rule):
            found.append((field.name, value.source))
        elif isinstance(value, tuple):
            found += [(f"{field.name}[{i}]", band.source) for i, band in enumerate(value)]
    return found


def test_tax_year_2025_26_is_registered() -> None:
    """Fails if the profile's only supported year has no rates (feature 002, research R13)."""
    assert rates_for("2025-26").tax_year == "2025-26"


def test_an_unknown_year_has_no_rates() -> None:
    """Fails if a year without FBR rates is answered with another year's."""
    with pytest.raises(KeyError):
        rates_for("2024-25")


@pytest.mark.parametrize("tax_year", YEARS)
def test_every_rule_names_its_source(tax_year: str) -> None:
    """Fails if any rule lacks its FBR document, location or Finance Act (Principle II)."""
    found = sources_of(RATES[tax_year])

    assert len(found) >= 6
    for rule, source in found:
        assert source.document.strip(), rule
        assert source.location.strip(), rule
        assert source.finance_act.strip(), rule


@pytest.mark.parametrize("tax_year", YEARS)
def test_salary_bands_join_up_from_zero_with_an_open_top(tax_year: str) -> None:
    """Fails if a band is missing, overlaps another, or the table doesn't cover every income."""
    bands = RATES[tax_year].salary_bands

    assert bands[0].lower == 0
    for below, above in zip(bands, bands[1:], strict=False):
        assert below.upper == above.lower
    assert all(band.upper is not None for band in bands[:-1])
    assert bands[-1].upper is None


@pytest.mark.parametrize("tax_year", YEARS)
def test_each_fixed_amount_is_the_tax_at_the_top_of_the_band_below(tax_year: str) -> None:
    """Fails on a typo in a fixed amount, like the circular's 345,000 for 346,000 (R10, FR-009)."""
    bands = RATES[tax_year].salary_bands

    assert bands[0].fixed == 0
    for below, above in zip(bands, bands[1:], strict=False):
        assert below.upper is not None
        assert above.fixed == below.fixed + below.rate * (below.upper - below.lower)


def test_the_continuity_check_catches_the_circulars_typo() -> None:
    """Fails if the check above couldn't tell 345,000 from 346,000 (it must, or it's useless)."""
    bands = list(rates_for("2025-26").salary_bands)
    row5 = bands[4]
    bands[4] = Band(row5.lower, row5.upper, Decimal("345000"), row5.rate, row5.source)

    below, above = bands[3], bands[4]
    assert below.upper is not None
    assert above.fixed != below.fixed + below.rate * (below.upper - below.lower)


@pytest.mark.parametrize("tax_year", YEARS)
def test_all_amounts_are_exact_decimals(tax_year: str) -> None:
    """Fails if any rate or limit is a float (Principle I: exact decimal arithmetic)."""
    rates = RATES[tax_year]
    numbers = [value for band in rates.salary_bands for value in (band.fixed, band.rate)]
    numbers += [
        getattr(rates, f.name).value
        for f in fields(rates)
        if isinstance(getattr(rates, f.name), Rule)
    ]

    assert all(isinstance(number, Decimal) for number in numbers)
