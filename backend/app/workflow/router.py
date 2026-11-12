"""The guided run's API (feature 007, tasks T010, T015; contracts/workflow-api.md).

HTTP only: the service runs the steps and enforces the gate. Every endpoint needs a login and a
taxpayer profile (002's require_profile: 409 "Set up your profile first.").
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.rag.embed import Embedder
from app.rag.router import get_embedder
from app.settings import get_settings
from app.workflow import service
from app.workflow.client import AgentClient, GeminiAgentClient
from app.workflow.models import Step, WorkflowRun

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

NO_RUN = "No guided run yet."
_GATE_ONWARDS = (Step.GATE, Step.RESULT, Step.DONE)


def get_agent_client() -> AgentClient:
    """The agents' client the app uses (tests replace it with a FakeAgentClient)."""
    settings = get_settings()
    return GeminiAgentClient(
        api_key=settings.gemini_api_key,
        model=settings.workflow_model,
        effort=settings.workflow_effort,
    )


async def get_context(
    user: Annotated[User, Depends(current_user)],
    profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[AgentClient, Depends(get_agent_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> service.Context:
    """The request's user, profile, session and AI services, for the service."""
    return service.Context(db=db, user=user, profile=profile, client=client, embedder=embedder)


Ctx = Annotated[service.Context, Depends(get_context)]


async def run_out(ctx: service.Context, run: WorkflowRun) -> dict[str, Any]:
    """The contract's run object."""
    outputs = run.step_outputs or {}
    return {
        "step": run.step.value,
        "tax_year": run.tax_year,
        "fingerprint": run.outputs_fingerprint,
        "document": outputs.get("document"),
        "validation": outputs.get("validation"),
        "research": outputs.get("research"),
        "gate": await service.gate_view(ctx) if run.step in _GATE_ONWARDS else None,
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "done_at": run.done_at.isoformat() if run.done_at else None,
    }


@router.get("")
async def read_run(ctx: Ctx) -> dict[str, Any]:
    """The current run, re-checked first if the inputs changed; 404 before the first start."""
    run = await service.get_run(ctx)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_RUN)
    return await run_out(ctx, run)


@router.post("/start", dependencies=[Depends(require_json)])
async def start_run(ctx: Ctx) -> dict[str, Any]:
    """Start (or restart) the run: steps 1-3, then the gate or what's missing."""
    return await run_out(ctx, await service.start(ctx))
