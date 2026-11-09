"""GET /api/tax/{tax_year} (feature 004, tasks T011-T012; contracts/tax-api.md).

Inputs come only from confirmed certificates (feature 003's confirmed_documents) and the ATL
status in the user's taxpayer profile (feature 002); results are recalculated on every request.
"""

from decimal import Decimal

import pytest
from httpx2 import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import (
    FIELDS_BY_TYPE,
    Confidence,
    DocStatus,
    DocType,
    Document,
    ExtractedField,
    FieldName,
)
from app.main import app
from app.profile.service import save_profile
from app.tax.router import get_summariser
from app.tax.summary import FakeSummariser

pytestmark = pytest.mark.anyio

LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."


async def add_document(
    db: AsyncSession,
    user: User,
    doc_type: DocType,
    values: dict[FieldName, str],
    status: DocStatus = DocStatus.CONFIRMED,
) -> None:
    """A certificate with the given figures, confirmed unless said otherwise."""
    confirmed = status is DocStatus.CONFIRMED
    fields = [
        ExtractedField(
            name=name,
            amount=None if name is FieldName.TAX_YEAR else Decimal(values[name]),
            text_value="2025-26" if name is FieldName.TAX_YEAR else None,
            confidence=Confidence.HIGH,
            user_edited=False,
            confirmed=confirmed,
        )
        for name in FIELDS_BY_TYPE[doc_type]
    ]
    db.add(
        Document(
            user_id=user.id,
            doc_type=doc_type,
            tax_year="2025-26",
            file_path="/data/uploads/synthetic.pdf",
            media_type="application/pdf",
            page_count=1,
            status=status,
            fields=fields,
        )
    )
    await db.flush()


def salary(taxable: str, deducted: str) -> dict[FieldName, str]:
    """A salary certificate's figures (gross isn't used by the tax calculation)."""
    return {
        FieldName.GROSS_SALARY: taxable,
        FieldName.TAXABLE_SALARY: taxable,
        FieldName.TAX_DEDUCTED: deducted,
    }


def bank(profit: str, withheld: str) -> dict[FieldName, str]:
    """A bank profit certificate's figures."""
    return {FieldName.PROFIT_AMOUNT: profit, FieldName.TAX_WITHHELD: withheld}


async def test_logged_out_is_refused(client: AsyncClient) -> None:
    """Fails if anyone can see a tax result without logging in."""
    assert (await client.get("/api/tax/2025-26")).status_code == 401


@pytest.mark.usefixtures("user_with_profile")
async def test_a_year_without_rates_is_404(client: AsyncClient) -> None:
    """Fails if a tax year without FBR rates is answered (with another year's rates)."""
    assert (await client.get("/api/tax/2024-25")).status_code == 404


async def test_confirmed_certificates_are_summed_and_calculated(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if two employers and two banks aren't summed, or the shape differs from the
    contract (money as strings, steps, the label)."""
    await add_document(
        db, user_with_profile, DocType.SALARY_CERTIFICATE, salary("1000000", "30000")
    )
    await add_document(db, user_with_profile, DocType.SALARY_CERTIFICATE, salary("800000", "39000"))
    await add_document(
        db, user_with_profile, DocType.BANK_PROFIT_CERTIFICATE, bank("60000", "12000")
    )
    await add_document(
        db, user_with_profile, DocType.BANK_PROFIT_CERTIFICATE, bank("40000", "8000")
    )

    response = await client.get("/api/tax/2025-26")

    assert response.status_code == 200
    body = response.json()
    assert body["tax_year"] == "2025-26"
    assert body["blocked_reason"] is None
    assert body["salary_tax"] == "72000"
    assert body["surcharge"] == "0"
    assert body["profit_tax"] == "20000"
    assert body["salary_balance"] == "3000"
    assert body["profit_balance"] == "0"
    assert body["non_atl_extra_withheld"] is None
    assert len(body["steps"]) == 5
    assert set(body["steps"][0]) == {"description", "rule_location", "result"}
    assert body["steps"][0]["result"] == "72000"
    assert body["label"] == LABEL


async def test_unconfirmed_certificates_are_ignored(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a figure the user hasn't confirmed reaches the calculation (Principle III)."""
    await add_document(
        db, user_with_profile, DocType.SALARY_CERTIFICATE, salary("1800000", "60000")
    )
    await add_document(
        db,
        user_with_profile,
        DocType.SALARY_CERTIFICATE,
        salary("5000000", "0"),
        status=DocStatus.NEEDS_REVIEW,
    )

    body = (await client.get("/api/tax/2025-26")).json()

    assert body["salary_tax"] == "72000"


async def test_atl_status_comes_from_the_profile_not_the_query(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if the page could pass its own ATL answer instead of the profile's (amended 004)."""
    await save_profile(db, logged_in_user, "2025-26", on_atl=False)
    await add_document(db, logged_in_user, DocType.SALARY_CERTIFICATE, salary("3000000", "300000"))
    await add_document(db, logged_in_user, DocType.BANK_PROFIT_CERTIFICATE, bank("200000", "80000"))

    body = (await client.get("/api/tax/2025-26?atl=yes")).json()

    assert body["non_atl_extra_withheld"] == "40000"
    assert body["profit_balance"] == "0"


async def test_without_a_profile_it_asks_for_the_atl_status(
    client: AsyncClient, db: AsyncSession, logged_in_user: User
) -> None:
    """Fails if a user with no profile gets figures instead of being sent to set ATL status."""
    await add_document(db, logged_in_user, DocType.SALARY_CERTIFICATE, salary("1800000", "60000"))

    body = (await client.get("/api/tax/2025-26")).json()

    assert body["blocked_reason"] == "needs_atl_answer"
    assert body["message"] == "Set your ATL status in your profile."
    assert body["salary_tax"] is None
    assert body["steps"] == []
    assert body["label"] == LABEL


@pytest.mark.usefixtures("user_with_profile")
async def test_without_a_confirmed_salary_certificate_it_says_so(client: AsyncClient) -> None:
    """Fails if there's nothing to calculate from but the user isn't told what to do."""
    body = (await client.get("/api/tax/2025-26")).json()

    assert body["blocked_reason"] == "no_confirmed_salary_certificate"
    assert "salary certificate" in body["message"]


async def test_a_checked_summary_is_returned_with_the_breakdown(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a safe summary is lost, or an unsafe one reaches the user (FR-011)."""
    await add_document(
        db, user_with_profile, DocType.SALARY_CERTIFICATE, salary("1800000", "60000")
    )
    for text, expected in [
        ("Your salary tax is Rs 72,000; Rs 12,000 is payable.", True),
        ("Your salary tax is Rs 75,000.", False),
    ]:
        app.dependency_overrides[get_summariser] = lambda text=text: FakeSummariser(text)
        try:
            body = (await client.get("/api/tax/2025-26")).json()
        finally:
            app.dependency_overrides.pop(get_summariser, None)

        assert (body["summary"] == text) is expected
        assert len(body["steps"]) == 5  # the breakdown is always there
