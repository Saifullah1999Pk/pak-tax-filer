"""The reconciliation's wording (feature 005, task T015; research R2, R9; FR-007, FR-009).

Fixed templates filled with the calculation's own numbers, each step naming its TY2026 form line
(SRO 1495(I)/2026). The "where to look" lists are fixed, written here, never by an AI, and never
contain an amount, so nothing nudges the user towards numbers that merely force a zero.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.tax.breakdown import money


@dataclass(frozen=True)
class Step:
    """One breakdown step: what was done, its form line, and its result."""

    description: str
    form_line: str
    result: Decimal


RECONCILED_MESSAGE = "Your wealth statement reconciles."

WHERE_TO_LOOK: dict[str, tuple[str, ...]] = {
    # Assets grew more than inflows explain: something that came in is missing.
    "growth_exceeds_inflows": (
        "A gift you received",
        "An inheritance",
        "Money sent to you from abroad (foreign remittance)",
        "Family members' contribution to household expenses",
        "Other exempt income",
    ),
    # Inflows exceed the growth: something you own or spent is missing.
    "inflows_exceed_growth": (
        "A bank account or savings not listed",
        "A vehicle, jewellery or other asset not listed",
        "A personal expense category left empty",
        "A gift you gave",
    ),
}

NOT_READY_MESSAGES = {
    "needs_previous_net_assets": (
        "Enter your net assets as on 30 June 2025, from last year's wealth statement."
    ),
    "no_confirmed_salary_certificate": "Upload and confirm your salary certificate first.",
    "profit_over_limit": "Bank profit over Rs 5,000,000 isn't supported yet.",
}


def gross_below_taxable_message(certificate: str) -> str:
    """The not-ready message naming the certificate (FR-011)."""
    return (
        f"{certificate}: the gross salary is lower than the taxable salary. Check the "
        "certificate; if it's wrong, delete it and upload it again."
    )


def gap_message(direction: str, unreconciled: Decimal) -> str:
    """The result in words, the amount without its sign (FR-007)."""
    amount = money(abs(unreconciled))
    if direction == "inflows_exceed_growth":
        return (
            f"Your inflows exceed the growth in your assets by {amount}: an expense or asset "
            "may be missing."
        )
    if direction == "growth_exceeds_inflows":
        return (
            f"Your assets grew {amount} more than your inflows explain: an inflow may be missing."
        )
    return RECONCILED_MESSAGE


def _operand(amount: Decimal) -> str:
    """A figure inside a sum: negatives in brackets, so "Rs 1 - (-Rs 2)" reads plainly."""
    return money(amount) if amount >= 0 else f"({money(amount)})"


def _sum(parts: list[tuple[str, Decimal]], total: Decimal) -> str:
    named = " + ".join(f"{name} {money(amount)}" for name, amount in parts if amount)
    return f"{named or 'nothing'} = {money(total)}"


def total_step(label: str, form_line: str, count: int, total: Decimal) -> Step:
    """Total assets (7019) or liabilities (7029)."""
    items = "item" if count == 1 else "items"
    return Step(f"{label} ({count} {items}) = {money(total)}", form_line, total)


def net_assets_step(assets: Decimal, liabilities: Decimal, net: Decimal) -> Step:
    """Net assets this year (703001)."""
    return Step(
        f"Net assets this year: {money(assets)} - {money(liabilities)} = {money(net)}",
        "703001",
        net,
    )


def increase_step(net: Decimal, previous: Decimal, increase: Decimal) -> Step:
    """The increase or decrease since 30 June 2025 (703003)."""
    word = "Decrease" if increase < 0 else "Increase"
    return Step(
        f"{word} in net assets: {_operand(net)} - {_operand(previous)} (net assets on 30 June "
        f"2025) = {money(increase)}",
        "703003",
        increase,
    )


def inflows_step(parts: list[tuple[str, Decimal]], total: Decimal) -> Step:
    """Inflows (7049), naming each line that has an amount."""
    return Step(f"Inflows: {_sum(parts, total)}", "7049", total)


def outflows_step(parts: list[tuple[str, Decimal]], total: Decimal) -> Step:
    """Outflows (7099), naming each part that has an amount."""
    return Step(f"Outflows: {_sum(parts, total)}", "7099", total)


def unreconciled_step(
    inflows: Decimal, outflows: Decimal, increase: Decimal, unreconciled: Decimal
) -> Step:
    """The unreconciled amount (703000): inflows - outflows - increase."""
    return Step(
        f"Unreconciled amount: {money(inflows)} - {money(outflows)} - {_operand(increase)} = "
        f"{money(unreconciled)}",
        "703000",
        unreconciled,
    )
