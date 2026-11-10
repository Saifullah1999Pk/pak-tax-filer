"""GET and PUT /api/wealth/{tax_year} (feature 005, tasks T010, T020; contracts/wealth-api.md).

Entries are stored; the reconciliation is recalculated on every request from the statement and
the user's confirmed certificates only (FR-004, FR-012, Principle III).
"""

from typing import Any

import pytest
from document_helpers import add_confirmed_document
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password
from app.documents.models import DocType

pytestmark = pytest.mark.anyio

URL = "/api/wealth/2025-26"
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."

# The signed-off "reconciled" example (tests/wealth/worked_examples.yaml).
STATEMENT: dict[str, Any] = {
    "previous_net_assets": "2100000",
    "assets": [
        {"category": "bank_account", "description": "Savings account", "amount": "1350000"},
        {"category": "motor_vehicle", "description": "Car", "amount": "1400000"},
    ],
    "liabilities": [{"description": "Car loan", "creditor": "Bank", "amount": "200000"}],
    "other_exempt_income": "0",
    "foreign_remittance": "0",
    "inheritance": "0",
    "gifts_received": "0",
    "family_contribution": "0",
    "gifts_given": "0",
    "expenses": {"rent": "600000", "electricity": "150000", "other_household": "768000"},
}
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "72000"}
BANK = {"profit_amount": "50000", "tax_withheld": "10000"}


async def certificates(db: AsyncSession, user: User) -> None:
    """The example's salary and bank certificates, confirmed."""
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    await add_confirmed_document(db, user.id, DocType.BANK_PROFIT_CERTIFICATE, BANK)


async def test_logged_out_is_refused(client: AsyncClient) -> None:
    """Fails if anyone can read or write a wealth statement without logging in."""
    assert (await client.get(URL)).status_code == 401
    assert (await client.put(URL, json=STATEMENT)).status_code == 401


@pytest.mark.usefixtures("logged_in_user")
async def test_a_year_without_rates_is_404(client: AsyncClient) -> None:
    """Fails if a tax year the app doesn't support is answered."""
    assert (await client.get("/api/wealth/2024-25")).status_code == 404
    assert (await client.put("/api/wealth/2024-25", json=STATEMENT)).status_code == 404


@pytest.mark.usefixtures("logged_in_user")
async def test_a_statement_never_saved_is_empty_and_not_ready(client: AsyncClient) -> None:
    """Fails if a new user gets an error, figures, or no label."""
    body = (await client.get(URL)).json()

    assert body["statement"]["assets"] == [] and body["statement"]["saved_at"] is None
    assert body["result"]["not_ready_reason"] == "needs_previous_net_assets"
    assert body["result"]["message"]
    assert body["result"]["net_assets"] is None and body["result"]["steps"] == []
    assert body["certificates_changed"] is False
    assert body["label"] == LABEL


async def test_save_then_read_reconciles_the_signed_off_example(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a field doesn't round-trip, or the result differs from the hand working."""
    await certificates(db, logged_in_user)

    saved = await client.put(URL, json=STATEMENT)
    body = (await client.get(URL)).json()

    assert saved.status_code == 200
    assert saved.json()["result"] == body["result"]
    statement = body["statement"]
    for key, value in STATEMENT.items():
        if key == "liabilities":
            assert statement[key] == value
        else:
            assert statement[key] == value, key
    assert statement["saved_at"] is not None
    result = body["result"]
    assert result["not_ready_reason"] is None
    assert (result["net_assets"], result["increase"]) == ("2550000", "450000")
    assert (result["inflows"], result["outflows"]) == ("2050000", "1600000")
    assert (result["unreconciled"], result["direction"]) == ("0", "reconciled")
    assert [step["form_line"] for step in result["steps"]][-1] == "703000"
    assert result["where_to_look"] == []
    assert body["label"] == LABEL


async def test_auto_filled_lines_come_from_confirmed_certificates_and_name_them(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a certificate line is wrong, editable through the API, or doesn't say which
    certificate it came from (FR-004)."""
    await certificates(db, logged_in_user)

    lines = {line["label"]: line for line in (await client.get(URL)).json()["auto_filled"]}

    taxable = lines["Taxable salary"]
    assert (taxable["line"], taxable["amount"]) == ("7031", "1800000")
    assert taxable["certificates"] and taxable["certificates"][0].startswith("Salary certificate")
    exempt = lines["Exempt part of salary (gross - taxable)"]
    assert (exempt["line"], exempt["amount"], exempt["provisional"]) == ("7032", "200000", True)
    profit = lines["Bank profit"]
    assert (profit["line"], profit["amount"]) == ("7033", "50000")
    assert profit["certificates"][0].startswith("Bank profit certificate")
    tax = lines["Tax deducted and withheld at source (outflow)"]
    assert (tax["line"], tax["amount"]) == (None, "82000")
    assert len(tax["certificates"]) == 2


@pytest.mark.usefixtures("logged_in_user")
async def test_an_unconfirmed_or_another_users_certificate_is_never_counted(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if another user's figures reach this statement (FR-016, Principle III)."""
    other = User(email="other@example.com", password_hash=hash_password("other-pass"))
    db.add(other)
    await db.commit()
    await add_confirmed_document(db, other.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.put(URL, json=STATEMENT)

    body = (await client.get(URL)).json()

    assert body["result"]["not_ready_reason"] == "no_confirmed_salary_certificate"
    assert all(line["certificates"] == [] for line in body["auto_filled"])


@pytest.mark.parametrize(
    "change",
    [
        {"inheritance": "-1"},
        {"gifts_given": "100.50"},
        {"assets": [{"category": "yacht", "description": "Boat", "amount": "1"}]},
        {"assets": [{"category": "bank_account", "description": "", "amount": "1"}]},
    ],
)
@pytest.mark.usefixtures("logged_in_user")
async def test_invalid_entries_are_422_and_nothing_is_saved(
    client: AsyncClient, change: dict[str, Any]
) -> None:
    """Fails if an invalid statement is saved, or the error repeats what was sent."""
    response = await client.put(URL, json={**STATEMENT, **change})

    assert response.status_code == 422
    assert "Boat" not in response.text and "100.50" not in response.text
    assert (await client.get(URL)).json()["statement"]["saved_at"] is None


@pytest.mark.usefixtures("logged_in_user")
async def test_saving_again_replaces_the_whole_statement(client: AsyncClient) -> None:
    """Fails if rows from an earlier save survive a replace (research R8)."""
    await client.put(URL, json=STATEMENT)
    await client.put(URL, json={**STATEMENT, "assets": [], "expenses": {"rent": "1"}})

    statement = (await client.get(URL)).json()["statement"]

    assert statement["assets"] == [] and statement["expenses"] == {"rent": "1"}


@pytest.mark.usefixtures("logged_in_user")
async def test_non_json_save_is_refused(client: AsyncClient) -> None:
    """Fails if a save accepts a form post (002 research R3: JSON only)."""
    assert (await client.put(URL, data={"previous_net_assets": "1"})).status_code == 415


# Task T020: the certificate-change notice (research R7, FR-013).


async def test_the_notice_appears_when_certificates_change_and_clears_on_save(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a certificate added or deleted since the last save goes unnoticed, or the notice
    stays after the user saves again."""
    await certificates(db, logged_in_user)
    await client.put(URL, json=STATEMENT)
    assert (await client.get(URL)).json()["certificates_changed"] is False

    added = await add_confirmed_document(
        db, logged_in_user.id, DocType.BANK_PROFIT_CERTIFICATE, BANK
    )
    assert (await client.get(URL)).json()["certificates_changed"] is True

    await client.put(URL, json=STATEMENT)
    assert (await client.get(URL)).json()["certificates_changed"] is False

    deleted = await client.request("DELETE", f"/api/documents/{added.id}", json={})
    assert deleted.status_code == 204
    assert (await client.get(URL)).json()["certificates_changed"] is True
