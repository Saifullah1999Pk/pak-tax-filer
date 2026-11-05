"""Upload checks and storage (feature 003, task T010, research R4; spec US1 scenario 4).

Every refused file must be refused before anything is sent to the AI.
"""

from pathlib import Path

import pytest
from document_helpers import PROFILE_YEAR, make_image, make_pdf, upload
from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.extraction.client import FakeExtractor
from app.documents.models import Document
from app.documents.uploads import MAX_BYTES

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("fake_extractor")]


@pytest.mark.parametrize(
    ("content", "filename", "media_type"),
    [
        (make_pdf(), "certificate.pdf", "application/pdf"),
        (make_image("JPEG"), "photo.jpg", "image/jpeg"),
        (make_image("JPEG"), "photo.jpeg", "image/jpeg"),
        (make_image("PNG"), "photo.png", "image/png"),
    ],
)
@pytest.mark.usefixtures("user_with_profile")
async def test_pdf_jpg_and_png_are_accepted(
    client: AsyncClient, content: bytes, filename: str, media_type: str
) -> None:
    """Fails if an allowed file type is refused."""
    response = await upload(client, content, filename)

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "needs_review"
    assert response.json()["page_count"] == 1
    assert response.json()["media_type"] == media_type
    file = await client.get(f"/api/documents/{response.json()['id']}/file")
    assert file.headers["content-type"] == media_type


@pytest.mark.parametrize(
    ("content", "filename", "status", "words"),
    [
        (b"PK\x03\x04 a word document", "certificate.pdf", 415, "PDF, JPG or PNG"),
        (make_pdf(), "certificate.docx", 415, "PDF, JPG or PNG"),
        (b"%PDF-" + b"0" * MAX_BYTES, "certificate.pdf", 413, "10 MB"),
        (make_pdf(pages=6), "certificate.pdf", 422, "5 pages"),
        (make_pdf(password="secret"), "certificate.pdf", 422, "password"),
        (b"%PDF-1.7 not really a pdf", "certificate.pdf", 422, "couldn't be read"),
    ],
)
@pytest.mark.usefixtures("user_with_profile")
async def test_bad_files_are_refused_before_the_ai_sees_them(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    client: AsyncClient,
    fake_extractor: FakeExtractor,
    db: AsyncSession,
    content: bytes,
    filename: str,
    status: int,
    words: str,
) -> None:
    """Fails if a wrong type, oversize, too-long, encrypted or corrupt file gets through."""
    response = await upload(client, content, filename)

    assert response.status_code == status
    assert words in response.json()["detail"]
    assert not fake_extractor.calls
    assert (await db.scalars(select(Document))).first() is None


async def test_file_is_stored_under_a_random_name(
    client: AsyncClient, user_with_profile: User, upload_dir: Path, db: AsyncSession
) -> None:
    """Fails if the uploaded file name is used on disk (path tricks, research R4)."""
    pdf = make_pdf()
    response = await upload(client, pdf, "../../etc/passwd.pdf")

    document = await db.get(Document, response.json()["id"])
    assert document is not None
    stored = Path(document.file_path)
    assert stored.parent == upload_dir / str(user_with_profile.id)
    assert stored.suffix == ".pdf"
    assert "passwd" not in stored.name
    assert stored.read_bytes() == pdf


async def test_document_takes_the_profile_tax_year(
    client: AsyncClient, user_with_profile: User
) -> None:
    """Fails if the document's tax year doesn't come from the profile (feature 002)."""
    del user_with_profile
    response = await upload(client, make_pdf())

    assert response.json()["tax_year"] == PROFILE_YEAR


@pytest.mark.usefixtures("logged_in_user")
async def test_without_a_profile_upload_is_refused(
    client: AsyncClient, fake_extractor: FakeExtractor
) -> None:
    """Fails if a user without a profile can upload (409, feature 002's require_profile)."""
    response = await upload(client, make_pdf())

    assert response.status_code == 409
    assert response.json()["detail"] == "Set up your profile first."
    assert not fake_extractor.calls


async def test_logged_out_upload_is_refused(client: AsyncClient) -> None:
    """Fails if uploading works without logging in."""
    response = await upload(client, make_pdf())

    assert response.status_code == 401


@pytest.mark.usefixtures("user_with_profile")
async def test_unknown_document_type_is_refused(client: AsyncClient) -> None:
    """Fails if a type other than the two certificates is accepted."""
    response = await upload(client, make_pdf(), doc_type="passport")

    assert response.status_code == 422
