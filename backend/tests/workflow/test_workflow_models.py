"""The guided run's table (feature 007, task T002; specs/007-agentic-workflow/data-model.md).

Run against the migrated test database, as the other features' table tests are.
"""

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import Base
from app.workflow.models import Step, WorkflowRun

pytestmark = pytest.mark.anyio


async def a_user(db: AsyncSession, email: str = "run@example.com") -> User:
    """A synthetic user to own runs."""
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    return user


def a_run(user: User, tax_year: str = "2025-26") -> WorkflowRun:
    """A fresh run at the document step."""
    now = datetime.now(UTC)
    return WorkflowRun(
        user_id=user.id, tax_year=tax_year, step=Step.DOCUMENT, created_at=now, updated_at=now
    )


async def test_a_new_run_starts_empty_at_the_document_step(db: AsyncSession) -> None:
    """Fails if a run's defaults would let it look approved, done or already checked."""
    run = a_run(await a_user(db))
    db.add(run)
    await db.flush()
    await db.refresh(run)

    assert run.step is Step.DOCUMENT
    assert run.step_outputs == {}
    assert run.outputs_fingerprint is None
    assert (run.approved_at, run.approved_fingerprint, run.done_at) == (None, None, None)


def test_the_steps_are_the_data_models_six() -> None:
    """Fails if a step is added, dropped or renamed without the data model changing too."""
    assert [s.value for s in Step] == ["document", "validate", "research", "gate", "result", "done"]


async def test_one_run_per_user_and_tax_year(db: AsyncSession) -> None:
    """Fails if a user could have two active runs for the same year (FR-002)."""
    user = await a_user(db)
    db.add(a_run(user, "2025-26"))
    db.add(a_run(user, "2026-27"))
    await db.flush()  # another year is fine

    db.add(a_run(user, "2025-26"))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_runs_are_deleted_with_their_user(db: AsyncSession) -> None:
    """Fails if a user's runs outlive the user."""
    user = await a_user(db)
    db.add(a_run(user))
    await db.flush()

    await db.execute(delete(User).where(User.id == user.id))

    assert (await db.execute(select(func.count()).select_from(WorkflowRun))).scalar_one() == 0


async def test_the_migration_matches_the_model(db: AsyncSession) -> None:
    """Fails if migration 0008 creates something different from what the model describes."""
    connection = await db.connection()

    def differences(sync_connection) -> list[str]:  # type: ignore[no-untyped-def]
        context = MigrationContext.configure(sync_connection)
        return [repr(d) for d in compare_metadata(context, Base.metadata) if "workflow" in repr(d)]

    assert await connection.run_sync(differences) == []
    assert (await db.execute(text("select to_regclass('workflow_runs')"))).scalar_one()
