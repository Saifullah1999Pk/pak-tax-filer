"""current_user: the reusable protection for endpoints that need a logged-in user (T020, FR-010).

Usage in any router:  `user: Annotated[User, Depends(current_user)]`. Missing, unknown,
logged-out and expired sessions all get the same 401 "Not logged in.".
"""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.sessions import get_user_for_token
from app.db import get_db

NOT_LOGGED_IN = "Not logged in."


async def current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[str | None, Cookie()] = None,
) -> User:
    """The logged-in user, from the `session` cookie; 401 otherwise."""
    user = await get_user_for_token(db, session) if session else None
    if user is None:
        # An expired session may have just been deleted; keep that deletion.
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_LOGGED_IN)
    return user
