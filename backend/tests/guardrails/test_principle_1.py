"""Guardrail: the AI never changes a figure (constitution Principle I; feature 008, task T011,
research R5).

The tax, wealth and guided-filing results must equal the hand-worked, signed-off examples to the
rupee. Since 2026-11-16 no AI rewords these results at all (the lead: AI only where reasoning is
needed); the last test fails if an AI summary comes back.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Any

import pytest
import yaml
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import a_corpus
from sqlalchemy.ext.asyncio import AsyncSession
from wealth_statement import STATEMENT

from app.auth.models import User
from app.documents.models import DocType

pytestmark = pytest.mark.anyio

TESTS = Path(__file__).resolve().parent.parent
TAX_FIGURES = (
    "salary_tax",
    "surcharge",
    "profit_tax",
    "salary_balance",
    "profit_balance",
    "non_atl_extra_withheld",
)
WEALTH_FIGURES = ("net_assets", "increase", "inflows", "outflows", "unreconciled", "direction")


def example(path: str, example_id: str) -> dict[str, Any]:
    """A signed-off worked example (004's or 005's)."""
    examples = yaml.safe_load((TESTS / path).read_text(encoding="utf-8"))["examples"]
    found: dict[str, Any] = next(e for e in examples if e["id"] == example_id)
    assert found["signed_off_by"] and found["signed_off_date"], "only signed-off examples"
    return found


TAX = example("tax/worked_examples.yaml", "two-salary-and-two-bank-certificates")
WEALTH = example("wealth/worked_examples.yaml", "reconciled")


async def tax_certificates(db: AsyncSession, user: User) -> None:
    """The tax example's certificates, confirmed."""
    for salary in TAX["inputs"]["salary_certificates"]:
        await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, salary)
    for bank in TAX["inputs"]["bank_certificates"]:
        await add_confirmed_document(db, user.id, DocType.BANK_PROFIT_CERTIFICATE, bank)


def tax_figures(result: dict[str, Any]) -> dict[str, Any]:
    """The result's figures, as the example writes them."""
    return {name: result[name] for name in TAX_FIGURES}


async def test_the_tax_result_is_the_worked_example(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a tax figure differs from the signed-off worked example."""
    assert TAX["inputs"]["atl"] is True  # the profile fixture is on the ATL
    await tax_certificates(db, user_with_profile)

    result = (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()

    assert result["blocked_reason"] is None
    assert tax_figures(result) == {name: TAX["expected"][name] for name in TAX_FIGURES}


async def test_the_wealth_result_is_the_worked_example(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a wealth figure differs from the signed-off worked example."""
    for salary in WEALTH["inputs"]["salary_certificates"]:
        figures = {k: v for k, v in salary.items() if k != "file"}
        await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, figures)
    for bank in WEALTH["inputs"]["bank_certificates"]:
        figures = {k: v for k, v in bank.items() if k != "file"}
        await add_confirmed_document(
            db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, figures
        )
    await client.put(f"/api/wealth/{PROFILE_YEAR}", json=STATEMENT)

    result = (await client.get(f"/api/wealth/{PROFILE_YEAR}")).json()["result"]

    assert result["not_ready_reason"] is None
    assert {name: result[name] for name in WEALTH_FIGURES} == {
        name: WEALTH["expected"][name] for name in WEALTH_FIGURES
    }


async def test_the_guided_result_is_the_worked_example(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the guided result differs from the worked example (its steps are plain code
    since 2026-11-16)."""
    await a_corpus(db)
    await tax_certificates(db, user_with_profile)

    run = (await client.post("/api/workflow/start", json={})).json()
    await client.post("/api/workflow/approve", json={"fingerprint": run["fingerprint"]})
    result = (await client.get("/api/workflow/result")).json()

    assert tax_figures(result) == {name: TAX["expected"][name] for name in TAX_FIGURES}


async def test_no_ai_rewords_a_computed_result(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if an AI summary of the tax or wealth result comes back (amended 2026-11-16, the
    lead: no AI where no reasoning is needed; the step-by-step breakdowns explain the figures)."""
    await tax_certificates(db, user_with_profile)

    for page in ("tax", "wealth"):
        assert (await client.get(f"/api/{page}/{PROFILE_YEAR}/summary")).status_code == 404, page
    assert "summary" not in (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()
