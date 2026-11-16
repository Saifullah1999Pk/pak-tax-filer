"""The guided run's three steps, as plain code (feature 007, amended 2026-11-16: the lead, "if our
code doesn't need reasoning capability then no need to add AI").

Each step's facts were always decided by code; the AI only reworded them. Now the plain result is
the result: no model, no embedding search, nothing to wait for.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from rag_helpers import a_corpus
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument
from app.workflow.steps import document_step, research_step, validation_step

pytestmark = pytest.mark.anyio

YEAR = "2025-26"
UPLOADED = datetime(2026, 11, 10, tzinfo=UTC)


def salary(taxable: str = "1800000", deducted: str = "75000") -> ConfirmedDocument:
    """A confirmed salary certificate."""
    return ConfirmedDocument(
        id=uuid.uuid4(),
        doc_type=DocType.SALARY_CERTIFICATE,
        values={
            FieldName.TAX_YEAR: YEAR,
            FieldName.GROSS_SALARY: Decimal("2000000"),
            FieldName.TAXABLE_SALARY: Decimal(taxable),
            FieldName.TAX_DEDUCTED: Decimal(deducted),
        },
        uploaded_at=UPLOADED,
    )


def bank() -> ConfirmedDocument:
    """A confirmed bank profit certificate."""
    return ConfirmedDocument(
        id=uuid.uuid4(),
        doc_type=DocType.BANK_PROFIT_CERTIFICATE,
        values={
            FieldName.TAX_YEAR: YEAR,
            FieldName.PROFIT_AMOUNT: Decimal("100000"),
            FieldName.TAX_WITHHELD: Decimal("20000"),
        },
        uploaded_at=UPLOADED,
    )


def test_without_a_salary_certificate_the_document_step_says_what_is_missing() -> None:
    """Fails if a run with no confirmed salary certificate isn't stopped with the way forward."""
    step = document_step([bank()])

    assert step["missing"] == ["salary_certificate"]
    assert "Documents page" in step["message"]
    assert "Bank certificate uploaded 10 Nov 2026" in step["message"]


def test_with_a_salary_certificate_nothing_is_missing() -> None:
    """Fails if a confirmed salary certificate isn't enough to go on."""
    step = document_step([salary()])

    assert not step["missing"]
    assert "Salary certificate uploaded 10 Nov 2026" in step["message"]


def test_the_validation_step_lists_003s_rule_issues() -> None:
    """Fails if 003's checks aren't run on every certificate, or an issue isn't named."""
    clean = validation_step([salary()], YEAR)
    broken = validation_step([salary(taxable="2500000")], YEAR)  # more than gross

    assert clean["issues"] == []
    assert clean["message"] == "The figures on your confirmed certificates are consistent."
    # 003 names both fields of a broken "part not above its whole" rule.
    assert "taxable_salary" in [issue["field"] for issue in broken["issues"]]
    assert broken["message"].startswith("Please check these before you approve:")


async def test_the_research_step_reads_the_sections_for_each_income(db: AsyncSession) -> None:
    """Fails if the research step doesn't cite the Ordinance's sections for the user's income,
    straight from the corpus (no search, so no AI and no waiting)."""
    await a_corpus(db)

    salary_only = await research_step(db, [salary()])
    both = await research_step(db, [salary(), bank()])

    assert [p["location"] for p in salary_only["passages"]] == ["§12(1)", "§149(1)"]
    assert [p["location"] for p in both["passages"]] == ["§12(1)", "§149(1)", "§7B(1)", "§151(1)"]
    assert salary_only["passages"][0]["source"] == "Income Tax Ordinance, 2001"
    assert salary_only["note"] == "These sections of the Income Tax Ordinance apply to your income."


async def test_without_the_corpus_the_research_step_says_so(db: AsyncSession) -> None:
    """Fails if a missing corpus (not built yet) breaks the run instead of saying so."""
    step = await research_step(db, [salary()])

    assert step["passages"] == []
    assert step["note"] == "No passages found in the FBR texts for your income."
