"""Where uploaded files are kept (feature 003, FR-018, task T048 and its review; research R4).

With a bucket configured, files go only to the private bucket; without one, the local disk.
Files are read and deleted by their stored location, which must be inside the uploads folder or
the configured bucket. Google's errors become one StorageUnavailable that reveals nothing. No
test reaches Google: the bucket client is an in-memory fake with the real client's shape.
"""

import logging
import uuid
from pathlib import Path

import pytest
from document_helpers import FakeBucketClient
from google.api_core.exceptions import Forbidden

from app.documents import storage as storage_module
from app.documents.storage import Storage, StorageUnavailable

pytestmark = pytest.mark.anyio

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
PDF = b"%PDF-1.7 synthetic"


def files_in(folder: Path) -> list[Path]:
    """Every file on the disk under the folder."""
    return [path for path in folder.rglob("*") if path.is_file()]


def forbidden() -> Forbidden:
    """Google's 403, with details that must never reach the user or the logs."""
    return Forbidden(  # type: ignore[no-untyped-call]  # google-api-core is untyped
        "secret-detail service-account@example.iam.gserviceaccount.com"
    )


async def test_with_a_bucket_a_file_goes_only_to_the_bucket(tmp_path: Path) -> None:
    """Fails if a deployed upload lands on the VM's disk, or under a guessable name (FR-018)."""
    client = FakeBucketClient()
    storage = Storage(tmp_path, bucket="uploads", client=client)

    location = await storage.save(USER, PDF, "pdf", "application/pdf")

    assert location.startswith(f"gs://uploads/{USER}/")
    name = location.removeprefix("gs://uploads/")
    uuid.UUID(name.removeprefix(f"{USER}/").removesuffix(".pdf"))  # a random id, not the filename
    assert client.buckets["uploads"][name] == (PDF, "application/pdf")
    assert not files_in(tmp_path)


async def test_a_bucket_file_is_read_back_and_deleted(tmp_path: Path) -> None:
    """Fails if a stored file can't be shown for review, retried, or removed with its document."""
    client = FakeBucketClient()
    storage = Storage(tmp_path, bucket="uploads", client=client)
    location = await storage.save(USER, PDF, "pdf", "application/pdf")

    assert await storage.read(location) == PDF
    await storage.delete(location)

    assert not client.buckets["uploads"]
    assert await storage.read(location) is None


async def test_without_a_bucket_files_stay_on_the_disk(tmp_path: Path) -> None:
    """Fails if development or tests stop using the local folder."""
    storage = Storage(tmp_path)

    location = await storage.save(USER, PDF, "pdf", "application/pdf")

    assert Path(location).parent == tmp_path / str(USER)
    assert await storage.read(location) == PDF
    await storage.delete(location)
    assert not files_in(tmp_path)


async def test_disk_files_from_before_the_switch_still_work(tmp_path: Path) -> None:
    """Fails if documents uploaded before a bucket was configured can't be read or deleted."""
    old = await Storage(tmp_path).save(USER, PDF, "pdf", "application/pdf")
    storage = Storage(tmp_path, bucket="uploads", client=FakeBucketClient())

    assert await storage.read(old) == PDF
    await storage.delete(old)
    assert not files_in(tmp_path)


async def test_a_missing_file_reads_as_none_and_deletes_quietly(tmp_path: Path) -> None:
    """Fails if a file that's already gone breaks the review page, retry or delete."""
    storage = Storage(tmp_path, bucket="uploads", client=FakeBucketClient())

    for location in [f"gs://uploads/{USER}/gone.pdf", str(tmp_path / str(USER) / "gone.pdf")]:
        assert await storage.read(location) is None
        await storage.delete(location)


@pytest.mark.parametrize(
    "location",
    [
        "/etc/passwd",  # outside the uploads folder
        "{tmp}/../outside.pdf",  # climbs out of it
        "gs://someone-elses-bucket/file.pdf",  # another bucket
        "gs://uploads",  # no object name
        "gs://uploads/../file.pdf",
    ],
)
async def test_a_location_outside_the_uploads_is_never_touched(
    tmp_path: Path, location: str
) -> None:
    """Fails if a tampered file_path could read or delete any file on the server, or reach
    another bucket the VM can see (storage review #4)."""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(PDF)
    client = FakeBucketClient()
    client.buckets["someone-elses-bucket"] = {"file.pdf": (PDF, "application/pdf")}
    storage = Storage(uploads, bucket="uploads", client=client)
    location = location.replace("{tmp}", str(uploads))

    assert await storage.read(location) is None
    await storage.delete(location)

    assert outside.exists()
    assert "file.pdf" in client.buckets["someone-elses-bucket"]


async def test_googles_errors_become_storage_unavailable_and_reveal_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Fails if a permission error or outage escapes as a raw 500, or its details are logged."""
    client = FakeBucketClient()
    storage = Storage(tmp_path, bucket="uploads", client=client)
    location = await storage.save(USER, PDF, "pdf", "application/pdf")
    client.fail = forbidden()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(StorageUnavailable):
            await storage.read(location)
        with pytest.raises(StorageUnavailable):
            await storage.delete(location)
        with pytest.raises(StorageUnavailable):
            await storage.save(USER, PDF, "pdf", "application/pdf")

    assert "Forbidden" in caplog.text
    assert "secret-detail" not in caplog.text
    assert "iam.gserviceaccount" not in caplog.text


async def test_a_failed_save_leaves_nothing_behind(tmp_path: Path) -> None:
    """Fails if a save that errors after Google stored the object leaves an unrecorded file."""
    client = FakeBucketClient()
    client.fail_after_store = forbidden()
    storage = Storage(tmp_path, bucket="uploads", client=client)

    with pytest.raises(StorageUnavailable):
        await storage.save(USER, PDF, "pdf", "application/pdf")

    assert not client.buckets["uploads"]


async def test_the_google_client_is_created_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails if every request builds a new client (credential lookup, a new token each time)."""
    created: list[FakeBucketClient] = []

    def new_client() -> FakeBucketClient:
        created.append(FakeBucketClient())
        return created[-1]

    monkeypatch.setattr(storage_module, "_new_client", new_client)
    storage_module.shared_client.cache_clear()
    try:
        for _ in range(3):
            await Storage(tmp_path, bucket="uploads").save(USER, PDF, "pdf", "application/pdf")
    finally:
        storage_module.shared_client.cache_clear()

    assert len(created) == 1
