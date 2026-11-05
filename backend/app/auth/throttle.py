"""Login throttling (feature 002, task T014, FR-007, research R4).

After 10 failed logins for an email within 15 minutes, further attempts for that email are
refused until the 15 minutes pass. Unknown emails are counted the same way, so throttling never
reveals which emails are registered. Stored in the database, so it survives restarts.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginFailure

MAX_FAILURES = 10
WINDOW = timedelta(minutes=15)


async def is_throttled(db: AsyncSession, email: str) -> bool:
    """True if this (normalised) email has 10 or more failures in the last 15 minutes."""
    since = datetime.now(UTC) - WINDOW
    failures = (
        await db.execute(
            select(func.count())
            .select_from(LoginFailure)
            .where(LoginFailure.email == email, LoginFailure.attempted_at > since)
        )
    ).scalar_one()
    return failures >= MAX_FAILURES


async def record_failure(db: AsyncSession, email: str) -> None:
    """Remember one failed attempt for this (normalised) email."""
    db.add(LoginFailure(email=email, attempted_at=datetime.now(UTC)))
    await db.flush()
