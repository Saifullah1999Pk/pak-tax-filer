"""The guided run's table (feature 007, task T002; specs/007-agentic-workflow/data-model.md).

One row per user and tax year: the current step, what the document, validation and research
steps produced with the fingerprint of the inputs they were made for, and the approval with the
fingerprint it was given for. The tax result is never stored; it is recalculated (as in 004).
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Step(enum.StrEnum):
    """Where a run is (research R2)."""

    DOCUMENT = "document"
    VALIDATE = "validate"
    RESEARCH = "research"
    GATE = "gate"
    RESULT = "result"
    DONE = "done"


class WorkflowRun(Base):
    """One user's guided run for one tax year (at most one, FR-002)."""

    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("user_id", "tax_year", name="uq_workflow_runs_user_year"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tax_year: Mapped[str] = mapped_column(String(7))
    step: Mapped[Step] = mapped_column(
        Enum(Step, name="workflow_step", values_callable=lambda members: [m.value for m in members])
    )
    # The document, validation and research outputs (data-model.md); empty until step 1 runs.
    step_outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    outputs_fingerprint: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_fingerprint: Mapped[str | None] = mapped_column(String(64))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
