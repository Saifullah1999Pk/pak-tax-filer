"""The guided run's API (feature 007, tasks T008, T014, T018; contracts/workflow-api.md).

The steps are plain code (amended 2026-11-16: no AI), so nothing here is faked: the run is the
same in tests as live.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Any
from decimal import Decimal

import pytest
import yaml
from conftest import make_user
from document_helpers import PROFILE_YEAR, add_confirmed_document
from httpx2 import AsyncClient
from rag_helpers import a_corpus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.models import DocType, Document, ExtractedField, FieldName
from app.main import app
from app.profile.service import save_profile
from app.rag.models import AskRequest
from app.rag.router import get_embedder
from app.workflow import fingerprint as fingerprint_module
from app.workflow import service
from app.workflow.models import WorkflowRun

pytestmark = pytest.mark.anyio

URL = "/api/workflow"
SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}


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
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the gate lacks what the user approves: the confirmed figures, the profile's tax
    year and ATL status, the validation result and the cited passages (FR-008)."""
    await a_corpus(db)
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)

    run = (await client.post(f"{URL}/start", json={})).json()

    assert run["step"] == "gate" and run["tax_year"] == PROFILE_YEAR
    assert run["gate"]["on_atl"] is True
    assert run["gate"]["figures"]["taxable_salary"] == "1800000.00"
    assert run["gate"]["figures"]["tax_deducted"] == "75000.00"
    assert run["validation"]["issues"] == []
    assert [p["location"] for p in run["research"]["passages"]] == ["§12(1)", "§149(1)"]
    assert "fallback" not in run["research"]  # plain code is the result, not a fallback
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


async def _park(client: AsyncClient, db: AsyncSession, user: User, where: str) -> None:
    """A run left at `where`: document (no salary certificate), gate, result or done."""
    if where == "document":
        await client.post(f"{URL}/start", json={})
        return
    if where == "gate":
        await add_confirmed_document(db, user.id, DocType.SALARY_CERTIFICATE, SALARY)
        await client.post(f"{URL}/start", json={})
        return
    await approved_run(client, db, user)
    if where == "done":
        assert (await client.post(f"{URL}/done", json={})).status_code == 200


@pytest.mark.parametrize(
    ("parked", "step"),
    [("document", "document"), ("gate", "gate"), ("result", "gate"), ("done", "gate")],
)
async def test_new_steps_re_run_a_saved_run_without_claiming_its_inputs_changed(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    monkeypatch: pytest.MonkeyPatch,
    parked: str,
    step: str,
) -> None:
    """Fails if a run saved by older steps errors, keeps an approval the new steps never
    showed, or tells the user their inputs changed when only the app's steps did."""
    await _park(client, db, user_with_profile, parked)
    monkeypatch.setattr(fingerprint_module, "STEPS_VERSION", fingerprint_module.STEPS_VERSION + 1)

    response = await client.get(URL)

    assert response.status_code == 200
    run = response.json()
    assert run["step"] == step and run["approved_at"] is None and run["done_at"] is None
    assert run["inputs_changed"] is False
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


async def test_a_change_before_approval_re_runs_the_steps(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the gate could show checks made for older inputs, or a run never approved
    claims its inputs changed after approval."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.post(f"{URL}/start", json={})
    await add_confirmed_document(
        db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "50000"}
    )

    run = (await client.get(URL)).json()
    again = (await client.get(URL)).json()

    assert run["gate"]["figures"]["gross_profit"] == "50000.00"
    assert run["inputs_changed"] is False
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


# ---- Backend review fixes ----


async def test_a_run_that_crashed_mid_way_re_runs_on_the_next_request(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fails if a failure between the reset and the end leaves a half-reset run that never
    re-runs (backend review M2)."""
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.post(f"{URL}/start", json={})  # a finished run, then a restart that crashes
    real = getattr(service, "research_step")

    async def crash(*args: object, **kwargs: object) -> object:
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.workflow.service.research_step", crash)
    with pytest.raises(RuntimeError):
        await client.post(f"{URL}/start", json={})
    monkeypatch.setattr("app.workflow.service.research_step", real)

    run = (await client.get(URL)).json()

    assert run["step"] == "gate" and run["research"] is not None


async def test_a_second_change_keeps_the_notice_and_approval_clears_it(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if "inputs changed" disappears on a second change before re-approving, or stays
    after approving (backend review L6)."""
    await approved_run(client, db, user_with_profile)
    await save_profile(db, user_with_profile, PROFILE_YEAR, on_atl=False)
    await client.get(URL)
    await save_profile(db, user_with_profile, PROFILE_YEAR, on_atl=True)

    run = (await client.get(URL)).json()
    approved = (
        await client.post(f"{URL}/approve", json={"fingerprint": run["fingerprint"]})
    ).json()

    assert run["inputs_changed"] is True
    assert approved["inputs_changed"] is False


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/approve"), ("post", "/back"), ("post", "/done")],
)
async def test_acting_on_no_run_is_404(
    client: AsyncClient, user_with_profile: User, method: str, path: str
) -> None:
    """Fails if an action before any run answers differently from GET (backend review L8)."""
    del user_with_profile
    body = {"fingerprint": "x"} if path == "/approve" else {}

    response = await getattr(client, method)(f"{URL}{path}", json=body)

    assert response.status_code == 404 and response.json() == {"detail": "No guided run yet."}


async def test_straight_after_a_change_the_result_and_done_are_refused(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if /result or /done (without a GET first) could use an approval for older inputs
    (backend review L10)."""
    await approved_run(client, db, user_with_profile)
    await add_confirmed_document(
        db, user_with_profile.id, DocType.BANK_PROFIT_CERTIFICATE, {"profit_amount": "1000"}
    )

    assert (await client.get(f"{URL}/result")).status_code == 409
    assert (await client.post(f"{URL}/done", json={})).status_code == 409


async def test_editing_a_confirmed_figure_after_approval_returns_to_the_gate(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if a changed figure on a confirmed certificate keeps the old approval (FR-013)."""
    await approved_run(client, db, user_with_profile)
    field = (
        await db.execute(
            select(ExtractedField)
            .join(Document)
            .where(
                Document.user_id == user_with_profile.id,
                ExtractedField.name == FieldName.TAXABLE_SALARY,
            )
        )
    ).scalar_one()
    field.amount = Decimal("1900000")
    await db.flush()

    run = (await client.get(URL)).json()

    assert run["step"] == "gate" and run["approved_at"] is None
    assert run["gate"]["figures"]["taxable_salary"] == "1900000.00"


class _NoEmbedder:
    """An embedder that fails the test if the guided run ever calls it."""

    async def embed_query(self, text: str) -> list[float]:
        """Fails the test: the run must not embed a query."""
        raise AssertionError(f"the guided run called the AI (embedding {len(text)} chars)")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Fails the test: the run must not embed documents."""
        raise AssertionError(f"the guided run called the AI ({len(texts)} texts)")


async def test_the_run_needs_no_ai(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the guided run calls any AI (amended 2026-11-16: plain code only, so it is fast):
    with an embedder that raises, it still reaches the gate citing the salary sections."""
    app.dependency_overrides[get_embedder] = _NoEmbedder
    try:
        await a_corpus(db)
        await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)

        run = (await client.post(f"{URL}/start", json={})).json()
    finally:
        app.dependency_overrides.pop(get_embedder, None)

    assert run["step"] == "gate"
    assert [p["location"] for p in run["research"]["passages"]] == ["§12(1)", "§149(1)"]
    assert await questions_recorded(db) == 0  # no AI, so nothing counts against 006's limits
