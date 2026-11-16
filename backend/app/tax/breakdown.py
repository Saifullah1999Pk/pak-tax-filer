"""The breakdown's wording (feature 004, task T017; research R7, FR-010).

Fixed templates filled with the calculation's own numbers, each step citing its rule. Amounts read
"Rs 1,800,000" (paisa shown only when there are some), rates "11%". Plain code: no AI writes or
checks any of this (constitution Principle I).
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from app.tax.rates.model import Band, Source

if TYPE_CHECKING:  # the engine imports this module, so only for the type hint
    from app.tax.engine import TaxResult


def money(amount: Decimal) -> str:
    """'Rs 1,800,000', 'Rs 2,681,000.35' when there are paisa (half up), '-Rs 4,000'."""
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount == amount.to_integral_value():
        return f"{sign}Rs {amount:,.0f}"
    return f"{sign}Rs {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def percent(rate: Decimal) -> str:
    """'11%' for 0.11."""
    return f"{(rate * 100).normalize():f}%"


def where(source: Source) -> str:
    """The rule's full location, for the step's citation."""
    return f"{source.document}, {source.location}"


def equals(exact: Decimal, rounded: Decimal) -> str:
    """'= Rs 72,000', or '= Rs 0.50, rounded to Rs 1 (section 219)' when rounding changed it."""
    if exact == rounded:
        return f"= {money(rounded)}"
    return f"= {money(exact)}, rounded to {money(rounded)} (section 219)"


def balance_words(rounded: Decimal, overpaid: str) -> str:
    """'Rs 12,000 payable', 'Rs 4,000 over-deducted' or 'nothing to pay'."""
    if rounded > 0:
        return f"{money(rounded)} payable"
    if rounded < 0:
        return f"{money(-rounded)} {overpaid}"
    return "nothing to pay"


def salary_tax(
    band: Band,
    taxable: Decimal,
    exact: Decimal,
    rounded: Decimal,
    lead: str = "Salary tax: taxable salary",
) -> str:
    """'Salary tax: taxable salary Rs 1,800,000 falls in the Rs 1,200,001 to Rs 2,200,000 band:
    Rs 6,000 + 11% of Rs 600,000 = Rs 72,000'. Feature 010's calculator passes its own `lead`
    ("Tax on taxable income"), since its income isn't only salary."""
    if band.upper is None:
        position = f"exceeds {money(band.lower)}"
    elif band.lower == 0:
        position = f"does not exceed {money(band.upper)}"
    else:
        position = f"falls in the {money(band.lower + 1)} to {money(band.upper)} band"
    over = taxable - band.lower
    if band.rate == 0 and band.fixed == 0:
        formula = "no tax"
    elif band.fixed == 0:
        formula = f"{percent(band.rate)} of {money(over)} above {money(band.lower)}"
    else:
        formula = (
            f"{money(band.fixed)} + {percent(band.rate)} of {money(over)} above {money(band.lower)}"
        )
    return f"{lead} {money(taxable)} {position}: {formula} {equals(exact, rounded)}"


def _left(balance: Decimal, overpaid: str, side: str) -> str:
    """How a summary sentence ends: still payable, paid too much, or nothing more on this side
    (named, so it never reads as an answer for both)."""
    if balance > 0:
        return f"{money(balance)} is still payable."
    if balance < 0:
        return f"{money(-balance)} was {overpaid} too much."
    return f"nothing more is payable on {side}."


def tax_summary(result: "TaxResult") -> str | None:
    """The result in two or three plain sentences, from its own amounts only; never the two
    sides added together (design 2026-11-16-plain-summary). None when refused: its message
    already says why."""
    if result.blocked_reason is not None:
        return None
    zero = Decimal(0)
    surcharge = result.surcharge or zero
    salary = f"Your salary tax for {result.tax_year} is {money(result.salary_tax or zero)}"
    if surcharge > 0:
        salary += f" plus a surcharge of {money(surcharge)}"
    salary += f". Your employers deducted {money(result.salary_credit or zero)}, so " + _left(
        result.salary_balance or zero, "deducted", "your salary"
    )
    profit_tax, profit_credit = result.profit_tax or zero, result.profit_credit or zero
    if not profit_tax and not profit_credit:
        return salary
    # Off the ATL only withholding up to the tax counts, so the credit may be less than banks
    # withheld: say it is the part counted (the extra stays in the page's own notice).
    if result.non_atl_extra_withheld is not None:
        credit = f"counting {money(profit_credit)} of what banks withheld, "
    else:
        credit = f"after {money(profit_credit)} withheld by banks, "
    return f"{salary} Tax on your bank profit is {money(profit_tax)}; {credit}" + _left(
        result.profit_balance or zero, "withheld", "your bank profit"
    )
