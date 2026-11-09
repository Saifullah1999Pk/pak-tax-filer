"""POST /api/auth/signup (feature 002, User Story 6, task T047; contracts/auth-api.md, R15).

Sign-up reuses create_user (the create-user command's rules) and logs the new user in exactly
as login does.
"""

import pytest
from httpx2 import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Session, User
from app.auth.passwords import hash_password

pytestmark = pytest.mark.anyio

PASSWORD = "s3cret-pass"
EXISTS = {"detail": "An account with this email already exists. Log in instead."}


async def signup(client: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    """POST a JSON sign-up."""
    return await client.post("/api/auth/signup", json={"email": email, "password": password})


async def users(db: AsyncSession) -> int:
    """How many accounts exist."""
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def test_signup_creates_the_account_and_logs_in(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if a new account isn't created, or the user isn't logged in like after login
    (FR-024, FR-025)."""
    response = await signup(client, "  New.User@Example.com ")

    assert response.status_code == 201
    assert response.json() == {"email": "new.user@example.com"}
    cookie = response.headers["set-cookie"]
    assert "session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert (await client.get("/api/auth/me")).json() == {"email": "new.user@example.com"}
    user = (await db.execute(select(User))).scalar_one()
    assert user.email == "new.user@example.com"
    assert PASSWORD not in user.password_hash
    assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 1


async def test_the_new_password_works_for_login(client: AsyncClient) -> None:
    """Fails if the stored password can't be used to log in later."""
    await signup(client, "new@example.com")
    await client.post("/api/auth/logout", json={})

    login = await client.post(
        "/api/auth/login", json={"email": "new@example.com", "password": PASSWORD}
    )

    assert login.status_code == 200


@pytest.mark.parametrize("email", ["demo@example.com", "DEMO@Example.COM", "  demo@example.com "])
async def test_an_existing_email_is_refused_and_nothing_changes(
    client: AsyncClient, db: AsyncSession, email: str
) -> None:
    """Fails if an existing account (any case or spacing) is overwritten or duplicated, or the
    visitor isn't told to log in (FR-026)."""
    original = hash_password("original-pass")
    db.add(User(email="demo@example.com", password_hash=original))
    await db.flush()

    response = await signup(client, email, "another-pass")

    assert response.status_code == 409
    assert response.json() == EXISTS
    assert "set-cookie" not in response.headers
    assert await users(db) == 1
    stored = (await db.execute(select(User))).scalar_one()
    assert stored.password_hash == original


async def test_a_short_password_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if a password under 8 characters creates an account (FR-002, FR-024)."""
    response = await signup(client, "new@example.com", "7-chars")

    assert response.status_code == 422
    assert response.json() == {"detail": "Password must be at least 8 characters."}
    assert await users(db) == 0


async def test_an_email_without_at_sign_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if something that isn't an email becomes an account name."""
    response = await signup(client, "not-an-email")

    assert response.status_code == 422
    assert await users(db) == 0


async def test_non_json_signup_is_refused(client: AsyncClient, db: AsyncSession) -> None:
    """Fails if sign-up accepts form posts (research R3: JSON only)."""
    response = await client.post(
        "/api/auth/signup", data={"email": "new@example.com", "password": PASSWORD}
    )

    assert response.status_code == 415
    assert await users(db) == 0


async def test_a_validation_error_never_echoes_the_password(client: AsyncClient) -> None:
    """Fails if a rejected sign-up repeats the password back (security rule)."""
    response = await signup(client, "new@example.com", "do-not-echo-" + "x" * 1030)

    assert response.status_code == 422
    assert "do-not-echo" not in response.text
