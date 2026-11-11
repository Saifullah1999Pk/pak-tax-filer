"""The MCP server's three tools (feature 006, task T030; contracts/mcp-tools.md, research R9).

Every call checks the token (PAKTAX_TOKEN) and acts as its owner, for that owner's data only
(SC-006). The tools call the app's own functions, so there is one implementation of each rule:
search is app.rag.search (counted against the same question limits as Ask, FR-009b), the tax
is 004's engine on confirmed certificates only (Principle III), and validation is 003's rule
check. No tool writes an answer or produces a tax figure of its own (Principle I).
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.extraction.rules import check_rules
from app.documents.models import DocType, FieldName
from app.profile.service import get_profile
from app.rag.checks import written_in_english
from app.rag.embed import Embedder, EmbeddingError
from app.rag.search import search
from app.rag.service import UNAVAILABLE_MESSAGE, refusal_message, use_question
from app.tax.engine import calculate
from app.tax.rates import RATES, rates_for
from app.tax.router import TaxOut, tax_out
from app.tax.service import tax_inputs
from app.tokens.service import owner_of

INVALID_TOKEN = "invalid or expired token"
# The year used when the token's owner has no profile yet (004 then says to set ATL status).
LATEST_TAX_YEAR = max(RATES)

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class PassageOut(BaseModel):
    """A passage and where it is, so the client can cite it."""

    title: str
    kind: str
    location: str
    page: int
    text: str
    score: float


class SearchOut(BaseModel):
    """Up to five passages, or none and not_covered below the relevance cut-off."""

    passages: list[PassageOut]
    not_covered: bool


class Issue(BaseModel):
    """A field that breaks one of 003's rules, and why."""

    field: str
    reason: str


class ValidationOut(BaseModel):
    """Whether the figures pass 003's rule checks; never a tax figure."""

    ok: bool
    issues: list[Issue]


def build_server(token: str | None, sessions: Sessions, embedder: Embedder) -> MCPServer:
    """The server for one token; `sessions` opens a database session per call."""
    server = MCPServer(
        "pak-tax-filer",
        instructions=(
            "Tools for one PakTaxFiler user's Pakistani income tax (tax year from their profile). "
            "Results are not yet reviewed by a tax practitioner and are not tax advice."
        ),
    )

    @asynccontextmanager
    async def as_owner() -> AsyncIterator[tuple[AsyncSession, User]]:
        async with sessions() as db:
            user = await owner_of(db, token)
            if user is None:
                raise ToolError(INVALID_TOKEN)
            await db.commit()  # last_used_at, even if the tool then fails
            yield db, user

    @server.tool()
    async def search_tax_documents(
        query: Annotated[str, Field(min_length=1, max_length=1000)],
    ) -> SearchOut:
        """Search FBR's Income Tax Ordinance and return-filing manual: up to 5 passages with
        their document, location and page, or not_covered. Returns passages, never an answer."""
        async with as_owner() as (db, user):
            if not written_in_english(query):
                return SearchOut(passages=[], not_covered=True)
            refused = await use_question(db, user.id)
            if refused is not None:
                raise ToolError(refusal_message(refused))
            await db.commit()
            try:
                found = await search(db, embedder, query)
            except EmbeddingError as exc:
                raise ToolError(UNAVAILABLE_MESSAGE) from exc
            if not found.covered:
                return SearchOut(passages=[], not_covered=True)
            return SearchOut(
                passages=[
                    PassageOut(
                        title=p.title,
                        kind=p.kind.value,
                        location=p.location,
                        page=p.page,
                        text=p.text,
                        score=round(p.score, 3),
                    )
                    for p in found.passages
                ],
                not_covered=False,
            )

    @server.tool()
    async def calculate_income_tax() -> TaxOut:
        """The user's income tax for their profile's tax year, from their confirmed certificates
        only: exactly what the app's Tax page shows, every step cited, or why it can't be
        calculated."""
        async with as_owner() as (db, user):
            profile = await get_profile(db, user)
            tax_year = LATEST_TAX_YEAR if profile is None else profile.tax_year
            return tax_out(calculate(await tax_inputs(db, user, tax_year), rates_for(tax_year)))

    @server.tool()
    async def validate_salary_information(
        tax_year: str, gross_salary: str, taxable_salary: str, tax_deducted: str
    ) -> ValidationOut:
        """Check a salary certificate's figures (decimal strings) against the app's rules: no
        negative amounts, taxable salary and tax deducted not above gross salary, and a tax year
        matching the user's profile. Never calculates tax."""
        async with as_owner() as (db, user):
            profile = await get_profile(db, user)
            profile_year = LATEST_TAX_YEAR if profile is None else profile.tax_year
            amounts = {
                FieldName.GROSS_SALARY: gross_salary,
                FieldName.TAXABLE_SALARY: taxable_salary,
                FieldName.TAX_DEDUCTED: tax_deducted,
            }
            issues = [
                Issue(field=name.value, reason="Not an amount.")
                for name, text in amounts.items()
                if _decimal(text) is None
            ]
            values: dict[FieldName, Decimal | str | None] = {
                name: _decimal(text) for name, text in amounts.items()
            }
            values[FieldName.TAX_YEAR] = tax_year.strip()
            reasons = check_rules(DocType.SALARY_CERTIFICATE, values, profile_year)
            issues += [Issue(field=name.value, reason=reason) for name, reason in reasons.items()]
            return ValidationOut(ok=not issues, issues=issues)

    return server


def _decimal(text: str) -> Decimal | None:
    """The amount, or None if it isn't a plain decimal number."""
    try:
        value = Decimal(text.strip().replace(",", ""))
    except InvalidOperation:
        return None
    return value if value.is_finite() else None
