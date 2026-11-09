"""At most 10 extractions per user in any 24 hours (feature 003, FR-017; 002 task T048).

Each upload or retry calls the free AI quota, so with open sign-up (002, User Story 6) one user
must not be able to use it up. Over the limit, nothing is stored and the AI isn't called.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from document_helpers import make_pdf, upload
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.passwords import hash_password
from app.documents.extraction.client import ExtractionResult, FakeExtractor, failed
from app.documents.models import Document, ExtractionAttempt

pytestmark = pytest.mark.anyio

LIMIT_MESSAGE = "Daily limit reached: 10 extractions per 24 hours. Try again later."


async def add_attempts(
    db: AsyncSession, user_id: uuid.UUID, count: int, hours_ago: float = 1
) -> None:
    """`count` earlier extraction attempts for the user, `hours_ago` hours ago."""
    at = datetime.now(UTC) - timedelta(hours=hours_ago)
    db.add_all(ExtractionAttempt(user_id=user_id, attempted_at=at) for _ in range(count))
    await db.flush()


async def attempts(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many attempts are recorded for the user."""
    return (
        await db.execute(
            select(func.count())
            .select_from(ExtractionAttempt)
            .where(ExtractionAttempt.user_id == user_id)
        )
    ).scalar_one()


def files_in(folder: Path) -> list[Path]:
    """Every stored file under the uploads folder."""
    return [path for path in folder.rglob("*") if path.is_file()]


async def test_the_eleventh_upload_is_refused_before_anything_happens(
    client: AsyncClient,
    db: AsyncSession,
    user_with_profile: User,
    fake_extractor: FakeExtractor,
    upload_dir: Path,
) -> None:
    """Fails if an upload over the limit stores a file, creates a document or calls the AI."""
    await add_attempts(db, user_with_profile.id, 10)

    response = await upload(client, make_pdf())

    assert response.status_code == 429
    assert response.json() == {"detail": LIMIT_MESSAGE}
    assert not fake_extractor.calls
    assert (await db.scalars(select(Document))).first() is None
    assert not files_in(upload_dir)
    assert await attempts(db, user_with_profile.id) == 10


@pytest.mark.usefixtures("fake_extractor")
async def test_an_upload_under_the_limit_works_and_is_counted(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if the 10th extraction is refused, or an upload isn't counted."""
    await add_attempts(db, user_with_profile.id, 9)

    response = await upload(client, make_pdf())

    assert response.status_code == 201
    assert await attempts(db, user_with_profile.id) == 10


async def test_retries_count_and_are_refused_over_the_limit(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if retrying could bypass the limit (each retry calls the AI too)."""
    fake_extractor.result = failed("The AI service is busy. Try again in a minute.")
    document_id = (await upload(client, make_pdf())).json()["id"]
    assert await attempts(db, user_with_profile.id) == 1

    assert (await client.post(f"/api/documents/{document_id}/retry", json={})).status_code == 200
    assert await attempts(db, user_with_profile.id) == 2

    await add_attempts(db, user_with_profile.id, 8)
    calls = len(fake_extractor.calls)
    refused = await client.post(f"/api/documents/{document_id}/retry", json={})

    assert refused.status_code == 429
    assert refused.json() == {"detail": LIMIT_MESSAGE}
    assert len(fake_extractor.calls) == calls


@pytest.mark.usefixtures("fake_extractor")
async def test_deleting_a_document_does_not_reset_the_count(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if upload-and-delete could be repeated forever."""
    document_id = (await upload(client, make_pdf())).json()["id"]

    deleted = await client.request("DELETE", f"/api/documents/{document_id}", json={})

    assert deleted.status_code == 204
    assert await attempts(db, user_with_profile.id) == 1


async def test_a_wrong_type_upload_still_counts(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, fake_extractor: FakeExtractor
) -> None:
    """Fails if a refused wrong-type file (which did call the AI) isn't counted."""
    fake_extractor.result = ExtractionResult(
        failure_reason="This doesn't look like a salary certificate.", wrong_type=True
    )

    assert (await upload(client, make_pdf())).status_code == 422
    assert await attempts(db, user_with_profile.id) == 1


@pytest.mark.usefixtures("fake_extractor")
async def test_attempts_older_than_24_hours_do_not_count(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if yesterday's uploads still block today's."""
    await add_attempts(db, user_with_profile.id, 10, hours_ago=25)

    assert (await upload(client, make_pdf())).status_code == 201


@pytest.mark.usefixtures("fake_extractor")
async def test_another_users_attempts_do_not_count(
    client: AsyncClient, db: AsyncSession, user_with_profile: User
) -> None:
    """Fails if one user's uploads use up someone else's limit."""
    other = User(email="other@example.com", password_hash=hash_password("other-pass"))
    db.add(other)
    await db.flush()
    await add_attempts(db, other.id, 10)

    assert (await upload(client, make_pdf())).status_code == 201
    assert await attempts(db, user_with_profile.id) == 1
