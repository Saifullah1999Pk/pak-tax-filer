"""The agents' tools (feature 007, task T005; contracts/workflow-api.md "Agent tools").

Read-only by construction (FR-010): the toolbox offers exactly four tools, none of which writes,
confirms, approves or calculates; they call the app's own functions.
"""

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from rag_helpers import QUESTION, a_corpus, a_user
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocStatus, DocType
from app.rag.embed import FakeEmbedder
from app.workflow.tools import AGENT_TOOLS, TOOL_NAMES, Toolbox

pytestmark = pytest.mark.anyio

FORBIDDEN = ("approve", "confirm", "edit", "set", "save", "delete", "calculate", "update", "write")


def test_there_are_exactly_four_read_only_tools() -> None:
    """Fails if a tool is added that could change a run, a document or a figure (FR-010)."""
    assert TOOL_NAMES == {
        "list_confirmed_documents",
        "validate_salary_information",
        "check_bank_certificate",
        "search_tax_documents",
    }
    # Whole words: "list_confirmed_documents" reads confirmations, it doesn't confirm.
    assert not [name for name in TOOL_NAMES if set(name.split("_")) & set(FORBIDDEN)]
    public = {
        name
        for name in dir(Toolbox)
        if not name.startswith("_") and callable(getattr(Toolbox, name))
    }
    assert public == TOOL_NAMES
    assert set().union(*AGENT_TOOLS.values()) == TOOL_NAMES


async def toolbox(db: AsyncSession) -> tuple[Toolbox, object]:
    """A toolbox for a synthetic user with one confirmed salary certificate."""
    user = await a_user(db)
    await add_confirmed_document(
        db,
        user.id,
        DocType.SALARY_CERTIFICATE,
        {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"},
    )
    return Toolbox(
        db=db, user_id=user.id, profile_tax_year=PROFILE_YEAR, embedder=FakeEmbedder()
    ), user


async def test_only_confirmed_certificates_are_listed(db: AsyncSession) -> None:
    """Fails if a certificate awaiting review could look ready to the document agent."""
    tools, user = await toolbox(db)
    pending = await add_confirmed_document(db, user.id, DocType.BANK_PROFIT_CERTIFICATE, {})  # type: ignore[attr-defined]
    pending.status = DocStatus.NEEDS_REVIEW
    await db.flush()

    listed = await tools.list_confirmed_documents()

    assert [c["type"] for c in listed["certificates"]] == ["salary_certificate"]
    assert listed["upload_page"] == "/documents"


async def test_the_checks_are_003s_rules(db: AsyncSession) -> None:
    """Fails if the validation tools disagree with 003's rules (taxable above gross; withheld
    above profit; another tax year)."""
    tools, _ = await toolbox(db)

    salary = await tools.validate_salary_information(PROFILE_YEAR, "1200000", "1500000", "0")
    bank = await tools.check_bank_certificate("2023-24", "100000", "150000")

    assert salary["ok"] is False and {i["field"] for i in salary["issues"]} == {
        "gross_salary",
        "taxable_salary",
    }
    assert {i["field"] for i in bank["issues"]} == {"tax_withheld", "profit_amount", "tax_year"}


async def test_search_returns_corpus_passages_and_remembers_them(db: AsyncSession) -> None:
    """Fails if search returns anything but corpus passages with their citations, or forgets
    what it found (the research agent's citations are checked against these)."""
    tools, _ = await toolbox(db)
    await a_corpus(db)

    found = await tools.search_tax_documents(QUESTION)
    missed = await tools.search_tax_documents("What is the sales tax on imported cars?")

    assert found["passages"][0]["location"] == "§149(1)" and found["not_covered"] is False
    assert set(found["passages"][0]) == {"label", "source", "kind", "location", "page", "text"}
    assert missed == {"passages": [], "not_covered": True}
    assert tools.found[0].location == "§149(1)"
