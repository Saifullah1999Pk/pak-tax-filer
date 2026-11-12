"""The guided run's API (feature 007, tasks T008, T014, T018; contracts/workflow-api.md).

The agents are faked: by default (no_real_ai) every agent fails, so steps show their plain
results; tests that want an agent's own text script it with their own FakeAgentClient.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import QUESTION, a_corpus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocType
from app.main import app
from app.rag.models import AskRequest
from app.workflow.client import FakeAgentClient, Script
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
    from app.profile.service import save_profile  # pylint: disable=import-outside-toplevel

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
