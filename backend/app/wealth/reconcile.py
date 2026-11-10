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
from app.wealth import breakdown as words
from app.wealth.breakdown import Step

RECONCILED = "reconciled"
INFLOWS_EXCEED_GROWTH = "inflows_exceed_growth"
GROWTH_EXCEEDS_INFLOWS = "growth_exceeds_inflows"


@dataclass(frozen=True)
class CertificateFigures:  # pylint: disable=too-many-instance-attributes
    """One confirmed certificate's figures (feature 003), unrounded; name = how it is shown."""

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
    # Summed bank profit exceeds 004's limit, compared UNROUNDED as the tax engine does, so the
    # two pages always agree (R6; backend review M1).
    profit_over_limit: bool
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
    message: str | None = None
    # The fixed checklist for a non-zero result (FR-007); empty when reconciled or not ready.
    where_to_look: tuple[str, ...] = ()
    steps: tuple[Step, ...] = field(default_factory=tuple)


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
    profit = _total(c.profit_amount for c in bank)
    return WealthInputs(
        entries=entries,
        has_salary_certificate=bool(salary),
        taxable_salary=rupees(_total(c.taxable_salary for c in salary)),
        gross_salary=rupees(_total(c.gross_salary for c in salary)),
        tax_deducted=rupees(_total(c.tax_deducted for c in salary)),
        bank_profit=rupees(profit),
        tax_withheld=rupees(_total(c.tax_withheld for c in bank)),
        profit_over_limit=profit > rates.profit_limit.value,
        gross_below_taxable=below,
    )


def _not_ready(inputs: WealthInputs) -> ReconciliationResult | None:
    """A reason and no figures, checked in this order (research R6, FR-011, task T021)."""
    reason = None
    if inputs.entries.previous_net_assets is None:
        reason = "needs_previous_net_assets"
    elif not inputs.has_salary_certificate:
        reason = "no_confirmed_salary_certificate"
    elif inputs.profit_over_limit:
        # Line 7033 assumes s.7B applies, which stops above the limit (004 provisional rule 1).
        reason = "profit_over_limit"
    elif inputs.gross_below_taxable is not None:
        # 7032 (gross - taxable, provisional rule 4) would be negative for that certificate.
        name = inputs.gross_below_taxable
        return ReconciliationResult(
            not_ready_reason="gross_below_taxable",
            certificate=name,
            message=words.gross_below_taxable_message(name),
        )
    if reason is None:
        return None
    return ReconciliationResult(not_ready_reason=reason, message=words.NOT_READY_MESSAGES[reason])


def reconcile(inputs: WealthInputs) -> ReconciliationResult:
    """The reconciliation of one statement (research R2)."""
    not_ready = _not_ready(inputs)
    if not_ready is not None:
        return not_ready
    entries = inputs.entries
    previous = entries.previous_net_assets
    assert previous is not None  # checked by _not_ready
    assets, liabilities = _total(entries.assets), _total(entries.liabilities)
    net_assets = assets - liabilities
    increase = net_assets - previous
    inflow_parts = [
        ("taxable salary (7031)", inputs.taxable_salary),
        (
            "exempt income (7032)",
            inputs.gross_salary - inputs.taxable_salary + entries.other_exempt_income,
        ),
        ("bank profit (7033)", inputs.bank_profit),
        ("foreign remittance (7035)", entries.foreign_remittance),
        ("inheritance (7036)", entries.inheritance),
        ("gifts received (7037)", entries.gifts_received),
        ("family contribution (7088)", entries.family_contribution),
    ]
    inflows = _total(amount for _, amount in inflow_parts)
    outflow_parts = [
        ("personal expenses (7089)", _total(entries.personal_expenses)),
        ("gifts given (7091)", entries.gifts_given),
        ("tax deducted and withheld at source", inputs.tax_deducted + inputs.tax_withheld),
    ]
    outflows = _total(amount for _, amount in outflow_parts)
    unreconciled = inflows - outflows - increase
    if unreconciled == 0:
        direction = RECONCILED
    elif unreconciled > 0:
        direction = INFLOWS_EXCEED_GROWTH
    else:
        direction = GROWTH_EXCEEDS_INFLOWS
    steps = (
        words.total_step("Total assets", "7019", len(entries.assets), assets),
        words.total_step("Total liabilities", "7029", len(entries.liabilities), liabilities),
        words.net_assets_step(assets, liabilities, net_assets),
        words.increase_step(net_assets, previous, increase),
        words.inflows_step(inflow_parts, inflows),
        words.outflows_step(outflow_parts, outflows),
        words.unreconciled_step(inflows, outflows, increase, unreconciled),
    )
    return ReconciliationResult(
        net_assets=net_assets,
        increase=increase,
        inflows=inflows,
        outflows=outflows,
        unreconciled=unreconciled,
        direction=direction,
        message=words.gap_message(direction, unreconciled),
        where_to_look=words.WHERE_TO_LOOK.get(direction, ()),
        steps=steps,
    )
