"""Personal access tokens for the MCP server (feature 006, task T003; data-model.md).

Only a token's SHA-256 is stored; its full value is shown once, when a developer creates it
with `python -m app.cli create-token` (FR-015, FR-016 amended). A token is valid while its hash
matches, it isn't revoked and it hasn't expired (90 days).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PersonalAccessToken(Base):
    """Lets an MCP client act as one user, for that user's own data only."""

    __tablename__ = "personal_access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Which client it's for, e.g. "Claude Code" (1-50 characters).
    name: Mapped[str] = mapped_column(String(50))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # The first 8 characters (e.g. "ptx_ab12"), to tell tokens apart and revoke one.
    prefix: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
