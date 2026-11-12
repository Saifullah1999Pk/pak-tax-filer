"""Checking a certificate's figures typed as text (feature 007, task T005; 006's MCP tool).

One function for 006's validate_salary_information tool and 007's validation agent's tools, so
the "Not an amount." parsing and 003's rules live in one place.
"""

from app.documents.certificate_check import check_figures
from app.documents.models import DocType, FieldName

SALARY = {
    FieldName.GROSS_SALARY: "1,200,000",
    FieldName.TAXABLE_SALARY: "1000000",
    FieldName.TAX_DEDUCTED: "30000",
}


def test_consistent_salary_figures_have_no_issues() -> None:
    """Fails if figures that break no rule (commas allowed) are reported."""
    assert check_figures(DocType.SALARY_CERTIFICATE, "2025-26", SALARY, "2025-26") == []


def test_taxable_above_gross_names_both_fields() -> None:
    """Fails if 003's taxable-above-gross rule is lost."""
    figures = {**SALARY, FieldName.TAXABLE_SALARY: "1500000"}

    issues = check_figures(DocType.SALARY_CERTIFICATE, "2025-26", figures, "2025-26")

    assert {field for field, _ in issues} == {"gross_salary", "taxable_salary"}


def test_text_that_is_not_an_amount_is_reported() -> None:
    """Fails if "twelve lakh" or "NaN" reaches the rules as if it were a number."""
    for bad in ("twelve lakh", "NaN", ""):
        figures = {**SALARY, FieldName.GROSS_SALARY: bad}
        issues = check_figures(DocType.SALARY_CERTIFICATE, "2025-26", figures, "2025-26")
        assert ("gross_salary", "Not an amount.") in issues


def test_bank_figures_use_the_bank_rules_and_the_profile_year() -> None:
    """Fails if a bank certificate's withholding above its profit, or another year, passes."""
    figures = {FieldName.PROFIT_AMOUNT: "100000", FieldName.TAX_WITHHELD: "150000"}

    issues = check_figures(DocType.BANK_PROFIT_CERTIFICATE, "2023-24", figures, "2025-26")

    assert {field for field, _ in issues} == {"tax_withheld", "profit_amount", "tax_year"}
