"""Managing documents, and nobody else's (feature 003, task T021; docs/api-conventions.md).

Another user's document is always 404, never 403, so its existence isn't revealed.
"""

from pathlib import Path

import pytest
from conftest import TEST_PASSWORD, make_user
from document_helpers import PROFILE_YEAR, SALARY_RESULT, make_pdf, upload
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.extraction.client import ExtractionResult, FakeExtractor
from app.documents.models import Document, ExtractedField
from app.profile.service import save_profile

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("user_with_profile", "fake_extractor")]


async def switch_to_other_user(client: AsyncClient, db: AsyncSession) -> None:
    """Log the client in as a second synthetic user with a profile."""
    other = await make_user(db, "other@example.com")
    await save_profile(db, other, PROFILE_YEAR, on_atl=False)
    client.cookies.clear()
    response = await client.post(
        "/api/auth/login", json={"email": other.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def test_another_users_document_is_404_everywhere(
    client: AsyncClient, db: AsyncSession, fake_extractor: FakeExtractor
) -> None:
    """Fails if user B can read, download, edit, confirm, retry or delete user A's document."""
    fake_extractor.result = ExtractionResult(failure_reason="busy")  # So retry would apply.
    document_id = (await upload(client, make_pdf())).json()["id"]
    await switch_to_other_user(client, db)
    base = f"/api/documents/{document_id}"

    responses = [
        await client.get(base),
        await client.get(f"{base}/file"),
        await client.patch(f"{base}/fields/gross_salary", json={"value": "1"}),
        await client.post(f"{base}/confirm", json={}),
        await client.post(f"{base}/retry", json={}),
        await client.request("DELETE", base, json={}),
    ]

    assert [r.status_code for r in responses] == [404] * 6
    assert await db.get(Document, document_id) is not None
    assert (await client.get("/api/documents")).json() == []


async def test_list_shows_own_documents_newest_first_without_fields(
    client: AsyncClient,
) -> None:
    """Fails if the list is out of order or carries the figures."""
    first = (await upload(client, make_pdf())).json()["id"]
    second = (await upload(client, make_pdf())).json()["id"]

    response = await client.get("/api/documents")

    assert response.status_code == 200
    assert [d["id"] for d in response.json()] == [second, first]
    assert "fields" not in response.json()[0]
    assert response.json()[0]["status"] == "needs_review"


async def test_retry_reruns_a_failed_extraction(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a failed document can't be retried, or retry runs on anything else."""
    fake_extractor.result = ExtractionResult(failure_reason="busy")
    failed = (await upload(client, make_pdf())).json()
    fake_extractor.result = SALARY_RESULT

    retried = await client.post(f"/api/documents/{failed['id']}/retry", json={})
    again = await client.post(f"/api/documents/{failed['id']}/retry", json={})

    assert retried.status_code == 200
    assert retried.json()["status"] == "needs_review"
    assert retried.json()["failure_reason"] is None
    assert len(retried.json()["fields"]) == 4
    assert again.status_code == 409


async def test_delete_removes_the_document_its_fields_and_file(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Fails if deleting leaves the row, its fields or the stored file behind."""
    document_id = (await upload(client, make_pdf())).json()["id"]
    document = await db.get(Document, document_id)
    assert document is not None
    stored = Path(document.file_path)
    assert stored.exists()

    response = await client.request("DELETE", f"/api/documents/{document_id}", json={})

    assert response.status_code == 204
    db.expunge_all()
    assert await db.get(Document, document_id) is None
    assert (await db.scalars(select(ExtractedField))).first() is None
    assert not stored.exists()
    assert (await client.get(f"/api/documents/{document_id}")).status_code == 404


async def test_state_changes_must_be_json(client: AsyncClient) -> None:
    """Fails if a cross-site form could edit, confirm, retry or delete (research R3 of 002)."""
    document_id = (await upload(client, make_pdf())).json()["id"]
    base = f"/api/documents/{document_id}"
    form = {"Content-Type": "application/x-www-form-urlencoded"}

    responses = [
        await client.request(method, url, content="value=1", headers=form)
        for method, url in [
            ("PATCH", f"{base}/fields/gross_salary"),
            ("POST", f"{base}/confirm"),
            ("POST", f"{base}/retry"),
            ("DELETE", base),
        ]
    ]

    assert [r.status_code for r in responses] == [415] * 4
