"""Consistency rules on extracted figures (feature 003, research R3; spec US1 scenario 5).

Run after normalising and after every user edit. Each broken rule names every field involved,
which is then shown as low confidence with the reason (FR-005). Plain code, never the model.
"""

import re
from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal

from app.documents.models import DocType, FieldName

# (part, whole, reason): the part may not exceed the whole.
_NOT_MORE_THAN: dict[DocType, tuple[tuple[FieldName, FieldName, str], ...]] = {
    DocType.SALARY_CERTIFICATE: (
        (
            FieldName.TAXABLE_SALARY,
            FieldName.GROSS_SALARY,
            "Taxable salary is more than gross salary.",
        ),
        (FieldName.TAX_DEDUCTED, FieldName.GROSS_SALARY, "Tax deducted is more than gross salary."),
    ),
    DocType.BANK_PROFIT_CERTIFICATE: (
        (
            FieldName.TAX_WITHHELD,
            FieldName.PROFIT_AMOUNT,
            "Tax withheld is more than the profit amount.",
        ),
    ),
}
_TAX_YEAR = re.compile(r"(\d{4})-(\d{2})")


def is_tax_year(text: str) -> bool:
    """True for two consecutive years in the "2025-26" form."""
    match = _TAX_YEAR.fullmatch(text)
    return match is not None and int(match[2]) == (int(match[1]) + 1) % 100


def check_rules(
    doc_type: DocType,
    values: Mapping[FieldName, Decimal | str | None],
    profile_tax_year: str,
) -> dict[FieldName, str]:
    """The reason each field breaks a rule, for the fields that break any; empty if none do.

    Missing values (None, "not found") are skipped: confirming needs them filled in anyway.
    """
    reasons: defaultdict[FieldName, list[str]] = defaultdict(list)

    for name, value in values.items():
        if isinstance(value, Decimal) and value < 0:
            reasons[name].append("A negative amount isn't valid here.")

    for part, whole, reason in _NOT_MORE_THAN[doc_type]:
        part_value, whole_value = values.get(part), values.get(whole)
        if (
            isinstance(part_value, Decimal)
            and isinstance(whole_value, Decimal)
            and part_value > whole_value
        ):
            reasons[part].append(reason)
            reasons[whole].append(reason)

    year = values.get(FieldName.TAX_YEAR)
    if isinstance(year, str):
        if not is_tax_year(year):
            reasons[FieldName.TAX_YEAR].append("Not a tax year in the form 2025-26.")
        elif year != profile_tax_year:
            reasons[FieldName.TAX_YEAR].append(
                f"Doesn't match the tax year in your profile ({profile_tax_year})."
            )

    return {name: " ".join(texts) for name, texts in reasons.items()}
