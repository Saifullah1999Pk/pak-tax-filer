"""The TY2026 tax calculation (feature 004, task T010; research R1, R3).

A pure function: the same inputs always give the same result (constitution Principle I). No
database, network, clock or AI is imported here; a test enforces that. All amounts are exact
Decimals; only the final amounts (salary tax, surcharge, profit tax and each balance) are rounded,
to the nearest rupee with 50 paisa or more going up (section 219).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.tax.rates.model import Band, TaxYearRates


@dataclass(frozen=True)
class TaxInputs:  # pylint: disable=too-many-instance-attributes  # one field per input
    """What the calculation needs: confirmed certificates summed per type, and ATL status."""

    tax_year: str
    # From the taxpayer profile; None when the user has no profile yet.
    atl: bool | None
    taxable_salary: Decimal
    tax_deducted: Decimal
    gross_profit: Decimal
    tax_withheld: Decimal
    has_salary_certificate: bool


@dataclass(frozen=True)
class Step:
    """One line of the breakdown: what was done, the rule it follows, and its result."""

    description: str
    rule_location: str
    result: Decimal


@dataclass(frozen=True)
class TaxResult:  # pylint: disable=too-many-instance-attributes  # one field per figure
    """The calculation's figures, or why it was refused (then every figure is None)."""

    tax_year: str
    blocked_reason: str | None = None
    salary_tax: Decimal | None = None
    surcharge: Decimal | None = None
    profit_tax: Decimal | None = None
    # Positive: payable. Negative: over-deducted / over-withheld. Never added together (FR-005).
    salary_balance: Decimal | None = None
    profit_balance: Decimal | None = None
    # Non-ATL only: withholding above the profit tax, "to be confirmed", never a refund.
    non_atl_extra_withheld: Decimal | None = None
    steps: tuple[Step, ...] = field(default_factory=tuple)


def rupees(amount: Decimal) -> Decimal:
    """Round to the nearest rupee, 50 paisa or more up (section 219; never banker's rounding)."""
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def salary_band(rates: TaxYearRates, taxable_salary: Decimal) -> Band:
    """The row of the salaried table for this income ("does not exceed" the upper limit)."""
    for band in rates.salary_bands:
        if band.upper is None or taxable_salary <= band.upper:
            return band
    raise ValueError("The salary bands don't cover this income.")


def calculate(inputs: TaxInputs, rates: TaxYearRates) -> TaxResult:
    """Salary tax, surcharge, profit tax and the two balances, for one taxpayer and tax year."""
    band = salary_band(rates, inputs.taxable_salary)
    salary_tax = band.fixed + band.rate * (inputs.taxable_salary - band.lower)

    income = inputs.taxable_salary + inputs.gross_profit
    surcharge = Decimal(0)
    if income > rates.surcharge_threshold.value:
        surcharge = rates.surcharge_rate.value * salary_tax

    profit_tax = rates.profit_rate.value * inputs.gross_profit
    salary_balance = salary_tax + surcharge - inputs.tax_deducted

    extra: Decimal | None = None
    credited = inputs.tax_withheld
    if inputs.atl is False:
        # Provisional rule 2: only withholding up to the profit tax counts against it.
        credited = min(inputs.tax_withheld, profit_tax)
        extra = rupees(inputs.tax_withheld - credited)
    profit_balance = profit_tax - credited

    return TaxResult(
        tax_year=inputs.tax_year,
        salary_tax=rupees(salary_tax),
        surcharge=rupees(surcharge),
        profit_tax=rupees(profit_tax),
        salary_balance=rupees(salary_balance),
        profit_balance=rupees(profit_balance),
        non_atl_extra_withheld=extra,
    )
