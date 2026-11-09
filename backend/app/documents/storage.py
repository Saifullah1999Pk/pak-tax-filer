"""Where uploaded files are kept (feature 003, FR-018; research R4, amended 2026-11-09).

The deployed app keeps them in a private Google Cloud Storage bucket (UPLOAD_BUCKET), reached
with the VM's own Google identity, so no key exists anywhere. Development and tests keep them on
the local disk. Files are read and deleted by the form of their stored location (`gs://...` or a
path), so files stored before a switch keep working; a location must be inside the uploads
folder or the configured bucket, or it is treated as missing. Names are random, never the user's
file name. Users only ever get a file through the owner-checked endpoint: no public links.
"""

import logging
import uuid
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

import anyio
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError

logger = logging.getLogger(__name__)

_SCHEME = "gs://"
_T = TypeVar("_T")


class StorageUnavailable(Exception):
    """Google Cloud Storage refused or failed (permissions, outage); the user sees only "try
    again later", and only the error's type is logged (HTTP 503)."""


def _new_client() -> Any:
    # Imported here so development and tests, which use the disk, never load it.
    # google-cloud-storage ships no type information.
    from google.cloud import storage  # type: ignore[import-untyped]  # pylint: disable=import-outside-toplevel

    return storage.Client()


@lru_cache(maxsize=1)
def shared_client() -> Any:
    """One client for the process: finding the VM's credentials and a token is slow, so it's
    done once (storage review #3). Called only from worker threads."""
    return _new_client()


class Storage:
    """Save, read and delete uploaded files in the bucket (if configured) or on the disk."""

    def __init__(self, upload_dir: Path, bucket: str | None = None, client: Any = None) -> None:
        self._upload_dir = upload_dir
        self._bucket = bucket
        # Tests pass an in-memory fake; otherwise the shared client, created on first use.
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
        bucket = self._bucket
        try:
            await self._call(
                lambda client: (
                    client.bucket(bucket)
                    .blob(name)
                    .upload_from_string(content, content_type=media_type)
                )
            )
        except StorageUnavailable:
            # Google may have stored it before failing (e.g. a timeout); nothing records the
            # name, so remove it now or it could never be removed (storage review #5).
            await self._discard(bucket, name)
            raise
        return f"{_SCHEME}{bucket}/{name}"

    async def read(self, location: str) -> bytes | None:
        """The file's bytes, or None if it's gone (or the location isn't ours)."""
        if not location.startswith(_SCHEME):
            path = self._own_path(location)
            return await path.read_bytes() if path and await path.is_file() else None
        found = self._own_object(location)
        if found is None:
            return None
        bucket, name = found
        try:
            content: bytes = await self._call(
                lambda client: client.bucket(bucket).blob(name).download_as_bytes()
            )
        except _Missing:
            return None
        return content

    async def delete(self, location: str) -> None:
        """Remove the file; one that's already gone (or isn't ours) is left alone."""
        if not location.startswith(_SCHEME):
            path = self._own_path(location)
            if path is not None:
                await path.unlink(missing_ok=True)
            return
        found = self._own_object(location)
        if found is None:
            return
        bucket, name = found
        try:
            await self._call(lambda client: client.bucket(bucket).blob(name).delete())
        except _Missing:
            pass

    def _own_path(self, location: str) -> anyio.Path | None:
        """The path if it's inside the uploads folder, else None (storage review #4)."""
        path = Path(location).resolve()
        return anyio.Path(path) if path.is_relative_to(self._upload_dir.resolve()) else None

    def _own_object(self, location: str) -> tuple[str, str] | None:
        """(bucket, name) if it's an object in the configured bucket, else None."""
        bucket, _, name = location.removeprefix(_SCHEME).partition("/")
        if bucket != self._bucket or not name or ".." in name.split("/"):
            return None
        return bucket, name

    async def _call(self, operation: Callable[[Any], _T]) -> _T:
        """Run a client call in a worker thread; NotFound becomes _Missing, any other Google
        error StorageUnavailable, logging only its type (as the extractor does)."""

        def run() -> _T:
            client = self._client if self._client is not None else shared_client()
            return operation(client)

        try:
            return await anyio.to_thread.run_sync(run)
        except NotFound as missing:
            raise _Missing from missing
        except (GoogleAPIError, GoogleAuthError) as error:
            logger.warning("File storage failed: %s", type(error).__name__)
            raise StorageUnavailable("Couldn't reach file storage. Try again later.") from error

    async def _discard(self, bucket: str, name: str) -> None:
        try:
            await self._call(lambda client: client.bucket(bucket).blob(name).delete())
        except (_Missing, StorageUnavailable):
            pass


class _Missing(Exception):
    """The object isn't there (Google's NotFound)."""
