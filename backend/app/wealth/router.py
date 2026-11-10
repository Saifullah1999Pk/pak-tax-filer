"""GET and PUT /api/wealth/{tax_year} (feature 005, task T010; contracts/wealth-api.md, R8).

HTTP only: logic lives in service.py and the pure reconcile.py. A user only ever reads or writes
their own statement (FR-016); the result is recalculated on every request (FR-012).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.settings import get_settings
from app.tax.rates import rates_for
from app.tax.summary import GeminiSummariser, Summariser
from app.wealth.schemas import StatementIn, WealthOut
from app.wealth.service import save_statement, wealth_view
from app.wealth.summary import WEALTH_INSTRUCTIONS

router = APIRouter(prefix="/api/wealth", tags=["wealth"])

CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_wealth_summariser() -> Summariser:
    """The summary writer the wealth page uses (tests replace it with a FakeSummariser)."""
    settings = get_settings()
    return GeminiSummariser(
        api_key=settings.gemini_api_key,
        model=settings.summary_model,
        effort=settings.summary_effort,
        instructions=WEALTH_INSTRUCTIONS,
    )


SummariserDep = Annotated[Summariser, Depends(get_wealth_summariser)]


def _known_year(tax_year: str) -> None:
    """404 for a tax year the app has no FBR rates for (as the tax page)."""
    try:
        rates_for(tax_year)
    except KeyError as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rates for that tax year.") from missing


@router.get("/{tax_year}")
async def read_wealth(
    tax_year: str, user: CurrentUser, db: DbSession, summariser: SummariserDep
) -> WealthOut:
    """The saved statement, the certificate lines and the reconciliation."""
    _known_year(tax_year)
    return await wealth_view(db, user.id, tax_year, summariser)


@router.put("/{tax_year}", dependencies=[Depends(require_json)])
async def save_wealth(
    tax_year: str,
    body: StatementIn,
    user: CurrentUser,
    db: DbSession,
    summariser: SummariserDep,
) -> WealthOut:
    """Replace the whole statement, then answer as GET does."""
    _known_year(tax_year)
    await save_statement(db, user.id, tax_year, body)
    await db.commit()
    return await wealth_view(db, user.id, tax_year, summariser)
