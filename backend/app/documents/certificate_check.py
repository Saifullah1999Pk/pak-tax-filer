"""Checking a certificate's figures given as text (feature 007, task T005).

Used by 006's validate_salary_information MCP tool and 007's validation agent's tools, so the
amount parsing and 003's rules (rules.check_rules) live in one place. Never calculates tax.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from app.documents.extraction.rules import check_rules
from app.documents.models import DocType, FieldName

NOT_AN_AMOUNT = "Not an amount."


def check_figures(
    doc_type: DocType,
    tax_year: str,
    amounts: Mapping[FieldName, str],
    profile_tax_year: str,
) -> list[tuple[str, str]]:
    """Each (field, reason) the figures break: text that isn't an amount, then 003's rules
    (no negatives, parts not above their whole, the tax year matching the profile's)."""
    parsed = {name: _decimal(text) for name, text in amounts.items()}
    issues = [(name.value, NOT_AN_AMOUNT) for name, value in parsed.items() if value is None]
    values: dict[FieldName, Decimal | str | None] = {**parsed, FieldName.TAX_YEAR: tax_year.strip()}
    issues += [
        (name.value, reason)
        for name, reason in check_rules(doc_type, values, profile_tax_year).items()
    ]
    return issues


def _decimal(text: str) -> Decimal | None:
    """The amount, or None if it isn't a plain decimal number."""
    try:
        value = Decimal(text.strip().replace(",", ""))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None
