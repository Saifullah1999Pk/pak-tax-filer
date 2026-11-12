"""The wealth statement's request shape (feature 005, task T006; contracts/wealth-api.md, FR-003).

Money is decimal strings of whole rupees; nothing may be negative except last year's net assets.
"""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.wealth.models import ExpenseCategory
from app.wealth.schemas import StatementIn


def statement(**changes: Any) -> dict[str, Any]:
    """A valid statement body, with any fields replaced."""
    body: dict[str, Any] = {
        "previous_net_assets": "2100000",
        "assets": [
            {"category": "bank_account", "description": "Savings account", "amount": "1350000"}
        ],
        "liabilities": [{"description": "Car loan", "creditor": "Bank", "amount": "200000"}],
        "other_exempt_income": "0",
        "foreign_remittance": "0",
        "inheritance": "0",
        "gifts_received": "0",
        "family_contribution": "0",
        "gifts_given": "0",
        "expenses": {"rent": "600000", "other_household": "768000"},
    }
    body.update(changes)
    return body


def test_a_valid_statement_is_read_as_exact_rupees() -> None:
    """Fails if amounts aren't Decimals or the rows and expenses don't come through."""
    parsed = StatementIn.model_validate(statement())

    assert parsed.previous_net_assets == Decimal(2100000)
    assert parsed.assets[0].amount == Decimal(1350000)
    assert parsed.expenses[ExpenseCategory.RENT] == Decimal(600000)


def test_last_years_net_assets_may_be_negative_or_missing() -> None:
    """Fails if negative previous net assets (owing more than owning) or none is refused."""
    assert StatementIn.model_validate(statement(previous_net_assets="-700000"))
    assert (
        StatementIn.model_validate(statement(previous_net_assets=None)).previous_net_assets is None
    )


@pytest.mark.parametrize(
    "change",
    [
        {"inheritance": "-1"},  # negative
        {"assets": [{"category": "bank_account", "description": "A", "amount": "-5"}]},
        {"liabilities": [{"description": "Loan", "creditor": "", "amount": "-5"}]},
        {"expenses": {"rent": "-1"}},
        {"gifts_given": "100.50"},  # not whole rupees
        {"previous_net_assets": "1e6"},  # not plain digits
        {"foreign_remittance": 300000},  # a number, not a decimal string
        {"gifts_received": "123456789012345"},  # more than 14 digits
        {"assets": [{"category": "yacht", "description": "Boat", "amount": "1"}]},  # unknown
        {"expenses": {"holidays": "1"}},  # unknown expense category
        {"assets": [{"category": "bank_account", "description": "", "amount": "1"}]},
        {"assets": [{"category": "bank_account", "description": "x" * 201, "amount": "1"}]},
        {"liabilities": [{"description": "Loan", "creditor": "c" * 201, "amount": "1"}]},
    ],
)
def test_invalid_entries_are_refused(change: dict[str, Any]) -> None:
    """Fails if a negative, fractional, non-string, over-long or unknown value is accepted."""
    with pytest.raises(ValidationError):
        StatementIn.model_validate(statement(**change))


def test_a_missing_expense_category_means_zero() -> None:
    """Fails if leaving an expense category out isn't allowed (data model: missing = zero)."""
    parsed = StatementIn.model_validate(statement(expenses={}))

    assert parsed.expenses == {}


def test_only_ascii_digits_are_money() -> None:
    """Fails if digits from other scripts (e.g. Arabic-Indic) are read as rupees."""
    with pytest.raises(ValidationError):
        StatementIn.model_validate(statement(inheritance="١٢٣"))


def test_minus_zero_becomes_zero() -> None:
    """Fails if "-0" is kept as a negative-looking zero."""
    parsed = StatementIn.model_validate(statement(inheritance="-0", previous_net_assets="-0"))

    assert str(parsed.inheritance) == "0" and str(parsed.previous_net_assets) == "0"
