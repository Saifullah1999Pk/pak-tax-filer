"""Where uploaded files are kept (feature 003, FR-018, task T048; research R4, amended).

With a bucket configured, files go only to the private bucket; without one, the local disk.
Files are read and deleted by their stored location, so files from before a switch still work.
No test reaches Google: the bucket client is an in-memory fake with the real client's shape.
"""

import uuid
from pathlib import Path

import pytest
from google.api_core.exceptions import NotFound

from app.documents.storage import Storage

pytestmark = pytest.mark.anyio

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
PDF = b"%PDF-1.7 synthetic"


class FakeBlob:
    """One object in the fake bucket."""

    def __init__(self, store: dict[str, tuple[bytes, str]], name: str) -> None:
        self.store = store
        self.name = name

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        """Store the bytes and their media type."""
        self.store[self.name] = (data, content_type)

    def download_as_bytes(self) -> bytes:
        """The stored bytes, or NotFound like the real client."""
        if self.name not in self.store:
            raise NotFound(self.name)  # type: ignore[no-untyped-call]  # google-api-core is untyped
        return self.store[self.name][0]

    def delete(self) -> None:
        """Remove the object, or NotFound like the real client."""
        if self.store.pop(self.name, None) is None:
            raise NotFound(self.name)  # type: ignore[no-untyped-call]  # google-api-core is untyped


class FakeBucket:  # pylint: disable=too-few-public-methods
    """A bucket: objects by name."""

    def __init__(self, store: dict[str, tuple[bytes, str]]) -> None:
        self.store = store

    def blob(self, name: str) -> FakeBlob:
        """The object with this name (it may not exist yet)."""
        return FakeBlob(self.store, name)


class FakeClient:  # pylint: disable=too-few-public-methods
    """google.cloud.storage.Client's shape, kept in memory per bucket name."""

    def __init__(self) -> None:
        self.buckets: dict[str, dict[str, tuple[bytes, str]]] = {}

    def bucket(self, name: str) -> FakeBucket:
        """The bucket with this name."""
        return FakeBucket(self.buckets.setdefault(name, {}))


def files_in(folder: Path) -> list[Path]:
    """Every file on the disk under the uploads folder."""
    return [path for path in folder.rglob("*") if path.is_file()]


async def test_with_a_bucket_a_file_goes_only_to_the_bucket(tmp_path: Path) -> None:
    """Fails if a deployed upload lands on the VM's disk, or under a guessable name (FR-018)."""
    client = FakeClient()
    storage = Storage(tmp_path, bucket="uploads", client=client)

    location = await storage.save(USER, PDF, "pdf", "application/pdf")

    assert location.startswith(f"gs://uploads/{USER}/")
    assert location.endswith(".pdf")
    name = location.removeprefix("gs://uploads/")
    uuid.UUID(name.removeprefix(f"{USER}/").removesuffix(".pdf"))  # a random id, not the filename
    assert client.buckets["uploads"][name] == (PDF, "application/pdf")
    assert not files_in(tmp_path)


async def test_a_bucket_file_is_read_back_and_deleted(tmp_path: Path) -> None:
    """Fails if a stored file can't be shown for review, retried, or removed with its document."""
    client = FakeClient()
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
    storage = Storage(tmp_path, bucket="uploads", client=FakeClient())

    assert await storage.read(old) == PDF
    await storage.delete(old)
    assert not files_in(tmp_path)


async def test_bucket_files_still_work_if_the_setting_is_removed(tmp_path: Path) -> None:
    """Fails if a gs:// location is treated as a disk path when no bucket is configured."""
    client = FakeClient()
    location = await Storage(tmp_path, bucket="uploads", client=client).save(
        USER, PDF, "pdf", "application/pdf"
    )

    assert await Storage(tmp_path, client=client).read(location) == PDF


async def test_a_missing_file_reads_as_none_and_deletes_quietly(tmp_path: Path) -> None:
    """Fails if a file that's already gone breaks the review page, retry or delete."""
    storage = Storage(tmp_path, bucket="uploads", client=FakeClient())

    for location in ["gs://uploads/gone.pdf", str(tmp_path / "gone.pdf")]:
        assert await storage.read(location) is None
        await storage.delete(location)
