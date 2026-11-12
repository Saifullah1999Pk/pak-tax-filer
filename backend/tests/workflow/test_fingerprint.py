"""The inputs' fingerprint (feature 007, task T003; research R3).

A run's step outputs and its approval are only valid for the inputs they were made for: the
user's confirmed certificates and profile. Any change to those must change the fingerprint.
"""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocStatus, DocType, FieldName
from app.documents.service import ConfirmedDocument
from app.profile.service import save_profile
from app.workflow.fingerprint import current_fingerprint, fingerprint

CONFIRMED = datetime(2026, 11, 1, tzinfo=UTC)
SALARY = ConfirmedDocument(
    id=uuid.UUID(int=1),
    doc_type=DocType.SALARY_CERTIFICATE,
    values={FieldName.TAXABLE_SALARY: Decimal("1800000"), FieldName.TAX_YEAR: "2025-26"},
    confirmed_at=CONFIRMED,
)
BANK = ConfirmedDocument(
    id=uuid.UUID(int=2),
    doc_type=DocType.BANK_PROFIT_CERTIFICATE,
    values={FieldName.PROFIT_AMOUNT: Decimal("100000")},
    confirmed_at=CONFIRMED,
)


def test_the_same_inputs_give_the_same_fingerprint_in_any_order() -> None:
    """Fails if the order certificates are read in could look like a change."""
    assert fingerprint([SALARY, BANK], "2025-26", True) == fingerprint(
        [BANK, SALARY], "2025-26", True
    )
    assert len(fingerprint([SALARY], "2025-26", True)) == 64


@pytest.mark.parametrize(
    ("documents", "tax_year", "on_atl"),
    [
        ([SALARY, BANK], "2025-26", True),  # a certificate added
        ([], "2025-26", True),  # one deleted
        ([replace(SALARY, confirmed_at=CONFIRMED + timedelta(minutes=5))], "2025-26", True),
        (
            [
                replace(
                    SALARY, values={**SALARY.values, FieldName.TAXABLE_SALARY: Decimal("1800001")}
                )
            ],
            "2025-26",
            True,
        ),
        ([SALARY], "2026-27", True),  # the profile's tax year
        ([SALARY], "2025-26", False),  # the profile's ATL status
    ],
    ids=["added", "deleted", "re-confirmed", "value-edited", "tax-year", "atl"],
)
def test_any_change_to_the_inputs_changes_it(
    documents: list[ConfirmedDocument], tax_year: str, on_atl: bool
) -> None:
    """Fails if a change the gate must notice could leave an old approval standing (FR-013)."""
    assert fingerprint(documents, tax_year, on_atl) != fingerprint([SALARY], "2025-26", True)


@pytest.mark.anyio
async def test_unconfirmed_documents_do_not_change_it(db: AsyncSession) -> None:
    """Fails if a certificate still awaiting review could invalidate an approval (or count)."""
    user = User(email="fp@example.com", password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, {"taxable_salary": "1"})
    before = await current_fingerprint(db, user)

    pending = await add_confirmed_document(
        db, user.id, DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "5"}
    )
    pending.status = DocStatus.NEEDS_REVIEW
    await db.flush()

    assert await current_fingerprint(db, user) == before


@pytest.mark.anyio
async def test_without_a_profile_there_is_no_fingerprint(db: AsyncSession) -> None:
    """Fails if a run could be checked against inputs that don't exist yet (no profile)."""
    user = User(email="fp2@example.com", password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()

    assert await current_fingerprint(db, user) is None


def test_an_amount_read_back_from_the_database_is_the_same_amount() -> None:
    """Fails if 1800000 and 1800000.00 (the same amount, as cached and as read back from the
    database) give different fingerprints, which made an approval look stale at random."""
    stored = replace(
        SALARY, values={**SALARY.values, FieldName.TAXABLE_SALARY: Decimal("1800000.00")}
    )
    in_another_zone = replace(
        SALARY, confirmed_at=CONFIRMED.astimezone(timezone(timedelta(hours=5)))
    )

    assert fingerprint([stored], "2025-26", True) == fingerprint([SALARY], "2025-26", True)
    assert fingerprint([in_another_zone], "2025-26", True) == fingerprint([SALARY], "2025-26", True)
