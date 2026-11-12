"""Personal access token commands (feature 006, task T026; FR-015, FR-016 amended, research R8).

`create-token --email [--name]` prints the full value once and stores only its SHA-256;
`revoke-token --prefix` revokes it. The MCP server accepts a token only while it is valid.
"""

import hashlib
import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.cli import create_token_command, revoke_token_command
from app.tokens.models import PersonalAccessToken
from app.tokens.service import TOKEN_DAYS, owner_of

pytestmark = pytest.mark.anyio


async def a_user(db: AsyncSession, email: str = "demo@example.com") -> User:
    """A synthetic user."""
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    await db.flush()
    return user


async def created(db: AsyncSession, *args: str) -> tuple[int, str, str]:
    """Run create-token; its exit code, output and error output."""
    out, err = io.StringIO(), io.StringIO()
    code = await create_token_command(db, *args, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


async def test_a_token_is_shown_once_and_only_its_hash_is_stored(db: AsyncSession) -> None:
    """Fails if the full token is stored, or isn't printed, or lacks its 90-day expiry."""
    user = await a_user(db)

    code, out, _ = await created(db, "Demo@Example.com", "MCP client")

    assert code == 0
    token = next(word for word in out.split() if word.startswith("ptx_"))
    stored = (await db.execute(select(PersonalAccessToken))).scalar_one()
    assert stored.user_id == user.id and stored.name == "MCP client"
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored.prefix == token[:8]
    assert token not in (stored.token_hash, stored.prefix)
    assert stored.expires_at - stored.created_at == timedelta(days=TOKEN_DAYS) == timedelta(days=90)
    assert (await owner_of(db, token)).id == user.id  # type: ignore[union-attr]


@pytest.mark.parametrize("name", ["", "x" * 51])
async def test_a_name_must_be_1_to_50_characters(db: AsyncSession, name: str) -> None:
    """Fails if an empty or over-long name is stored (data-model.md)."""
    await a_user(db)

    code, out, err = await created(db, "demo@example.com", name)

    assert code == 1 and "ptx_" not in out and "1 to 50" in err


async def test_an_unknown_email_is_refused(db: AsyncSession) -> None:
    """Fails if a token can be made for no one, or the refusal says nothing."""
    code, out, err = await created(db, "nobody@example.com", "MCP client")

    assert code == 1 and "ptx_" not in out and "No user" in err


async def test_a_revoked_token_no_longer_works(db: AsyncSession) -> None:
    """Fails if revoke-token leaves the token usable (SC-006)."""
    await a_user(db)
    _, out, _ = await created(db, "demo@example.com", "MCP client")
    token = next(word for word in out.split() if word.startswith("ptx_"))
    printed = io.StringIO()

    code = await revoke_token_command(db, token[:8], out=printed, err=io.StringIO())

    assert code == 0 and token[:8] in printed.getvalue()
    assert await owner_of(db, token) is None


async def test_an_unknown_prefix_is_refused(db: AsyncSession) -> None:
    """Fails if revoking a token that doesn't exist claims success."""
    err = io.StringIO()

    assert await revoke_token_command(db, "ptx_none", out=io.StringIO(), err=err) == 1
    assert "No active token" in err.getvalue()


@pytest.mark.parametrize("state", ["wrong", "expired", "revoked", "missing"])
async def test_only_a_valid_token_has_an_owner(db: AsyncSession, state: str) -> None:
    """Fails if a wrong, expired, revoked or missing token is accepted (SC-006)."""
    await a_user(db)
    _, out, _ = await created(db, "demo@example.com", "MCP client")
    token = next(word for word in out.split() if word.startswith("ptx_"))
    stored = (await db.execute(select(PersonalAccessToken))).scalar_one()
    if state == "expired":
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    if state == "revoked":
        stored.revoked_at = datetime.now(UTC)
    await db.flush()
    presented = {"wrong": token[:-1] + ("y" if token.endswith("x") else "x"), "missing": None}.get(
        state, token
    )

    assert await owner_of(db, presented) is None


async def test_using_a_token_records_when(db: AsyncSession) -> None:
    """Fails if last_used_at isn't updated, so a developer can't tell a token is in use."""
    await a_user(db)
    _, out, _ = await created(db, "demo@example.com", "MCP client")
    token = next(word for word in out.split() if word.startswith("ptx_"))

    await owner_of(db, token)

    stored = (await db.execute(select(PersonalAccessToken))).scalar_one()
    assert stored.last_used_at is not None
