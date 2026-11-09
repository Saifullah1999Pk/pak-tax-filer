"""GET /api/tax/{tax_year} (feature 004, task T012; contracts/tax-api.md, research R6).

GET because nothing changes on the server: the result is recalculated from the user's confirmed
certificates and profile on every request. Money is returned as strings (docs/api-conventions.md).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.auth.models import User
from app.db import get_db
from app.tax.engine import TaxResult, calculate
from app.tax.rates import rates_for
from app.settings import get_settings
from app.tax.service import BLOCKED_MESSAGES, tax_inputs
from app.tax.summary import GeminiSummariser, Summariser, verified_summary

router = APIRouter(prefix="/api/tax", tags=["tax"])

# On every result (constitution Principle IV, FR-014).
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."


def get_summariser() -> Summariser:
    """The summary writer the app uses (tests replace it with a FakeSummariser)."""
    settings = get_settings()
    return GeminiSummariser(
        api_key=settings.gemini_api_key,
        model=settings.summary_model,
        effort=settings.summary_effort,
    )


class StepOut(BaseModel):
    """One breakdown step."""

    description: str
    rule_location: str
    result: str


class TaxOut(BaseModel):
    """The contract's calculated or blocked result."""

    tax_year: str
    blocked_reason: str | None
    message: str | None
    salary_tax: str | None
    surcharge: str | None
    profit_tax: str | None
    salary_balance: str | None
    profit_balance: str | None
    non_atl_extra_withheld: str | None
    steps: list[StepOut]
    summary: str | None
    label: str


def _text(amount: Decimal | None) -> str | None:
    return None if amount is None else str(amount)


def tax_out(result: TaxResult, summary: str | None = None) -> TaxOut:
    """The API form of a result: money as decimal strings, never floats."""
    return TaxOut(
        tax_year=result.tax_year,
        blocked_reason=result.blocked_reason,
        message=BLOCKED_MESSAGES.get(result.blocked_reason or ""),
        salary_tax=_text(result.salary_tax),
        surcharge=_text(result.surcharge),
        profit_tax=_text(result.profit_tax),
        salary_balance=_text(result.salary_balance),
        profit_balance=_text(result.profit_balance),
        non_atl_extra_withheld=_text(result.non_atl_extra_withheld),
        steps=[
            StepOut(description=s.description, rule_location=s.rule_location, result=str(s.result))
            for s in result.steps
        ],
        summary=summary,
        label=LABEL,
    )


@router.get("/{tax_year}")
async def read_tax(
    tax_year: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    summariser: Annotated[Summariser, Depends(get_summariser)],
) -> TaxOut:
    """The user's tax for the year, with every step; or why it can't be calculated."""
    try:
        rates = rates_for(tax_year)
    except KeyError as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rates for that tax year.") from missing
    result = calculate(await tax_inputs(db, user, tax_year), rates)
    # Optional and checked: no summary unless every number in it is in the breakdown.
    return tax_out(result, await verified_summary(result, summariser))
