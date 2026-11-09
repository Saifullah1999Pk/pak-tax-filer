"""The documents API with the private bucket configured (feature 003, FR-018; storage review).

Every other API test uses the disk; these run the same endpoints against an in-memory fake of
Google's client, including Google refusing or failing.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from document_helpers import FakeBucketClient, make_pdf, upload
from google.api_core.exceptions import Forbidden
from httpx2 import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.extraction.client import ExtractionResult, FakeExtractor, failed
from app.documents.models import Document, ExtractionAttempt
from app.documents.router import get_storage
from app.documents.storage import Storage
from app.main import app
from app.settings import Settings

pytestmark = pytest.mark.anyio

UNAVAILABLE = {"detail": "Couldn't reach file storage. Try again later."}


@pytest.fixture(name="bucket")
def fake_bucket(tmp_path: Path) -> Iterator[FakeBucketClient]:
    """The app's storage, pointed at a fake private bucket named "uploads"."""
    client = FakeBucketClient()
    app.dependency_overrides[get_storage] = lambda: Storage(tmp_path, "uploads", client)
    yield client


def objects(client: FakeBucketClient) -> dict[str, tuple[bytes, str]]:
    """What's in the bucket."""
    return client.buckets.get("uploads", {})


def forbidden() -> Forbidden:
    """Google's 403, as when the VM's identity has no access to the bucket."""
    return Forbidden("no access")  # type: ignore[no-untyped-call]  # google-api-core is untyped


async def attempts(db: AsyncSession) -> int:
    """How many extraction attempts are recorded."""
    return (await db.execute(select(func.count()).select_from(ExtractionAttempt))).scalar_one()


async def test_the_app_uses_the_bucket_when_one_is_configured() -> None:
    """Fails if UPLOAD_BUCKET is ignored and the deployed app keeps files on its disk."""
    settings = Settings(database_url="unused", cookie_secure=True, upload_bucket="uploads")
    client = FakeBucketClient()

    with patch("app.documents.router.get_settings", return_value=settings):
        storage = get_storage()
    with patch("app.documents.storage.shared_client", return_value=client):
        location = await storage.save(uuid.uuid4(), b"%PDF-1.7", "pdf", "application/pdf")

    assert location.startswith("gs://uploads/")
    assert objects(client)


@pytest.mark.usefixtures("user_with_profile", "fake_extractor")
async def test_upload_view_and_delete_go_through_the_bucket(
    client: AsyncClient, bucket: FakeBucketClient, upload_dir: Path
) -> None:
    """Fails if an upload, the review page's file or a delete doesn't use the private bucket."""
    pdf = make_pdf()
    created = await upload(client, pdf)
    assert created.status_code == 201
    assert [content for content, _ in objects(bucket).values()] == [pdf]
    assert not [path for path in upload_dir.rglob("*") if path.is_file()]

    file = await client.get(f"/api/documents/{created.json()['id']}/file")
    assert file.status_code == 200
    assert file.content == pdf
    assert file.headers["content-type"] == "application/pdf"

    deleted = await client.request("DELETE", f"/api/documents/{created.json()['id']}", json={})
    assert deleted.status_code == 204
    assert not objects(bucket)


@pytest.mark.usefixtures("user_with_profile")
async def test_a_refused_upload_leaves_the_bucket_empty(
    client: AsyncClient, bucket: FakeBucketClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a wrong-type upload's file stays in the bucket with no document."""
    fake_extractor.result = ExtractionResult(
        failure_reason="Not a salary certificate.", wrong_type=True
    )

    assert (await upload(client, make_pdf())).status_code == 422
    assert not objects(bucket)


@pytest.mark.usefixtures("user_with_profile")
async def test_a_retry_reads_the_file_from_the_bucket(
    client: AsyncClient, bucket: FakeBucketClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if retry looks for the file anywhere but where it was stored."""
    fake_extractor.result = failed("The AI service is busy. Try again in a minute.")
    document_id = (await upload(client, make_pdf())).json()["id"]
    assert objects(bucket)

    retried = await client.post(f"/api/documents/{document_id}/retry", json={})

    assert retried.status_code == 200
    assert "missing" not in (retried.json()["failure_reason"] or "")
    assert len(fake_extractor.calls) == 2


@pytest.mark.usefixtures("fake_extractor")
async def test_storage_failing_on_upload_is_503_and_costs_no_extraction(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, bucket: FakeBucketClient
) -> None:
    """Fails if Google refusing the upload is a raw 500, keeps a document, or uses up one of
    the user's daily extractions although the AI was never called (storage review #2)."""
    del user_with_profile
    bucket.fail = forbidden()

    response = await upload(client, make_pdf())

    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert (await db.scalars(select(Document))).first() is None
    assert await attempts(db) == 0


@pytest.mark.usefixtures("user_with_profile", "fake_extractor")
async def test_storage_failing_on_view_or_retry_is_503(
    client: AsyncClient, bucket: FakeBucketClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if the review page or a retry gets a raw 500 when Google is unavailable."""
    fake_extractor.result = failed("The AI service is busy. Try again in a minute.")
    document_id = (await upload(client, make_pdf())).json()["id"]
    bucket.fail = forbidden()

    file = await client.get(f"/api/documents/{document_id}/file")
    retried = await client.post(f"/api/documents/{document_id}/retry", json={})

    assert (file.status_code, file.json()) == (503, UNAVAILABLE)
    assert (retried.status_code, retried.json()) == (503, UNAVAILABLE)


@pytest.mark.usefixtures("user_with_profile", "fake_extractor")
async def test_a_delete_still_succeeds_if_removing_the_file_fails(
    client: AsyncClient, db: AsyncSession, bucket: FakeBucketClient
) -> None:
    """Fails if a delete that already happened answers 500 (a retry would then be 404)."""
    document_id = (await upload(client, make_pdf())).json()["id"]
    bucket.fail = forbidden()

    deleted = await client.request("DELETE", f"/api/documents/{document_id}", json={})

    assert deleted.status_code == 204
    assert (await db.scalars(select(Document))).first() is None
