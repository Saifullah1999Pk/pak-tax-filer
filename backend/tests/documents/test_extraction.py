"""From extractor result to stored, rule-checked fields (feature 003, task T011).

Uses FakeExtractor (research R8); the contract is specs/003-document-extraction/contracts/
documents-api.md.
"""

from typing import Any

import pytest
from document_helpers import BANK_RESULT, SALARY_RESULT, make_image, make_pdf, upload, value
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.extraction.client import ExtractionResult, FakeExtractor
from app.documents.models import Document, ExtractedField

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("user_with_profile", "fake_extractor")]


def by_name(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The document's fields, keyed by name."""
    return {field["name"]: field for field in document["fields"]}


async def test_salary_certificate_gives_four_normalised_fields(client: AsyncClient) -> None:
    """Fails if a salary result isn't stored as 4 fields shaped like the contract."""
    response = await upload(client, make_pdf())

    assert response.status_code == 201
    document = response.json()
    assert document["doc_type"] == "salary_certificate"
    assert document["status"] == "needs_review"
    assert [field["name"] for field in document["fields"]] == [
        "tax_year",
        "gross_salary",
        "taxable_salary",
        "tax_deducted",
    ]
    assert by_name(document)["gross_salary"] == {
        "name": "gross_salary",
        "value": "1800000.00",
        "confidence": "high",
        "source_page": 1,
        "source_label": "Gross Salary",
        "rule_reason": None,
        "user_edited": False,
        "confirmed": False,
    }
    assert by_name(document)["tax_deducted"]["value"] == "95000.00"
    assert by_name(document)["taxable_salary"]["confidence"] == "medium"
    assert by_name(document)["tax_year"]["value"] == "2025-26"


async def test_bank_certificate_gives_three_fields(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a bank result isn't stored as its 3 fields."""
    fake_extractor.result = BANK_RESULT

    response = await upload(client, make_image("PNG"), "photo.png", "bank_profit_certificate")

    fields = by_name(response.json())
    assert list(fields) == ["tax_year", "profit_amount", "tax_withheld"]
    assert fields["profit_amount"]["value"] == "120000.00"
    assert fake_extractor.calls == [("bank_profit_certificate", "image/png")]


async def test_rule_breaking_fields_are_lowered_with_the_reason(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if tax deducted above gross salary isn't shown as low with why (FR-005)."""
    fields = dict(SALARY_RESULT.fields)
    fields["tax_deducted"] = value("2,000,000")
    fake_extractor.result = ExtractionResult(fields=fields, model="claude-opus-5-5")

    document = (await upload(client, make_pdf())).json()

    for name in ("tax_deducted", "gross_salary"):
        assert by_name(document)[name]["confidence"] == "low"
        assert "Tax deducted is more than gross salary" in by_name(document)[name]["rule_reason"]
    assert by_name(document)["taxable_salary"]["rule_reason"] is None


async def test_unreadable_amount_is_low_and_empty(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if an amount that isn't a number is stored as a number or passes quietly."""
    fields = dict(SALARY_RESULT.fields)
    fields["gross_salary"] = value("about 18 lakh")
    fake_extractor.result = ExtractionResult(fields=fields, model="claude-opus-5-5")

    gross = by_name((await upload(client, make_pdf())).json())["gross_salary"]

    assert gross["value"] is None
    assert gross["confidence"] == "low"
    assert gross["rule_reason"]


async def test_wrong_tax_year_is_flagged(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a certificate for a year other than the profile's passes unflagged."""
    fields = dict(SALARY_RESULT.fields)
    fields["tax_year"] = value("Tax Year 2025")
    fake_extractor.result = ExtractionResult(fields=fields, model="claude-opus-5-5")

    year = by_name((await upload(client, make_pdf())).json())["tax_year"]

    assert year["value"] == "2024-25"
    assert year["confidence"] == "low"
    assert "profile" in year["rule_reason"]


async def test_failed_extraction_saves_no_fields(
    client: AsyncClient, fake_extractor: FakeExtractor, db: AsyncSession
) -> None:
    """Fails if a refusal or API error leaves fields behind or hides the reason."""
    fake_extractor.result = ExtractionResult(failure_reason="The AI service is busy.")

    response = await upload(client, make_pdf())

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["failure_reason"] == "The AI service is busy."
    assert response.json()["fields"] == []
    assert (await db.scalars(select(ExtractedField))).first() is None


async def test_only_the_listed_fields_are_stored(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if an extra key (e.g. a name) from the extractor is kept (FR-003)."""
    fields = {**SALARY_RESULT.fields, "employee_name": value("Synthetic Person")}
    fake_extractor.result = ExtractionResult(fields=fields, model="claude-opus-5-5")

    document = (await upload(client, make_pdf())).json()

    assert "employee_name" not in by_name(document)
    assert "Synthetic Person" not in str(document)


async def test_field_missing_from_the_result_is_not_found(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a field the extractor left out disappears instead of showing "not found"."""
    fields = {k: v for k, v in SALARY_RESULT.fields.items() if k != "tax_deducted"}
    fake_extractor.result = ExtractionResult(fields=fields, model="claude-opus-5-5")

    deducted = by_name((await upload(client, make_pdf())).json())["tax_deducted"]

    assert deducted["value"] is None
    assert deducted["source_page"] is None


async def test_model_is_recorded(
    client: AsyncClient, fake_extractor: FakeExtractor, db: AsyncSession
) -> None:
    """Fails if the model that answered isn't recorded on the document."""
    fake_extractor.result = ExtractionResult(fields=SALARY_RESULT.fields, model="claude-opus-4-8")

    response = await upload(client, make_pdf())

    document = await db.get(Document, response.json()["id"])
    assert document is not None
    assert document.model == "claude-opus-4-8"


async def test_document_and_file_can_be_read_back(client: AsyncClient) -> None:
    """Fails if GET /api/documents/{id} or its /file doesn't return what was uploaded."""
    pdf = make_pdf()
    created = (await upload(client, pdf)).json()

    fetched = await client.get(f"/api/documents/{created['id']}")
    file = await client.get(f"/api/documents/{created['id']}/file")

    assert fetched.status_code == 200
    assert fetched.json() == created
    assert file.status_code == 200
    assert file.headers["content-type"] == "application/pdf"
    assert file.content == pdf


async def test_unknown_document_is_404(client: AsyncClient) -> None:
    """Fails if a document id that doesn't exist gives anything but 404."""
    missing = "00000000-0000-0000-0000-000000000000"

    assert (await client.get(f"/api/documents/{missing}")).status_code == 404
    assert (await client.get(f"/api/documents/{missing}/file")).status_code == 404
