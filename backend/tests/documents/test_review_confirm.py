"""Review, correct and confirm (feature 003, task T017; constitution Principle III).

Figures reach other features only through confirmed_documents(), and only once confirmed.
"""

from decimal import Decimal
from typing import Any

import pytest
from conftest import make_user
from document_helpers import BANK_RESULT, SALARY_RESULT, make_pdf, upload, value
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.extraction.client import ExtractionResult, FakeExtractor
from app.documents.models import DocType, ExtractedField, FieldName
from app.documents.service import confirmed_documents

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("user_with_profile", "fake_extractor")]

YEAR = "2025-26"


async def new_document(client: AsyncClient, doc_type: str = "salary_certificate") -> str:
    """Upload a synthetic certificate and return its id."""
    response = await upload(client, make_pdf(), doc_type=doc_type)
    assert response.status_code == 201
    return str(response.json()["id"])


async def patch(client: AsyncClient, document_id: str, name: str, body: dict[str, Any]) -> Any:
    """PATCH one field."""
    return await client.patch(f"/api/documents/{document_id}/fields/{name}", json=body)


async def fields_of(client: AsyncClient, document_id: str) -> dict[str, dict[str, Any]]:
    """The document's fields by name, as the API shows them now."""
    document = (await client.get(f"/api/documents/{document_id}")).json()
    return {field["name"]: field for field in document["fields"]}


async def confirm_all_fields(client: AsyncClient, document_id: str) -> None:
    """Confirm every field of the document."""
    for name in await fields_of(client, document_id):
        response = await patch(client, document_id, name, {"confirmed": True})
        assert response.status_code == 200, response.text


async def test_editing_a_value_marks_it_user_entered_and_reruns_the_rules(
    client: AsyncClient,
) -> None:
    """Fails if an edit isn't normalised, marked user-entered, or checked by the rules."""
    document_id = await new_document(client)

    response = await patch(client, document_id, "tax_deducted", {"value": "Rs. 2,000,000"})

    assert response.status_code == 200
    assert response.json()["value"] == "2000000.00"
    assert response.json()["user_edited"] is True
    fields = await fields_of(client, document_id)
    assert "Tax deducted is more than gross salary" in fields["gross_salary"]["rule_reason"]


async def test_fixing_a_value_clears_the_rule_reason(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a broken rule's reason stays after the user corrects the figure."""
    bad = dict(SALARY_RESULT.fields)
    bad["tax_deducted"] = value("2,000,000")
    fake_extractor.result = ExtractionResult(fields=bad, model="gemini-3.8-flash")
    document_id = await new_document(client)

    await patch(client, document_id, "tax_deducted", {"value": "95,000"})

    fields = await fields_of(client, document_id)
    assert fields["tax_deducted"]["rule_reason"] is None
    assert fields["gross_salary"]["rule_reason"] is None


@pytest.mark.parametrize("bad_value", ["abc", "-5,000", "12.345", ""])
async def test_invalid_amount_is_refused(client: AsyncClient, bad_value: str) -> None:
    """Fails if a user can save something that isn't a valid non-negative amount."""
    document_id = await new_document(client)

    response = await patch(client, document_id, "gross_salary", {"value": bad_value})

    assert response.status_code == 422


async def test_invalid_tax_year_is_refused(client: AsyncClient) -> None:
    """Fails if a user can save a tax year that isn't in the 2025-26 form."""
    document_id = await new_document(client)

    response = await patch(client, document_id, "tax_year", {"value": "next year"})

    assert response.status_code == 422


async def test_field_the_type_does_not_have_is_404(client: AsyncClient) -> None:
    """Fails if a salary certificate accepts a bank-only field."""
    document_id = await new_document(client)

    response = await patch(client, document_id, "profit_amount", {"value": "1"})

    assert response.status_code == 404


async def test_editing_a_confirmed_field_needs_confirming_again(client: AsyncClient) -> None:
    """Fails if a changed figure keeps an earlier confirmation."""
    document_id = await new_document(client)
    await patch(client, document_id, "gross_salary", {"confirmed": True})

    response = await patch(client, document_id, "gross_salary", {"value": "1,900,000"})

    assert response.json()["confirmed"] is False


async def test_not_found_field_cannot_be_confirmed_until_filled_in(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a "not found" field can be confirmed without a value."""
    missing = dict(SALARY_RESULT.fields)
    missing["tax_deducted"] = value(None)
    fake_extractor.result = ExtractionResult(fields=missing, model="gemini-3.8-flash")
    document_id = await new_document(client)

    refused = await patch(client, document_id, "tax_deducted", {"confirmed": True})
    filled = await patch(client, document_id, "tax_deducted", {"value": "0", "confirmed": True})

    assert refused.status_code == 422
    assert filled.status_code == 200
    assert filled.json()["value"] == "0.00"
    assert filled.json()["confirmed"] is True


async def test_document_confirm_lists_what_is_missing(client: AsyncClient) -> None:
    """Fails if a document with unconfirmed fields can be confirmed (409 naming them)."""
    document_id = await new_document(client)
    await patch(client, document_id, "tax_year", {"confirmed": True})

    response = await client.post(f"/api/documents/{document_id}/confirm", json={})

    assert response.status_code == 409
    for name in ("gross_salary", "taxable_salary", "tax_deducted"):
        assert name in response.json()["detail"]
    assert "tax_year" not in response.json()["detail"]


async def test_confirmed_document_is_read_only(client: AsyncClient) -> None:
    """Fails if a confirmed document can still be edited or confirmed again."""
    document_id = await new_document(client)
    await confirm_all_fields(client, document_id)

    confirmed = await client.post(f"/api/documents/{document_id}/confirm", json={})
    edit = await patch(client, document_id, "gross_salary", {"value": "1"})
    again = await client.post(f"/api/documents/{document_id}/confirm", json={})

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"] is not None
    assert edit.status_code == 409
    assert again.status_code == 409


async def test_only_confirmed_documents_reach_other_features(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if unconfirmed figures leak, or several confirmed of one type aren't all returned."""
    first = await new_document(client)
    second = await new_document(client)
    await new_document(client)  # Never confirmed.
    fake_extractor.result = BANK_RESULT
    bank = await new_document(client, "bank_profit_certificate")
    for document_id in (first, second, bank):
        await confirm_all_fields(client, document_id)
        assert (
            await client.post(f"/api/documents/{document_id}/confirm", json={})
        ).status_code == 200

    found = await confirmed_documents(db, user_with_profile.id, YEAR)

    assert sorted(str(d.id) for d in found) == sorted([first, second, bank])
    salary = next(d for d in found if d.doc_type is DocType.SALARY_CERTIFICATE)
    assert salary.values[FieldName.GROSS_SALARY] == Decimal("1800000.00")
    assert await confirmed_documents(db, user_with_profile.id, "2024-25") == []


# Code review findings (2026-11-05).


async def test_negative_extracted_amount_cannot_be_confirmed(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a negative amount read by the AI can be confirmed (typed ones already can't)."""
    fields = dict(SALARY_RESULT.fields)
    fields["tax_deducted"] = value("(5,000)")
    fake_extractor.result = ExtractionResult(fields=fields, model="gemini-3.8-flash")
    document_id = await new_document(client)

    response = await patch(client, document_id, "tax_deducted", {"confirmed": True})

    assert response.status_code == 422
    assert "negative" in response.json()["detail"]


async def test_wrong_tax_year_document_cannot_be_confirmed(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a certificate for another year can be confirmed into the profile's year."""
    fields = dict(SALARY_RESULT.fields)
    fields["tax_year"] = value("Tax Year 2025")
    fake_extractor.result = ExtractionResult(fields=fields, model="gemini-3.8-flash")
    document_id = await new_document(client)
    await confirm_all_fields(client, document_id)

    response = await client.post(f"/api/documents/{document_id}/confirm", json={})

    assert response.status_code == 409
    assert "2024-25" in response.json()["detail"]
    assert "2025-26" in response.json()["detail"]


async def test_unknown_field_name_is_404(client: AsyncClient) -> None:
    """Fails if a field name that no document has gives anything but 404 (contract)."""
    document_id = await new_document(client)

    response = await patch(client, document_id, "employee_name", {"value": "1"})

    assert response.status_code == 404


async def test_document_with_an_unconfirmed_field_never_reaches_other_features(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if confirmed_documents trusts the status alone (defence against a lost race)."""
    document_id = await new_document(client)
    await confirm_all_fields(client, document_id)
    assert (await client.post(f"/api/documents/{document_id}/confirm", json={})).status_code == 200
    field = (
        await db.scalars(
            select(ExtractedField).where(ExtractedField.name == FieldName.GROSS_SALARY)
        )
    ).one()
    field.confirmed = False
    await db.flush()

    assert await confirmed_documents(db, user_with_profile.id, YEAR) == []


async def test_other_users_confirmed_documents_are_not_returned(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if one user's confirmed figures could reach another user's calculation."""
    document_id = await new_document(client)
    await confirm_all_fields(client, document_id)
    await client.post(f"/api/documents/{document_id}/confirm", json={})
    other = await make_user(db, "other@example.com")

    assert await confirmed_documents(db, other.id, YEAR) == []
    assert len(await confirmed_documents(db, user_with_profile.id, YEAR)) == 1
