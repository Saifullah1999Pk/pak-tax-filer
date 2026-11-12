"""The real agent client through the Gemini SDK, with an httpx2 MockTransport in place of Google
(feature 007, task T009; as 006's test_gemini_answerer.py). No key or quota is used."""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from document_helpers import PROFILE_YEAR
from pydantic import BaseModel
from rag_helpers import QUESTION, a_corpus, a_user, sessions_of
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed import FakeEmbedder
from app.workflow.client import AgentError, GeminiAgentClient
from app.workflow.tools import AGENT_TOOLS, Toolbox

pytestmark = pytest.mark.anyio

Handler = Callable[[httpx2.Request], httpx2.Response]


class Note(BaseModel):
    """A research agent's final answer."""

    note: str
    citations: list[str]


def client(handler: Handler, api_key: str | None = "test-key-not-real") -> GeminiAgentClient:
    """A GeminiAgentClient whose HTTP calls go to `handler`."""
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return GeminiAgentClient(
        api_key=api_key, model="gemini-test", effort="minimal", http_client=http
    )


def calls_tool(name: str, args: dict[str, Any]) -> httpx2.Response:
    """Gemini asking for one tool."""
    part = {"functionCall": {"name": name, "args": args}}
    return httpx2.Response(
        200,
        json={
            "candidates": [{"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}]
        },
    )


def says(text: str, finish: str = "STOP") -> httpx2.Response:
    """Gemini's final text."""
    return httpx2.Response(
        200,
        json={
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish}
            ]
        },
    )


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


async def test_a_tool_call_is_answered_then_the_final_answer_is_read(db: AsyncSession) -> None:
    """Fails if a tool's result isn't sent back to Gemini, or the final JSON isn't read."""
    tools = await a_toolbox(db)
    replies = [
        calls_tool("search_tax_documents", {"query": QUESTION}),
        says('```json\n{"note": "Employers deduct tax (P1).", "citations": ["P1"]}\n```'),
    ]
    sent: list[dict[str, Any]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return replies.pop(0)

    answer = await client(handle).run(
        "research", "instructions", "prompt", tools, AGENT_TOOLS["research"], Note
    )

    assert answer == Note(note="Employers deduct tax (P1).", citations=["P1"])
    assert tools.found[0].location == "§149(1)"
    declared = [f["name"] for t in sent[0]["tools"] for f in t["functionDeclarations"]]
    assert declared == ["search_tax_documents"]  # only the agent's own tools
    response_part = sent[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert response_part["name"] == "search_tax_documents"
    assert response_part["response"]["result"]["passages"][0]["location"] == "§149(1)"


async def test_a_tool_the_agent_lacks_is_refused(db: AsyncSession) -> None:
    """Fails if Gemini can call a tool outside the agent's own set (FR-010)."""
    tools = await a_toolbox(db)

    with pytest.raises(AgentError):
        await client(lambda r: calls_tool("search_tax_documents", {"query": "x"})).run(
            "document", "i", "p", tools, AGENT_TOOLS["document"], Note
        )


async def test_searches_stop_after_three(db: AsyncSession) -> None:
    """Fails if the research agent can search more than 3 times (research R4)."""
    tools = await a_toolbox(db)
    replies = [calls_tool("search_tax_documents", {"query": f"{QUESTION} {i}"}) for i in range(4)]
    replies.append(says('{"note": "n", "citations": []}'))
    sent: list[dict[str, Any]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return replies.pop(0)

    await client(handle).run("research", "i", "p", tools, AGENT_TOOLS["research"], Note)

    fourth = sent[4]["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"]
    assert fourth == {"error": "No more searches."}


@pytest.mark.parametrize(
    "response",
    [
        says("not json at all"),
        says('{"note": "missing citations"}'),
        says('{"note": "n", "citations": []}', finish="MAX_TOKENS"),
        httpx2.Response(400, json={"error": {"code": 400, "message": "Bad request."}}),
    ],
    ids=["not-json", "wrong-shape", "cut-short", "api-error"],
)
async def test_an_unusable_reply_is_an_agent_error(
    db: AsyncSession, response: httpx2.Response
) -> None:
    """Fails if a malformed, cut-short or failed reply could be used."""
    tools = await a_toolbox(db)

    with pytest.raises(AgentError):
        await client(lambda r: response).run(
            "research", "i", "p", tools, AGENT_TOOLS["research"], Note
        )


async def test_an_agent_that_never_finishes_is_stopped(db: AsyncSession) -> None:
    """Fails if a model that keeps calling tools could loop forever."""
    tools = await a_toolbox(db)

    with pytest.raises(AgentError):
        await client(lambda r: calls_tool("list_confirmed_documents", {})).run(
            "document", "i", "p", tools, AGENT_TOOLS["document"], Note
        )


async def test_without_a_key_nothing_is_sent(db: AsyncSession) -> None:
    """Fails if a missing key causes a request instead of an AgentError."""
    tools = await a_toolbox(db)

    def handle(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError(f"No request expected, got {request.url}")

    with pytest.raises(AgentError):
        await client(handle, api_key=None).run(
            "research", "i", "p", tools, AGENT_TOOLS["research"], Note
        )
