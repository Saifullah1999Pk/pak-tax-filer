"""POST /api/auth/login, /logout and GET /api/auth/me (feature 002, tasks T015, T021).

Contract: specs/002-auth-foundation/contracts/auth-api.md. Research: R2 (cookie), R3 (JSON only),
R4 (throttling), R5 (same answer and same work for unknown emails).
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import sessions, throttle
from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.auth.passwords import DUMMY_HASH, verify_password
from app.auth.users import get_user_by_email, normalize_email
from app.db import get_db
from app.settings import get_settings

COOKIE_NAME = "session"
INVALID_LOGIN = "Invalid email or password."
TOO_MANY_ATTEMPTS = "Too many attempts. Try again later."


router = APIRouter(prefix="/api/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class LoginRequest(BaseModel):
    """Login body."""

    email: str
    password: str


class EmailResponse(BaseModel):
    """The logged-in user's email, and nothing else."""

    email: str


@router.post("/login", dependencies=[Depends(require_json)])
async def login(body: LoginRequest, response: Response, db: DbSession) -> EmailResponse:
    """Log in with email and password; on success set the session cookie."""
    email = normalize_email(body.email)

    # Throttled attempts don't check the password at all (contract).
    if await throttle.is_throttled(db, email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)

    user = await get_user_by_email(db, email)
    # Unknown emails still pay for an Argon2 check, so timing doesn't reveal them (R5).
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok:
        await throttle.record_failure(db, email)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    token = await sessions.create_session(db, user)
    await db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(sessions.SESSION_LIFETIME.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
    )
    return EmailResponse(email=user.email)


@router.post(
    "/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_json)]
)
async def logout(
    response: Response,
    db: DbSession,
    session: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> None:
    """End the current session, if any, and clear the cookie. Always 204."""
    if session:
        await sessions.delete_session(db, session)
        await db.commit()
    response.delete_cookie(
        COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=get_settings().cookie_secure
    )


@router.get("/me")
async def me(user: Annotated[User, Depends(current_user)]) -> EmailResponse:
    """The logged-in user's email and nothing else (FR-011); 401 when not logged in."""
    return EmailResponse(email=user.email)
