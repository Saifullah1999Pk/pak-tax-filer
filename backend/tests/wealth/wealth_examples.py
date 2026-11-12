"""Shared helpers for the wealth tests: the signed-off worked examples, and running one through
build_inputs and reconcile exactly as the service does (feature 005)."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from app.tax.rates import rates_for
from app.wealth.reconcile import (
    CertificateFigures,
    ReconciliationResult,
    UserEntries,
    build_inputs,
    reconcile,
)

EXAMPLES = yaml.safe_load(
    Path(__file__).with_name("worked_examples.yaml").read_text(encoding="utf-8")
)["examples"]
READY = [e for e in EXAMPLES if e["expected"]["not_ready_reason"] is None]


def run(example: dict[str, Any]) -> ReconciliationResult:
    """The example's inputs through build_inputs and reconcile."""
    i = example["inputs"]
    salary = [
        CertificateFigures(
            name=c["file"],
            gross_salary=Decimal(c["gross_salary"]),
            taxable_salary=Decimal(c["taxable_salary"]),
            tax_deducted=Decimal(c["tax_deducted"]),
        )
        for c in i["salary_certificates"]
    ]
    bank = [
        CertificateFigures(
            name=b["file"],
            profit_amount=Decimal(b["profit_amount"]),
            tax_withheld=Decimal(b["tax_withheld"]),
        )
        for b in i["bank_certificates"]
    ]

    def amount(name: str) -> Decimal:
        return Decimal(i.get(name, "0"))

    entries = UserEntries(
        previous_net_assets=(
            None if i["previous_net_assets"] is None else Decimal(i["previous_net_assets"])
        ),
        assets=tuple(Decimal(a["amount"]) for a in i["assets"]),
        liabilities=tuple(Decimal(liability["amount"]) for liability in i["liabilities"]),
        other_exempt_income=amount("other_exempt_income"),
        foreign_remittance=amount("foreign_remittance"),
        inheritance=amount("inheritance"),
        gifts_received=amount("gifts_received"),
        family_contribution=amount("family_contribution"),
        personal_expenses=tuple(Decimal(v) for v in i["personal_expenses"].values()),
        gifts_given=amount("gifts_given"),
    )
    return reconcile(build_inputs(entries, salary, bank, rates_for("2025-26")))
