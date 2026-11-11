"""Tax year 2026 (1 July 2025 to 30 June 2026, "2025-26") rates (feature 004, task T007).

Every value is from the Income Tax Ordinance, 2001 as amended up to 31.07.2025, FBR's own text:
https://download1.fbr.gov.pk/Docs/2025881983148210Income-Tax-Ordinance,-2001-Amended-upto-31.07.2025.pdf
Locations give the PDF page, checked by Saifullah Khan on 2026-11-09 (worked examples sign-off).
Note: FBR Circular 01 of 2025-26 prints two wrong fixed amounts (345,000 and 615,000); the
Ordinance's 346,000 and 616,000 are the only values consistent with the bands, and the statute
prevails. Never use the superseded tables printed in the Ordinance's footnotes.
"""

from decimal import Decimal

from app.tax.rates.model import Band, Rule, Source, TaxYearRates

ORDINANCE = "Income Tax Ordinance, 2001 (amended up to 31.07.2025)"
TABLE = "First Schedule, Part I, Division I, clause (2)"


def _row(number: int) -> Source:
    return Source(
        document=ORDINANCE,
        location=f"{TABLE}, row {number} (PDF page 493, printed page 492)",
        finance_act="Finance Act 2025 (table substituted)",
    )


RATES = TaxYearRates(
    tax_year="2025-26",
    salary_bands=(
        Band(Decimal("0"), Decimal("600000"), Decimal("0"), Decimal("0"), _row(1)),
        Band(Decimal("600000"), Decimal("1200000"), Decimal("0"), Decimal("0.01"), _row(2)),
        Band(Decimal("1200000"), Decimal("2200000"), Decimal("6000"), Decimal("0.11"), _row(3)),
        Band(Decimal("2200000"), Decimal("3200000"), Decimal("116000"), Decimal("0.23"), _row(4)),
        Band(Decimal("3200000"), Decimal("4100000"), Decimal("346000"), Decimal("0.30"), _row(5)),
        Band(Decimal("4100000"), None, Decimal("616000"), Decimal("0.35"), _row(6)),
    ),
    salary_share_threshold=Rule(
        Decimal("0.75"),
        Source(
            ORDINANCE,
            f"{TABLE}: the salaried table applies where salary exceeds 75% of taxable income "
            "(PDF page 493)",
            "Finance Act 2025",
        ),
    ),
    surcharge_rate=Rule(
        Decimal("0.09"),
        Source(
            ORDINANCE,
            "Section 4AB, proviso: nine percent of the Division I tax for an individual with "
            "income under the head Salary (PDF page 34)",
            "Finance Act 2025 (proviso added; section 4AB inserted by Finance Act 2024)",
        ),
    ),
    surcharge_threshold=Rule(
        Decimal("10000000"),
        Source(
            ORDINANCE,
            "Section 4AB: where the taxable income exceeds rupees ten million (PDF page 34)",
            "Finance Act 2024 (section 4AB inserted)",
        ),
    ),
    profit_rate=Rule(
        Decimal("0.20"),
        Source(
            ORDINANCE,
            "Section 7B(1)-(2) on the gross profit on debt (PDF pages 40-41), at First Schedule, "
            "Part I, Division IIIA(a): 20% of profit paid by a banking company (PDF page 501)",
            "Finance Act 2025 (Division IIIA substituted)",
        ),
    ),
    profit_limit=Rule(
        Decimal("5000000"),
        Source(
            ORDINANCE,
            "Section 7B(3)(b): section 7B does not apply to profit on debt exceeding five million "
            "rupees (PDF page 41)",
            'Finance Act 2019 (sub-section (3)); "five" substituted by Finance Act 2021',
        ),
    ),
    rounding=Source(
        ORDINANCE,
        "Section 219: tax or refund to the nearest rupee; fractions of fifty paisa or more count "
        "as one rupee (PDF page 437)",
        "Income Tax Ordinance, 2001 (original)",
    ),
)
