"""GET /api/tax/{tax_year} (feature 004, task T012; contracts/tax-api.md, R6; AI summary removed
2026-11-16),
and POST /api/tax/calculator (feature 010, task T012; its contracts/calculator-api.md).

GET because nothing changes on the server: the result is recalculated from the user's confirmed
certificates and profile on every request. The calculator is a POST only because its amounts
are a body (kept out of URLs and logs); it stores nothing either. Money is returned as strings
(docs/api-conventions.md).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.tax.breakdown import tax_summary
from app.tax.calculator import calculate_simple
from app.tax.calculator_schemas import CalculatorIn, CalculatorOut, calculator_out
from app.tax.engine import TaxResult, calculate
from app.tax.rates import rates_for
from app.tax.service import BLOCKED_MESSAGES, tax_inputs

router = APIRouter(prefix="/api/tax", tags=["tax"])

# On every result (constitution Principle IV, FR-014).
LABEL = "Not yet reviewed by a tax practitioner. Not tax advice."


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
    salary_credit: str | None
    profit_credit: str | None
    steps: list[StepOut]
    # Plain sentences written by code from the figures above; null when blocked (2026-11-16).
    summary: str | None
    label: str


def _text(amount: Decimal | None) -> str | None:
    return None if amount is None else str(amount)


def tax_out(result: TaxResult) -> TaxOut:
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
        salary_credit=_text(result.salary_credit),
        profit_credit=_text(result.profit_credit),
        steps=[
            StepOut(description=s.description, rule_location=s.rule_location, result=str(s.result))
            for s in result.steps
        ],
        summary=tax_summary(result),
        label=LABEL,
    )


async def _result(db: AsyncSession, user: User, tax_year: str) -> TaxResult:
    """The user's result for a tax year the app has FBR rates for (else 404)."""
    try:
        rates = rates_for(tax_year)
    except KeyError as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rates for that tax year.") from missing
    return calculate(await tax_inputs(db, user, tax_year), rates)


@router.get("/{tax_year}")
async def read_tax(
    tax_year: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaxOut:
    """The user's tax for the year, with every step; or why it can't be calculated."""
    return tax_out(await _result(db, user, tax_year))


@router.post("/calculator", dependencies=[Depends(require_json)])
async def calculate_tax(
    body: CalculatorIn,
    profile: Annotated[TaxpayerProfile, Depends(require_profile)],
) -> CalculatorOut:
    """The tax on typed amounts for the profile's tax year and ATL status, every line
    explained; or why the calculator can't answer. Nothing is stored (feature 010, FR-003)."""
    try:
        rates = rates_for(profile.tax_year)
    except KeyError as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No rates for that tax year.") from missing
    result = calculate_simple(body.inputs(profile.tax_year, profile.on_atl), rates)
    return calculator_out(result, LABEL, profile.on_atl)
