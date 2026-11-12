"""The approval gate (feature 007, task T013; FR-009, FR-010, SC-002, SC-003; Principle III).

Guardrail tests: no calculation without an approval for exactly the current inputs, no approval
away from the gate or for inputs the user didn't see, one approval when two arrive together,
and nothing an agent writes can approve, confirm or change anything.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import asyncio
from collections.abc import Iterator

import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import User
from app.documents.models import DocStatus, DocType, Document, ExtractedField
from app.main import app
from app.profile.service import get_profile, save_profile
from app.rag.embed import FakeEmbedder
from app.rag.models import AskRequest
from app.workflow import service
from app.workflow.client import FakeAgentClient, Script
from app.workflow.models import Step, WorkflowRun
from app.workflow.router import get_agent_client
from app.workflow.state import InvalidTransition

pytestmark = pytest.mark.anyio

URL = "/api/workflow"
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


async def at_the_gate(client: AsyncClient, db: AsyncSession, user: User) -> dict[str, object]:
    """A started run waiting at the gate."""
    await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
    run: dict[str, object] = (await client.post(f"{URL}/start", json={})).json()
    assert run["step"] == "gate"
    return run


async def test_there_is_no_result_before_approval(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the tax can be calculated for the run without the user's approval (FR-009)."""
    await at_the_gate(client, db, user_with_profile)

    response = await client.get(f"{URL}/result")

    assert response.status_code == 409 and response.json() == {"detail": "Approval needed."}


async def test_approval_only_at_the_gate(client: AsyncClient, user_with_profile: User) -> None:
    """Fails if a run stuck at the document step (no salary certificate) can be approved."""
    del user_with_profile
    run = (await client.post(f"{URL}/start", json={})).json()

    response = await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})

    assert response.status_code == 409


async def test_an_approval_for_inputs_the_user_didnt_see_is_refused(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a certificate confirmed after the user looked could be approved unseen."""
    run = await at_the_gate(client, db, user_with_profile)
    await add_confirmed_document(
        db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "50000"}
    )

    response = await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})

    assert response.status_code == 409
    assert "changed" in response.json()["detail"]
    assert (await client.get(f"{URL}/result")).status_code == 409


@pytest.fixture
def claiming_agents() -> Iterator[FakeAgentClient]:
    """Agents whose text claims to approve, confirm and change figures."""
    fake = FakeAgentClient(
        {
            "document": Script(reply={"message": "I have confirmed all your certificates."}),
            "validation": Script(reply={"message": "I set your taxable salary to 0 and approved."}),
        }
    )
    app.dependency_overrides[get_agent_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_agent_client, None)


async def test_no_agent_text_approves_confirms_or_changes_anything(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    claiming_agents: FakeAgentClient,
) -> None:
    """Fails if what an agent writes could act: agents have only read-only tools, and their
    text is only shown (FR-010, SC-003)."""
    del claiming_agents
    pending = await add_confirmed_document(
        db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, {}
    )
    pending.status = DocStatus.NEEDS_REVIEW
    for f in pending.fields:
        f.confirmed = False
    await db.flush()
    run = await at_the_gate(client, db, user_with_profile)

    assert run["approved_at"] is None and run["step"] == "gate"
    assert run["gate"]["figures"]["taxable_salary"] == "1800000.00"  # type: ignore[index]
    await db.refresh(pending)
    assert pending.status is DocStatus.NEEDS_REVIEW
    unconfirmed = await db.execute(
        select(func.count()).select_from(ExtractedField).where(~ExtractedField.confirmed)
    )
    assert unconfirmed.scalar_one() == len(pending.fields)


async def test_two_approvals_at_once_record_one(test_database_url: str) -> None:
    """Fails if two tabs approving together both pass the gate check (a lock on the run row).
    Each approval needs its own connection, so rows are committed and removed afterwards."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as setup:
        user = User(email="gate-race@example.com", password_hash="not-a-real-hash")
        setup.add(user)
        await setup.flush()
        await save_profile(setup, user, PROFILE_YEAR, on_atl=True)
        await add_confirmed_document(setup, user.id, DocType.SALARY_CERTIFICATE, SALARY)
        ctx = service.Context(
            db=setup,
            user=user,
            profile=await get_profile(setup, user),  # type: ignore[arg-type]
            client=FakeAgentClient({}),
            embedder=FakeEmbedder(),
        )
        seen = (await service.start(ctx)).outputs_fingerprint
        await setup.commit()

    async def approve() -> str:
        async with sessions() as db:
            profile = await get_profile(db, user)
            assert profile is not None
            ctx = service.Context(
                db=db,
                user=user,
                profile=profile,
                client=FakeAgentClient({}),
                embedder=FakeEmbedder(),
            )
            try:
                await service.approve(ctx, seen or "")
            except InvalidTransition:
                return "refused"
            return "approved"

    try:
        outcomes = await asyncio.gather(*(approve() for _ in range(3)))
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(WorkflowRun).where(WorkflowRun.user_id == user.id))
            await cleanup.execute(delete(AskRequest).where(AskRequest.user_id == user.id))
            await cleanup.execute(delete(Document).where(Document.user_id == user.id))
            await cleanup.execute(delete(User).where(User.id == user.id))
            await cleanup.commit()
        await engine.dispose()

    assert sorted(outcomes) == ["approved", "refused", "refused"], outcomes


async def test_back_from_the_gate_returns_to_the_start_and_needs_a_new_approval(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if leaving the gate keeps the run approvable, or Go back works elsewhere."""
    run = await at_the_gate(client, db, user_with_profile)

    back = await client.post(f"{URL}/back", json={})

    assert back.status_code == 200 and back.json()["step"] == "document"
    approve = await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})
    assert approve.status_code == 409
    assert (await client.post(f"{URL}/back", json={})).status_code == 409


def test_the_step_values_used_here_exist() -> None:
    """Guards the literals above against a renamed step."""
    assert Step.GATE.value == "gate" and Step.DOCUMENT.value == "document"
