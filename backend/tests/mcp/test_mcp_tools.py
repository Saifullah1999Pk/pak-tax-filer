"""The MCP server's three tools, through a real in-process MCP client (feature 006, task T027;
contracts/mcp-tools.md, SC-005, SC-006, Principle III).

The server shares the test's rolled-back session and the fake embedder; nothing reaches the
network.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from mcp import Client
from rag_helpers import QUESTION, a_corpus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocStatus, DocType
from app.mcp_server.server import INVALID_TOKEN, build_server
from app.profile.service import save_profile
from app.rag.embed import FakeEmbedder
from app.rag.models import AskRequest
from app.rag.search import search
from app.tokens.models import PersonalAccessToken
from app.tokens.service import create_token

pytestmark = pytest.mark.anyio

TOOLS = {"search_tax_documents", "calculate_income_tax", "validate_salary_information"}
CALLS: dict[str, dict[str, str]] = {
    "search_tax_documents": {"query": QUESTION},
    "calculate_income_tax": {},
    "validate_salary_information": {
        "tax_year": PROFILE_YEAR,
        "gross_salary": "1200000",
        "taxable_salary": "1000000",
        "tax_deducted": "30000",
    },
}
EXAMPLES = yaml.safe_load(
    (Path(__file__).parents[1] / "tax" / "worked_examples.yaml").read_text(encoding="utf-8")
)["examples"]


async def a_user(db: AsyncSession, email: str = "mcp@example.com") -> User:
    """A synthetic user."""
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    return user


async def call(db: AsyncSession, token: str | None, tool: str, arguments: dict[str, Any]) -> Any:
    """Call one tool as an MCP client would; the result as sent over the protocol."""

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield db

    server = build_server(token, sessions, FakeEmbedder())
    async with Client(server) as client:
        return await client.call_tool(tool, arguments)


def body(result: Any) -> Any:
    """A successful result's JSON."""
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


async def test_exactly_three_tools_are_listed(db: AsyncSession) -> None:
    """Fails if a tool is added or removed (Principle VII: scope)."""

    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        yield db

    async with Client(build_server(None, sessions, FakeEmbedder())) as client:
        listed = await client.list_tools()

    assert {tool.name for tool in listed.tools} == TOOLS


@pytest.mark.parametrize("tool", sorted(TOOLS))
@pytest.mark.parametrize("state", ["missing", "wrong", "expired", "revoked"])
async def test_every_tool_refuses_an_invalid_token(db: AsyncSession, tool: str, state: str) -> None:
    """Fails if any tool acts for a missing, wrong, expired or revoked token (SC-006)."""
    user = await a_user(db)
    token = await create_token(db, user.id, "MCP client")
    stored = (await db.execute(select(PersonalAccessToken))).scalar_one()
    if state == "expired":
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    if state == "revoked":
        stored.revoked_at = datetime.now(UTC)
    await db.flush()
    presented = {"missing": None, "wrong": token[:-1] + "x"}.get(state, token)

    result = await call(db, presented, tool, CALLS[tool])

    assert result.is_error and INVALID_TOKEN in result.content[0].text


async def test_search_returns_what_the_app_search_does(db: AsyncSession) -> None:
    """Fails if the tool's passages differ from app.rag.search, or lack a citation's parts."""
    await a_corpus(db)
    user = await a_user(db)
    token = await create_token(db, user.id, "MCP client")

    result = body(await call(db, token, "search_tax_documents", {"query": QUESTION}))

    expected = await search(db, FakeEmbedder(), QUESTION)
    assert result["not_covered"] is False
    assert [(p["location"], p["page"], p["kind"]) for p in result["passages"]] == [
        (p.location, p.page, p.kind.value) for p in expected.passages
    ]
    assert set(result["passages"][0]) == {"title", "kind", "location", "page", "text", "score"}


async def test_search_below_the_cut_off_is_not_covered(db: AsyncSession) -> None:
    """Fails if a question far from every passage returns passages anyway (FR-006)."""
    await a_corpus(db)
    user = await a_user(db)
    token = await create_token(db, user.id, "MCP client")

    result = body(
        await call(db, token, "search_tax_documents", {"query": "Sales tax on imported cars?"})
    )

    assert result == {"passages": [], "not_covered": True}


async def test_searches_count_against_the_question_limits(db: AsyncSession) -> None:
    """Fails if MCP searches escape the hourly limit or the app's daily cap (FR-009b)."""
    await a_corpus(db)
    user = await a_user(db)
    token = await create_token(db, user.id, "MCP client")
    now = datetime.now(UTC)
    db.add_all(
        AskRequest(user_id=user.id, created_at=now - timedelta(minutes=i)) for i in range(30)
    )
    await db.flush()

    result = await call(db, token, "search_tax_documents", {"query": QUESTION})

    assert result.is_error and "try again later" in result.content[0].text.lower()
    count = (await db.execute(select(func.count()).select_from(AskRequest))).scalar_one()
    assert count == 30


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
async def test_calculate_returns_the_tax_page_body(
    client: AsyncClient, db: AsyncSession, logged_in_user: User, example: dict[str, Any]
) -> None:
    """Fails if the tool's result differs from GET /api/tax/{year} for a signed-off worked
    example: one engine, one answer, wherever it's asked (SC-005)."""
    inputs = example["inputs"]
    if inputs["atl"] is not None:
        await save_profile(db, logged_in_user, PROFILE_YEAR, on_atl=inputs["atl"])
    for certificate in inputs["salary_certificates"]:
        await add_confirmed_document(db, logged_in_user.id, DocType.SALARY_CERTIFICATE, certificate)
    for certificate in inputs["bank_certificates"]:
        await add_confirmed_document(
            db, logged_in_user.id, DocType.BANK_PROFIT_CERTIFICATE, certificate
        )
    token = await create_token(db, logged_in_user.id, "MCP client")

    result = body(await call(db, token, "calculate_income_tax", {}))

    assert result == (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()


async def test_calculate_without_a_profile_needs_the_atl_answer(db: AsyncSession) -> None:
    """Fails if a token owner without a profile gets anything but 004's needs_atl_answer."""
    user = await a_user(db)
    token = await create_token(db, user.id, "MCP client")

    result = body(await call(db, token, "calculate_income_tax", {}))

    assert result["blocked_reason"] == "needs_atl_answer" and result["salary_tax"] is None
    assert result["label"] == "Not yet reviewed by a tax practitioner. Not tax advice."


async def test_calculate_ignores_certificates_awaiting_review(db: AsyncSession) -> None:
    """Fails if AI-extracted figures nobody confirmed reach the calculation (Principle III)."""
    user = await a_user(db)
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    document = await add_confirmed_document(
        db, user.id, DocType.SALARY_CERTIFICATE, {"taxable_salary": "2000000"}
    )
    document.status = DocStatus.NEEDS_REVIEW
    for field in document.fields:
        field.confirmed = False
    await db.flush()
    token = await create_token(db, user.id, "MCP client")

    result = body(await call(db, token, "calculate_income_tax", {}))

    assert result["blocked_reason"] == "no_confirmed_salary_certificate"
    assert result["salary_tax"] is None and result["steps"] == []


async def test_validate_reports_taxable_above_gross_and_no_tax_figure(db: AsyncSession) -> None:
    """Fails if the rule check misses taxable salary above gross, or the tool returns a tax
    figure (it only checks figures; the engine calculates)."""
    user = await a_user(db)
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    token = await create_token(db, user.id, "MCP client")
    arguments = {**CALLS["validate_salary_information"], "taxable_salary": "1500000"}

    result = body(await call(db, token, "validate_salary_information", arguments))

    assert set(result) == {"ok", "issues"} and result["ok"] is False
    assert {issue["field"] for issue in result["issues"]} == {"gross_salary", "taxable_salary"}


async def test_validate_compares_the_tax_year_with_the_profile(db: AsyncSession) -> None:
    """Fails if a certificate for another year passes as this profile's year."""
    user = await a_user(db)
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    token = await create_token(db, user.id, "MCP client")
    arguments = {**CALLS["validate_salary_information"], "tax_year": "2023-24"}

    result = body(await call(db, token, "validate_salary_information", arguments))

    assert result["ok"] is False and result["issues"][0]["field"] == "tax_year"


async def test_validate_passes_consistent_figures(db: AsyncSession) -> None:
    """Fails if figures that break no rule are reported as issues."""
    user = await a_user(db)
    await save_profile(db, user, PROFILE_YEAR, on_atl=True)
    token = await create_token(db, user.id, "MCP client")

    result = body(
        await call(db, token, "validate_salary_information", CALLS["validate_salary_information"])
    )

    assert result == {"ok": True, "issues": []}
