"""Where uploaded files are kept (feature 003, FR-018; research R4, amended 2026-11-09).

The deployed app keeps them in a private Google Cloud Storage bucket (UPLOAD_BUCKET), reached
with the VM's own Google identity, so no key exists anywhere. Development and tests keep them on
the local disk. Files are read and deleted by the form of their stored location (`gs://...` or a
path), so files stored before a switch keep working. Names are random, never the user's file
name. Users only ever get a file through the owner-checked endpoint: there are no public links.
"""

import uuid
from pathlib import Path
from typing import Any

import anyio
from google.api_core.exceptions import NotFound

_SCHEME = "gs://"


class Storage:
    """Save, read and delete uploaded files in the bucket (if configured) or on the disk."""

    def __init__(self, upload_dir: Path, bucket: str | None = None, client: Any = None) -> None:
        self._upload_dir = upload_dir
        self._bucket = bucket
        # google.cloud.storage.Client, created on first use; tests pass an in-memory fake.
        self._client = client

    async def save(
        self, user_id: uuid.UUID, content: bytes, extension: str, media_type: str
    ) -> str:
        """Store the file under <user_id>/<random uuid>.<ext>; return where it is."""
        name = f"{user_id}/{uuid.uuid4()}.{extension}"
        if self._bucket is None:
            path = anyio.Path(self._upload_dir) / name
            await path.parent.mkdir(parents=True, exist_ok=True)
            await path.write_bytes(content)
            return str(path)
        blob = self._blob(self._bucket, name)
        await anyio.to_thread.run_sync(
            lambda: blob.upload_from_string(content, content_type=media_type)
        )
        return f"{_SCHEME}{self._bucket}/{name}"

    async def read(self, location: str) -> bytes | None:
        """The file's bytes, or None if it's gone."""
        if not location.startswith(_SCHEME):
            path = anyio.Path(location)
            return await path.read_bytes() if await path.is_file() else None
        blob = self._blob(*_split(location))
        try:
            return await anyio.to_thread.run_sync(blob.download_as_bytes)
        except NotFound:
            return None

    async def delete(self, location: str) -> None:
        """Remove the file; a file that's already gone is fine."""
        if not location.startswith(_SCHEME):
            await anyio.Path(location).unlink(missing_ok=True)
            return
        blob = self._blob(*_split(location))
        try:
            await anyio.to_thread.run_sync(blob.delete)
        except NotFound:
            pass

    def _blob(self, bucket: str, name: str) -> Any:
        if self._client is None:
            # Imported here so development and tests, which use the disk, never load it.
            # google-cloud-storage ships no type information.
            from google.cloud import storage  # type: ignore[import-untyped]  # pylint: disable=import-outside-toplevel

            self._client = storage.Client()
        return self._client.bucket(bucket).blob(name)


def _split(location: str) -> tuple[str, str]:
    """('bucket', 'user/uuid.pdf') from 'gs://bucket/user/uuid.pdf'."""
    bucket, _, name = location.removeprefix(_SCHEME).partition("/")
    return bucket, name
