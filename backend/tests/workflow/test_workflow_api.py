"""The guided run's API (feature 007, tasks T008, T014, T018; contracts/workflow-api.md).

The agents are faked: by default (no_real_ai) every agent fails, so steps show their plain
results; tests that want an agent's own text script it with their own FakeAgentClient.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from datetime import UTC, datetime, timedelta

import pytest
import yaml
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import QUESTION, a_corpus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocType, Document
from app.main import app
from app.profile.service import save_profile
from app.rag.models import AskRequest
from app.workflow.client import FakeAgentClient, Script
from app.workflow.models import WorkflowRun
from app.workflow.router import get_agent_client

pytestmark = pytest.mark.anyio

URL = "/api/workflow"
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
RESEARCH = Script(
    calls=[("search_tax_documents", {"query": QUESTION})],
    reply={"note": "Your employer deducts tax from your salary (P1).", "citations": ["P1"]},
)


@pytest.fixture
def agents() -> Iterator[FakeAgentClient]:
    """The app's agent client, replaced by one whose research agent answers (the others fail)."""
    fake = FakeAgentClient({"research": RESEARCH})
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


async def questions_recorded(db: AsyncSession) -> int:
    """How many questions are counted against 006's limits."""
    return (await db.execute(select(func.count()).select_from(AskRequest))).scalar_one()


# ---- User Story 1 (T008) ----


async def test_logged_out_is_refused(client: AsyncClient) -> None:
    """Fails if anyone not logged in can see or start a run."""
    assert (await client.get(URL)).status_code == 401
    assert (await client.post(f"{URL}/start", json={})).status_code == 401


async def test_without_a_profile_it_asks_for_one(client: AsyncClient, logged_in_user: User) -> None:
    """Fails if a user without a profile gets anything but 002's 409 (the page sends them on)."""
    del logged_in_user
    response = await client.post(f"{URL}/start", json={})

    assert response.status_code == 409
    assert response.json() == {"detail": "Set up your profile first."}


async def test_before_starting_there_is_no_run(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if a run appears before the user starts one."""
    del user_with_profile
    assert (await client.get(URL)).status_code == 404


async def test_without_a_salary_certificate_the_run_stops_at_the_document_step(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if a run without a confirmed salary certificate goes past step 1 (FR-003)."""
    del user_with_profile

    response = await client.post(f"{URL}/start", json={})

    assert response.status_code == 200
    run = response.json()
    assert run["step"] == "document" and run["document"]["missing"] == ["salary_certificate"]
    assert run["gate"] is None and run["approved_at"] is None


async def test_with_a_salary_certificate_the_run_reaches_the_gate(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, agents: FakeAgentClient
) -> None:
    """Fails if the gate lacks what the user approves: the confirmed figures, the profile's tax
    year and ATL status, the validation result and the cited passages (FR-008)."""
    del agents
    await a_corpus(db)
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)

    run = (await client.post(f"{URL}/start", json={})).json()

    assert run["step"] == "gate" and run["tax_year"] == PROFILE_YEAR
    assert run["gate"]["on_atl"] is True
    assert run["gate"]["figures"]["taxable_salary"] == "1800000.00"
    assert run["gate"]["figures"]["tax_deducted"] == "75000.00"
    assert run["validation"]["issues"] == []
    assert run["research"]["fallback"] is False
    assert run["research"]["passages"][0]["location"] == "§149(1)"
    assert run["document"]["fallback"] is True  # the document agent wasn't scripted
    assert len(run["fingerprint"]) == 64
    assert (await client.get(URL)).json() == run  # resumes where it is (FR-002)


async def test_another_users_run_is_never_returned(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if one user could see another's run (FR-015)."""
    del user_with_profile
    await client.post(f"{URL}/start", json={})
    other = await make_user(db, "other@example.com")

    await save_profile(db, other, PROFILE_YEAR, on_atl=False)
    await client.post("/api/auth/logout", json={})
    login = await client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "s3cret-pass"}
    )
    assert login.status_code == 200

    assert (await client.get(URL)).status_code == 404


async def test_a_run_counts_as_one_question(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the agents' calls escape the tax assistant's limits, or count three times
    (FR-018, research R9)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)

    await client.post(f"{URL}/start", json={})

    assert await questions_recorded(db) == 1


async def test_past_the_hourly_limit_the_run_still_reaches_the_gate_without_the_ai(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, agents: FakeAgentClient
) -> None:
    """Fails if a user at the limit is blocked, or any agent is still called (FR-018)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    now = datetime.now(UTC)
    db.add_all(
        AskRequest(user_id=user_with_profile.id, created_at=now - timedelta(minutes=i))
        for i in range(30)
    )
    await db.flush()

    run = (await client.post(f"{URL}/start", json={})).json()

    assert run["step"] == "gate"
    assert all(run[s]["fallback"] for s in ("document", "validation", "research"))
    assert not agents.calls
    assert await questions_recorded(db) == 30


# ---- User Story 2 (T014) ----

EXAMPLES = yaml.safe_load(
    (Path(__file__).parents[1] / "tax" / "worked_examples.yaml").read_text(encoding="utf-8")
)["examples"]
# A run needs a profile (so an ATL answer) and a confirmed salary certificate to reach the gate;
# the other examples' blocks are the document step's and the profile page's job.
GATED = [
    e for e in EXAMPLES if e["inputs"]["atl"] is not None and e["inputs"]["salary_certificates"]
]


@pytest.mark.parametrize("example", GATED, ids=[e["id"] for e in GATED])
async def test_after_approval_the_result_is_the_tax_pages(
    client: AsyncClient, db: AsyncSession, logged_in_user: User, example: dict[str, Any]
) -> None:
    """Fails if the run's result differs from GET /api/tax for a signed-off worked example,
    blocked ones included: one engine, one answer (SC-004, FR-011)."""
    inputs = example["inputs"]
    await save_profile(db, logged_in_user, PROFILE_YEAR, on_atl=inputs["atl"])
    for certificate in inputs["salary_certificates"]:
        await add_confirmed_document(db, logged_in_user.id, DocType.SALARY_CERTIFICATE, certificate)
    for certificate in inputs["bank_certificates"]:
        await add_confirmed_document(
            db, logged_in_user.id, DocType.BANK_PROFIT_CERTIFICATE, certificate
        )
    run = (await client.post(f"{URL}/start", json={})).json()

    approved = await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})
    result = (await client.get(f"{URL}/result")).json()

    assert approved.status_code == 200 and approved.json()["step"] == "result"
    assert approved.json()["approved_at"] is not None
    passages = result.pop("passages")
    assert result == (await client.get(f"/api/tax/{PROFILE_YEAR}")).json()
    assert passages == run["research"]["passages"]


async def test_marking_done_records_the_date(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a run can be marked done before its result, or done isn't recorded (FR-014)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    run = (await client.post(f"{URL}/start", json={})).json()
    assert (await client.post(f"{URL}/done", json={})).status_code == 409  # still at the gate
    await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})

    done = (await client.post(f"{URL}/done", json={})).json()

    assert done["step"] == "done" and done["done_at"] is not None
    assert (await client.get(f"{URL}/result")).status_code == 200  # still readable when done


# ---- User Story 3 (T018) ----


async def approved_run(client: AsyncClient, db: AsyncSession, user: User) -> dict[str, Any]:
    """A run approved at the gate, with its result available."""
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    run = (await client.post(f"{URL}/start", json={})).json()
    approved: dict[str, Any] = (
        await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})
    ).json()
    assert (await client.get(f"{URL}/result")).status_code == 200
    return approved


async def test_a_new_certificate_after_approval_returns_to_the_gate(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a certificate confirmed after approval leaves the old approval (or result)
    standing, or the run doesn't say why it's back (FR-013, SC-006)."""
    before = await approved_run(client, db, user_with_profile)
    await add_confirmed_document(
        db,
        user_with_profile.id,
        DocType.BANK_PROFIT_CERTIFICATE,
        {"profit_amount": "50000", "tax_withheld": "10000"},
    )

    run = (await client.get(URL)).json()

    assert run["step"] == "gate" and run["approved_at"] is None
    assert run["inputs_changed"] is True
    assert run["fingerprint"] != before["fingerprint"]
    assert run["gate"]["figures"]["gross_profit"] == "50000.00"
    assert (await client.get(f"{URL}/result")).status_code == 409


async def test_deleting_the_salary_certificate_returns_to_the_document_step(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a run whose only salary certificate is gone stays approved."""
    await approved_run(client, db, user_with_profile)
    document = (
        await db.execute(select(Document).where(Document.user_id == user_with_profile.id))
    ).scalar_one()
    await db.delete(document)
    await db.flush()

    run = (await client.get(URL)).json()

    assert run["step"] == "document" and run["document"]["missing"] == ["salary_certificate"]
    assert run["approved_at"] is None


async def test_changing_the_profile_returns_to_the_gate(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a changed ATL answer keeps an approval given for the old one."""
    await approved_run(client, db, user_with_profile)
    await save_profile(db, user_with_profile, PROFILE_YEAR, on_atl=False)

    run = (await client.get(URL)).json()

    assert run["step"] == "gate" and run["gate"]["on_atl"] is False
    assert run["approved_at"] is None and run["inputs_changed"] is True


async def test_a_change_before_approval_re_runs_the_steps_and_counts_once(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the gate could show checks made for older inputs, or a re-run isn't counted
    (research R9), or a run never approved claims its inputs changed after approval."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.post(f"{URL}/start", json={})
    await add_confirmed_document(
        db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "50000"}
    )

    run = (await client.get(URL)).json()
    again = (await client.get(URL)).json()

    assert run["gate"]["figures"]["gross_profit"] == "50000.00"
    assert run["inputs_changed"] is False
    assert await questions_recorded(db) == 2  # the start, and one re-run (not two)
    assert again == run


async def test_starting_a_done_run_resets_it(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if starting again leaves the old approval, or makes a second run (FR-002)."""
    await approved_run(client, db, user_with_profile)
    await client.post(f"{URL}/done", json={})

    run = (await client.post(f"{URL}/start", json={})).json()

    assert run["step"] == "gate" and run["approved_at"] is None and run["done_at"] is None
    assert run["inputs_changed"] is False
    count = (await db.execute(select(func.count()).select_from(WorkflowRun))).scalar_one()
    assert count == 1
