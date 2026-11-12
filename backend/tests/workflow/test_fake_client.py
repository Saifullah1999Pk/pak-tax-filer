"""The fake agent client the workflow's tests use (feature 007, task T006).

It must behave like the real client from the service's side: tool calls go through the real
toolbox (so search results are remembered as they would be live), only the agent's own tools can
be called, and a scripted failure is raised as the real client would raise it.
"""

import pytest
from document_helpers import PROFILE_YEAR
from pydantic import BaseModel
from rag_helpers import QUESTION, a_corpus, a_user, sessions_of
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed import FakeEmbedder
from app.workflow.client import AgentError, FakeAgentClient, Script
from app.workflow.tools import AGENT_TOOLS, Toolbox

pytestmark = pytest.mark.anyio


class Note(BaseModel):
    """A research agent's final answer."""

    note: str
    citations: list[str]


async def a_toolbox(db: AsyncSession) -> Toolbox:
    """Tools for a synthetic user over the small test corpus."""
    user = await a_user(db)
    await a_corpus(db)
    return Toolbox(
        sessions=sessions_of(db),
        user_id=user.id,
        profile_tax_year=PROFILE_YEAR,
        embedder=FakeEmbedder(),
    )


async def test_scripted_tool_calls_go_through_the_real_toolbox(db: AsyncSession) -> None:
    """Fails if the fake skips the tools, so tests could pass with citations never searched."""
    tools = await a_toolbox(db)
    client = FakeAgentClient(
        {
            "research": Script(
                calls=[("search_tax_documents", {"query": QUESTION})],
                reply={"note": "Employers deduct tax (P1).", "citations": ["P1"]},
            )
        }
    )

    answer = await client.run(
        "research", "instructions", "prompt", tools, AGENT_TOOLS["research"], Note
    )

    assert answer == Note(note="Employers deduct tax (P1).", citations=["P1"])
    assert tools.found[0].location == "§149(1)"
    assert client.calls == [("research", "search_tax_documents", {"query": QUESTION})]


async def test_an_agent_cannot_call_another_agents_tool(db: AsyncSession) -> None:
    """Fails if the document agent could search, or call anything outside its own tools."""
    tools = await a_toolbox(db)
    client = FakeAgentClient(
        {"document": Script(calls=[("search_tax_documents", {"query": "x"})], reply={})}
    )

    with pytest.raises(AgentError):
        await client.run("document", "i", "p", tools, AGENT_TOOLS["document"], Note)


@pytest.mark.parametrize("failure", [TimeoutError(), AgentError("refused")])
async def test_a_scripted_failure_is_raised(db: AsyncSession, failure: Exception) -> None:
    """Fails if a timeout or a refusal can't be simulated for the fallback tests."""
    tools = await a_toolbox(db)
    client = FakeAgentClient({"validation": Script(reply=failure)})

    with pytest.raises(type(failure)):
        await client.run("validation", "i", "p", tools, AGENT_TOOLS["validation"], Note)
