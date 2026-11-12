"""Saves at the same moment (double-click, two tabs) don't fail (feature 005, backend review M2).

Like tests/auth/test_throttle_concurrency.py, each request here has its own database connection
so they truly run together; rows are committed to the test database and removed afterwards.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from conftest import TEST_PASSWORD
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.models import User
from app.auth.passwords import hash_password
from app.db import get_db
from app.main import app
from app.wealth.models import WealthStatement

pytestmark = pytest.mark.anyio

EMAIL = "wealth-race@example.com"
STATEMENT = {
    "previous_net_assets": "100000",
    "assets": [{"category": "bank_account", "description": "Savings", "amount": "100000"}],
    "liabilities": [{"description": "Loan", "creditor": "Bank", "amount": "5000"}],
    "expenses": {"rent": "1000", "medical": "2000"},
}


@pytest.mark.parametrize("saved_before", [False, True], ids=["first-saves", "replacing-saves"])
async def test_simultaneous_saves_all_succeed_with_one_statement(
    test_database_url: str, saved_before: bool
) -> None:
    """Fails if two first saves both insert (a unique-constraint 500), or two replace-all saves
    collide, instead of being applied one after the other."""
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def separate_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    async with sessions() as setup:
        setup.add(User(email=EMAIL, password_hash=hash_password(TEST_PASSWORD)))
        await setup.commit()

    app.dependency_overrides[get_db] = separate_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as http:
            login = await http.post(
                "/api/auth/login", json={"email": EMAIL, "password": TEST_PASSWORD}
            )
            assert login.status_code == 200
            if saved_before:
                # Then the saves below race to REPLACE rows (asset, liability and expense
                # rows), not to insert the first statement.
                first = await http.put("/api/wealth/2025-26", json=STATEMENT)
                assert first.status_code == 200
            responses = await asyncio.gather(
                *(http.put("/api/wealth/2025-26", json=STATEMENT) for _ in range(5))
            )
        async with sessions() as check:
            user_id = (await check.scalars(select(User.id).where(User.email == EMAIL))).one()
            statements = (
                await check.execute(
                    select(func.count())
                    .select_from(WealthStatement)
                    .where(WealthStatement.user_id == user_id)
                )
            ).scalar_one()
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with sessions() as cleanup:
            await cleanup.execute(delete(User).where(User.email == EMAIL))
            await cleanup.commit()
        await engine.dispose()

    assert [r.status_code for r in responses] == [200] * 5
    assert statements == 1
