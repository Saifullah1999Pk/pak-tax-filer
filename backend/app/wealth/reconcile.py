"""The wealth reconciliation: pure, deterministic code (feature 005, task T008; research R1, R2).

No database, network, clock or AI (constitution, Principle I): the same inputs always give the
same result. Signed-off worked examples are its tests (tests/wealth/worked_examples.yaml).

Formula (FBR IRIS FAQ; form lines from SRO 1495(I)/2026 pp. 38, 40):
    net assets (703001)   = total assets (7019) - total liabilities (7029)
    increase (703003)     = net assets - previous net assets (703002)
    inflows (7049)        = 7031 + 7032 + 7033 + 7035 + 7036 + 7037 + 7088
    outflows (7099)       = personal expenses (7089) + gifts given (7091) + tax at source
    unreconciled (703000) = inflows - outflows - increase      (zero means reconciled)
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.tax.engine import rupees
from app.tax.rates.model import TaxYearRates

RECONCILED = "reconciled"
INFLOWS_EXCEED_GROWTH = "inflows_exceed_growth"
GROWTH_EXCEEDS_INFLOWS = "growth_exceeds_inflows"


@dataclass(frozen=True)
class CertificateFigures:  # pylint: disable=too-many-instance-attributes
    """One confirmed certificate's figures (feature 003), unrounded; name = its file name."""

    name: str
    gross_salary: Decimal = Decimal(0)
    taxable_salary: Decimal = Decimal(0)
    tax_deducted: Decimal = Decimal(0)
    profit_amount: Decimal = Decimal(0)
    tax_withheld: Decimal = Decimal(0)


@dataclass(frozen=True)
class UserEntries:  # pylint: disable=too-many-instance-attributes
    """What the user typed, in whole rupees (FR-002, FR-003)."""

    previous_net_assets: Decimal | None
    assets: tuple[Decimal, ...] = ()
    liabilities: tuple[Decimal, ...] = ()
    other_exempt_income: Decimal = Decimal(0)
    foreign_remittance: Decimal = Decimal(0)
    inheritance: Decimal = Decimal(0)
    gifts_received: Decimal = Decimal(0)
    family_contribution: Decimal = Decimal(0)
    personal_expenses: tuple[Decimal, ...] = ()
    gifts_given: Decimal = Decimal(0)


@dataclass(frozen=True)
class WealthInputs:  # pylint: disable=too-many-instance-attributes
    """Everything the reconciliation needs, certificate sums already rounded (research R5)."""

    entries: UserEntries
    has_salary_certificate: bool
    taxable_salary: Decimal
    gross_salary: Decimal
    tax_deducted: Decimal
    bank_profit: Decimal
    tax_withheld: Decimal
    profit_limit: Decimal
    # The first salary certificate whose gross is below its taxable salary, if any (R6).
    gross_below_taxable: str | None = None


@dataclass(frozen=True)
class ReconciliationResult:  # pylint: disable=too-many-instance-attributes
    """The result; never stored (FR-012). Figures are None when not ready."""

    not_ready_reason: str | None = None
    certificate: str | None = None
    net_assets: Decimal | None = None
    increase: Decimal | None = None
    inflows: Decimal | None = None
    outflows: Decimal | None = None
    unreconciled: Decimal | None = None
    direction: str | None = None
    steps: tuple[object, ...] = field(default_factory=tuple)


def _total(amounts: Iterable[Decimal]) -> Decimal:
    return sum(amounts, Decimal(0))


def build_inputs(
    entries: UserEntries,
    salary: Sequence[CertificateFigures],
    bank: Sequence[CertificateFigures],
    rates: TaxYearRates,
) -> WealthInputs:
    """Sum each figure across certificates of its type, then round each sum (s.219, R5)."""
    below = next((c.name for c in salary if c.gross_salary < c.taxable_salary), None)
    return WealthInputs(
        entries=entries,
        has_salary_certificate=bool(salary),
        taxable_salary=rupees(_total(c.taxable_salary for c in salary)),
        gross_salary=rupees(_total(c.gross_salary for c in salary)),
        tax_deducted=rupees(_total(c.tax_deducted for c in salary)),
        bank_profit=rupees(_total(c.profit_amount for c in bank)),
        tax_withheld=rupees(_total(c.tax_withheld for c in bank)),
        profit_limit=rates.profit_limit.value,
        gross_below_taxable=below,
    )


def _not_ready(inputs: WealthInputs) -> ReconciliationResult | None:
    """A reason and no figures, checked in this order (research R6, FR-011, task T021)."""
    if inputs.entries.previous_net_assets is None:
        return ReconciliationResult(not_ready_reason="needs_previous_net_assets")
    if not inputs.has_salary_certificate:
        return ReconciliationResult(not_ready_reason="no_confirmed_salary_certificate")
    if inputs.bank_profit > inputs.profit_limit:
        # Line 7033 assumes s.7B applies, which stops above the limit (004 provisional rule 1).
        return ReconciliationResult(not_ready_reason="profit_over_limit")
    if inputs.gross_below_taxable is not None:
        # 7032 (gross - taxable, provisional rule 4) would be negative for that certificate.
        return ReconciliationResult(
            not_ready_reason="gross_below_taxable", certificate=inputs.gross_below_taxable
        )
    return None


def reconcile(inputs: WealthInputs) -> ReconciliationResult:
    """The reconciliation of one statement (research R2)."""
    not_ready = _not_ready(inputs)
    if not_ready is not None:
        return not_ready
    entries = inputs.entries
    assert entries.previous_net_assets is not None  # checked by _not_ready
    net_assets = _total(entries.assets) - _total(entries.liabilities)
    increase = net_assets - entries.previous_net_assets
    exempt = inputs.gross_salary - inputs.taxable_salary + entries.other_exempt_income
    inflows = (
        inputs.taxable_salary
        + exempt
        + inputs.bank_profit
        + entries.foreign_remittance
        + entries.inheritance
        + entries.gifts_received
        + entries.family_contribution
    )
    tax_at_source = inputs.tax_deducted + inputs.tax_withheld
    outflows = _total(entries.personal_expenses) + entries.gifts_given + tax_at_source
    unreconciled = inflows - outflows - increase
    if unreconciled == 0:
        direction = RECONCILED
    elif unreconciled > 0:
        direction = INFLOWS_EXCEED_GROWTH
    else:
        direction = GROWTH_EXCEEDS_INFLOWS
    return ReconciliationResult(
        net_assets=net_assets,
        increase=increase,
        inflows=inflows,
        outflows=outflows,
        unreconciled=unreconciled,
        direction=direction,
    )
