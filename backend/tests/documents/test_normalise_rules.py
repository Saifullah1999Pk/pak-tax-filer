"""Normalising extracted text and the consistency rules (feature 003, task T006, research R2-R3).

Rules are spec User Story 1, scenario 5. All plain code on Decimal, never the model (Principle I).
"""

from decimal import Decimal

import pytest

from app.documents.extraction.normalise import parse_amount, parse_tax_year
from app.documents.extraction.rules import check_rules
from app.documents.models import DocType, FieldName

PROFILE_YEAR = "2025-26"


# --- Amounts ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        ("1800000", Decimal("1800000.00")),
        ("1,800,000", Decimal("1800000.00")),
        ("1,800,000.50", Decimal("1800000.50")),
        ("Rs. 1,800,000", Decimal("1800000.00")),
        ("Rs 1,800,000", Decimal("1800000.00")),
        ("PKR 1,800,000.00", Decimal("1800000.00")),
        ("1 800 000", Decimal("1800000.00")),
        ("18,00,000", Decimal("1800000.00")),  # lakh grouping
        ("1,800,000/-", Decimal("1800000.00")),  # common Pakistani suffix
        ("0", Decimal("0.00")),
        ("(5,000)", Decimal("-5000.00")),  # brackets mean negative; the rules then catch it
        ("-5,000", Decimal("-5000.00")),
    ],
)
def test_amounts_are_read_as_exact_decimals(printed: str, expected: Decimal) -> None:
    """Fails if a common way of printing an amount is misread."""
    assert parse_amount(printed) == expected


@pytest.mark.parametrize(
    "printed",
    ["", "abc", "1,800,000 approx", "12.345", "1e6", "NaN", "Infinity", "1" * 13],
)
def test_unreadable_amounts_are_refused(printed: str) -> None:
    """Fails if junk, more than 2 decimals, or a value too big for numeric(14,2) is accepted."""
    with pytest.raises(ValueError):
        parse_amount(printed)


# --- Tax year --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "printed",
    ["2025-26", "2025-2026", "2025/26", "2025–26", "Tax Year 2026", "TY 2026", "2026", " 2025-26 "],
)
def test_tax_year_is_normalised_to_the_2025_26_form(printed: str) -> None:
    """Fails if a usual way of writing tax year 2026 isn't turned into "2025-26"."""
    assert parse_tax_year(printed) == "2025-26"


@pytest.mark.parametrize("printed", ["June 2026", "FY26", "2025-27", "26"])
def test_unrecognised_tax_years_are_kept_as_printed(printed: str) -> None:
    """Fails if an unclear year is guessed instead of kept for the rule check to flag."""
    assert parse_tax_year(printed) == printed


# --- Rules -----------------------------------------------------------------------------------

Values = dict[FieldName, Decimal | str | None]

SALARY_OK: Values = {
    FieldName.TAX_YEAR: "2025-26",
    FieldName.GROSS_SALARY: Decimal("1800000.00"),
    FieldName.TAXABLE_SALARY: Decimal("1700000.00"),
    FieldName.TAX_DEDUCTED: Decimal("95000.00"),
}
BANK_OK: Values = {
    FieldName.TAX_YEAR: "2025-26",
    FieldName.PROFIT_AMOUNT: Decimal("120000.00"),
    FieldName.TAX_WITHHELD: Decimal("24000.00"),
}


def test_consistent_certificates_pass() -> None:
    """Fails if valid figures are flagged."""
    assert not check_rules(DocType.SALARY_CERTIFICATE, SALARY_OK, PROFILE_YEAR)
    assert not check_rules(DocType.BANK_PROFIT_CERTIFICATE, BANK_OK, PROFILE_YEAR)


def test_equal_amounts_pass() -> None:
    """Fails if taxable salary equal to gross (no exempt part) is treated as an error."""
    values: Values = {**SALARY_OK, FieldName.TAXABLE_SALARY: SALARY_OK[FieldName.GROSS_SALARY]}
    assert not check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)


def test_negative_amount_is_flagged() -> None:
    """Fails if a negative amount (e.g. printed in brackets) isn't flagged."""
    values: Values = {**SALARY_OK, FieldName.TAX_DEDUCTED: Decimal("-5000.00")}

    reasons = check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)

    assert set(reasons) == {FieldName.TAX_DEDUCTED}
    assert "negative" in reasons[FieldName.TAX_DEDUCTED]


def test_tax_deducted_above_gross_flags_both_fields() -> None:
    """Fails if tax deducted greater than gross salary doesn't flag both fields involved."""
    values: Values = {**SALARY_OK, FieldName.TAX_DEDUCTED: Decimal("2000000.00")}

    reasons = check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)

    assert set(reasons) == {FieldName.TAX_DEDUCTED, FieldName.GROSS_SALARY}
    assert "Tax deducted is more than gross salary" in reasons[FieldName.GROSS_SALARY]


def test_taxable_above_gross_flags_both_fields() -> None:
    """Fails if taxable salary greater than gross salary doesn't flag both fields involved."""
    values: Values = {**SALARY_OK, FieldName.TAXABLE_SALARY: Decimal("1900000.00")}

    reasons = check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)

    assert set(reasons) == {FieldName.TAXABLE_SALARY, FieldName.GROSS_SALARY}


def test_one_field_can_break_two_rules() -> None:
    """Fails if a second broken rule overwrites the first reason instead of adding to it."""
    values: Values = {
        **SALARY_OK,
        FieldName.TAXABLE_SALARY: Decimal("1900000.00"),
        FieldName.TAX_DEDUCTED: Decimal("2000000.00"),
    }

    reasons = check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)

    assert "Taxable salary" in reasons[FieldName.GROSS_SALARY]
    assert "Tax deducted" in reasons[FieldName.GROSS_SALARY]


def test_tax_withheld_above_profit_flags_both_fields() -> None:
    """Fails if bank tax withheld greater than the profit doesn't flag both fields."""
    values: Values = {**BANK_OK, FieldName.TAX_WITHHELD: Decimal("130000.00")}

    reasons = check_rules(DocType.BANK_PROFIT_CERTIFICATE, values, PROFILE_YEAR)

    assert set(reasons) == {FieldName.TAX_WITHHELD, FieldName.PROFIT_AMOUNT}


@pytest.mark.parametrize("year", ["June 2026", "2025-27"])
def test_tax_year_not_in_the_right_form_is_flagged(year: str) -> None:
    """Fails if a tax year that isn't two consecutive years like 2025-26 passes."""
    reasons = check_rules(
        DocType.BANK_PROFIT_CERTIFICATE, {**BANK_OK, FieldName.TAX_YEAR: year}, PROFILE_YEAR
    )

    assert set(reasons) == {FieldName.TAX_YEAR}
    assert "2025-26" in reasons[FieldName.TAX_YEAR]


def test_tax_year_other_than_the_profile_year_is_flagged() -> None:
    """Fails if a certificate for another year passes (it would be summed into the wrong year)."""
    reasons = check_rules(
        DocType.SALARY_CERTIFICATE, {**SALARY_OK, FieldName.TAX_YEAR: "2024-25"}, PROFILE_YEAR
    )

    assert set(reasons) == {FieldName.TAX_YEAR}
    assert "profile" in reasons[FieldName.TAX_YEAR]


def test_missing_fields_are_not_rule_failures() -> None:
    """Fails if "not found" fields crash the rules or are flagged (they're handled separately)."""
    values: Values = {name: None for name in SALARY_OK}

    assert not check_rules(DocType.SALARY_CERTIFICATE, values, PROFILE_YEAR)
