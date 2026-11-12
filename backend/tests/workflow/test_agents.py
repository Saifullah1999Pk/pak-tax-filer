"""The document, validation and research agents (feature 007, tasks T007 and T009; research R4,
R5; FR-003 to FR-007).

Scripted with the fake agent client over the real toolbox and the small test corpus. What each
step decides (what's missing, which rules break, which passages exist) is plain code; an agent
only explains it, and any text that fails its check is replaced by the plain result.
"""

import asyncio
import uuid
from typing import Any

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from rag_helpers import QUESTION, a_corpus, a_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import DocType
from app.documents.service import confirmed_documents
from app.rag.embed import FakeEmbedder
from app.rag.models import Passage
from app.workflow.agents import document_step, research_step, validation_step
from app.workflow.client import AgentError, FakeAgentClient, Script
from app.workflow.tools import Toolbox

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def setup(
    db: AsyncSession, *certificates: tuple[DocType, dict[str, str]]
) -> tuple[Toolbox, list[Any]]:
    """A user with these confirmed certificates, the test corpus, and their toolbox."""
    user = await a_user(db)
    await a_corpus(db)
    for doc_type, values in certificates:
        await add_confirmed_document(db, user.id, doc_type, values)
    tools = Toolbox(db=db, user_id=user.id, profile_tax_year=PROFILE_YEAR, embedder=FakeEmbedder())
    return tools, await confirmed_documents(db, user.id, PROFILE_YEAR)


# ---- Document step (FR-003) ----


async def test_without_a_salary_certificate_it_is_missing_whatever_the_agent_says(
    db: AsyncSession,
) -> None:
    """Fails if what's missing depends on the AI, or the plain message doesn't say a bank
    certificate is optional and where to upload."""
    tools, _ = await setup(db, (DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "1000"}))
    client = FakeAgentClient(
        {
            "document": Script(
                calls=[("list_confirmed_documents", {})], reply={"message": "All set!"}
            )
        }
    )

    agent = await document_step(client, tools, use_ai=True)
    plain = await document_step(FakeAgentClient(), tools, use_ai=True)

    assert agent["missing"] == ["salary_certificate"] and agent["message"] == "All set!"
    assert plain["missing"] == ["salary_certificate"] and plain["fallback"] is True
    assert "optional" in plain["message"] and "Documents page" in plain["message"]


async def test_with_a_salary_certificate_nothing_is_missing(db: AsyncSession) -> None:
    """Fails if a confirmed salary certificate isn't enough to go on (bank is optional)."""
    tools, _ = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))

    step = await document_step(FakeAgentClient(), tools, use_ai=True)

    assert step["missing"] == []


# ---- Validation step (FR-004) ----


async def test_validation_explains_an_issue_and_names_the_certificate(db: AsyncSession) -> None:
    """Fails if 003's taxable-above-gross issue is lost, or the run is blocked by it (issues
    warn; the user decides at the gate)."""
    bad = {**SALARY, "taxable_salary": "2500000"}
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, bad))
    client = FakeAgentClient(
        {
            "validation": Script(
                calls=[
                    (
                        "validate_salary_information",
                        {
                            "tax_year": PROFILE_YEAR,
                            "gross_salary": "2000000",
                            "taxable_salary": "2500000",
                            "tax_deducted": "75000",
                        },
                    )
                ],
                reply={
                    "message": "Your salary certificate shows taxable salary of 2500000, "
                    "above the gross 2000000."
                },
            )
        }
    )

    step = await validation_step(client, tools, documents, use_ai=True)

    assert step["fallback"] is False and "2500000" in step["message"]
    assert {i["field"] for i in step["issues"]} == {"gross_salary", "taxable_salary"}
    assert all(i["document_id"] == str(documents[0].id) for i in step["issues"])
    assert "Salary certificate" in step["issues"][0]["certificate"]


async def test_clean_figures_have_no_issues(db: AsyncSession) -> None:
    """Fails if consistent figures are reported as a problem."""
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))

    step = await validation_step(FakeAgentClient(), tools, documents, use_ai=True)

    assert step["issues"] == [] and step["fallback"] is True


# ---- Research step (FR-005) ----


async def test_research_cites_only_passages_search_found(db: AsyncSession) -> None:
    """Fails if a passage is shown that search didn't return, or without its location."""
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))
    client = FakeAgentClient(
        {
            "research": Script(
                calls=[("search_tax_documents", {"query": QUESTION})],
                reply={
                    "note": "Your employer deducts tax from your salary (P1).",
                    "citations": ["P1"],
                },
            )
        }
    )

    step = await research_step(client, tools, documents, use_ai=True)

    assert step["fallback"] is False
    assert [p["location"] for p in step["passages"]] == ["§149(1)"]
    assert set(step["passages"][0]) == {"id", "source", "kind", "location", "page", "text"}


async def test_without_the_ai_research_shows_the_plain_passages(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if research without the AI shows nothing, or a passage that isn't in the corpus.
    The real fixed queries come from the retrieval eval, where they clear the cut-off with
    Gemini's embeddings; the fake embedder needs words in common, so the test uses QUESTION."""
    monkeypatch.setattr(
        "app.workflow.agents._PLAIN_QUERIES", {DocType.SALARY_CERTIFICATE: (QUESTION,)}
    )
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))

    step = await research_step(FakeAgentClient(), tools, documents, use_ai=True)

    assert step["fallback"] is True
    assert step["passages"][0]["location"] == "§149(1)"
    corpus = set((await db.execute(select(Passage.id))).scalars())
    assert {uuid.UUID(p["id"]) for p in step["passages"]} <= corpus


async def test_with_nothing_above_the_cut_off_research_says_so_and_goes_on(
    db: AsyncSession,
) -> None:
    """Fails if a run stops, or invents passages, when the corpus has nothing relevant."""
    user = await a_user(db)  # no corpus at all
    tools = Toolbox(db=db, user_id=user.id, profile_tax_year=PROFILE_YEAR, embedder=FakeEmbedder())

    step = await research_step(FakeAgentClient(), tools, [], use_ai=True)

    assert step["passages"] == [] and "No passages" in step["note"]


# ---- Checks and fallbacks (FR-006, FR-007; research R5) ----


@pytest.mark.parametrize(
    ("agent", "reply"),
    [
        ("document", {"message": "You owe Rs 99,999."}),  # a number from nowhere
        ("validation", {"message": "Taxable salary is about 25 lakh."}),  # a number word
        ("research", {"note": "Tax is 35% (P1).", "citations": ["P1"]}),  # not in the passage
        ("research", {"note": "Employers deduct tax.", "citations": ["P9"]}),  # never found
    ],
    ids=["document-number", "validation-number-word", "research-number", "research-citation"],
)
async def test_text_failing_its_check_is_replaced_by_the_plain_result(
    db: AsyncSession, agent: str, reply: dict[str, Any]
) -> None:
    """Fails if agent text with an unchecked number or citation could be shown (SC-003)."""
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))
    calls = [("search_tax_documents", {"query": QUESTION})] if agent == "research" else []
    client = FakeAgentClient({agent: Script(calls=calls, reply=reply)})

    step = await {
        "document": lambda: document_step(client, tools, use_ai=True),
        "validation": lambda: validation_step(client, tools, documents, use_ai=True),
        "research": lambda: research_step(client, tools, documents, use_ai=True),
    }[agent]()

    assert step["fallback"] is True
    shown = str(step.get("message") or step.get("note"))
    assert "99,999" not in shown and "lakh" not in shown and "35%" not in shown


@pytest.mark.parametrize(
    "failure", [AgentError("no key"), TimeoutError()], ids=["error", "timeout"]
)
async def test_an_ai_failure_gives_the_plain_result(db: AsyncSession, failure: Exception) -> None:
    """Fails if a missing key, an API error or a timeout stops the run (SC-005)."""
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))
    client = FakeAgentClient(
        {name: Script(reply=failure) for name in ("document", "validation", "research")}
    )

    steps = [
        await document_step(client, tools, use_ai=True),
        await validation_step(client, tools, documents, use_ai=True),
        await research_step(client, tools, documents, use_ai=True),
    ]

    assert all(step["fallback"] for step in steps)


async def test_a_slow_agent_is_cut_off_at_the_step_limit(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if one slow agent can hold the run past its 15 seconds (FR-019)."""
    monkeypatch.setattr("app.workflow.agents.STEP_SECONDS", 0.05)
    tools, _ = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))

    class Slow(FakeAgentClient):
        """An agent that takes longer than the step may."""

        async def run(self, *args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            await asyncio.sleep(1)

    step = await document_step(Slow(), tools, use_ai=True)

    assert step["fallback"] is True


async def test_past_a_question_limit_no_agent_is_asked(db: AsyncSession) -> None:
    """Fails if an agent is called when the run may not use the AI (FR-018)."""
    tools, documents = await setup(db, (DocType.SALARY_CERTIFICATE, SALARY))
    client = FakeAgentClient(
        {name: Script(reply={}) for name in ("document", "validation", "research")}
    )

    await document_step(client, tools, use_ai=False)
    await validation_step(client, tools, documents, use_ai=False)
    step = await research_step(client, tools, documents, use_ai=False)

    assert not client.calls and step["fallback"] is True
