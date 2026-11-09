"""Checking an uploaded certificate (feature 003, task T012, research R4); storage.py keeps it.

Every check runs before anything is sent to the AI (spec US1 scenario 4).
"""

import io
from dataclasses import dataclass
from pathlib import Path

from fastapi import status
from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 5
_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
# The file's real type comes from its first bytes, never from its name.
_SIGNATURES = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)


class UploadRefused(Exception):
    """A file that breaks an upload rule; carries the HTTP status and a message for the user."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class CheckedFile:
    """An accepted file's real type, the extension it is stored with, and its page count."""

    media_type: str
    extension: str
    page_count: int


def check_file(filename: str, content: bytes) -> CheckedFile:
    """Accept a PDF, JPG or PNG of at most 10 MB and 5 pages; raise UploadRefused otherwise."""
    if len(content) > MAX_BYTES:
        raise UploadRefused(status.HTTP_413_CONTENT_TOO_LARGE, "The file is over 10 MB.")
    wrong_type = UploadRefused(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, JPG or PNG files can be uploaded."
    )
    if Path(filename).suffix.lower() not in _EXTENSIONS:
        raise wrong_type
    for signature, media_type, extension in _SIGNATURES:
        if content.startswith(signature):
            break
    else:
        raise wrong_type
    pages = _pdf_page_count(content) if media_type == "application/pdf" else 1
    return CheckedFile(media_type=media_type, extension=extension, page_count=pages)


def _pdf_page_count(content: bytes) -> int:
    """The PDF's page count, refusing encrypted, unreadable or over-long files."""
    unreadable = UploadRefused(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "The PDF couldn't be read. Try another copy."
    )
    try:
        reader = PdfReader(io.BytesIO(content))
        encrypted = reader.is_encrypted
        pages = 0 if encrypted else len(reader.pages)
    except (PyPdfError, ValueError, KeyError, TypeError, OSError) as exc:
        raise unreadable from exc
    if encrypted:
        raise UploadRefused(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The PDF is password-protected. Upload a copy without a password.",
        )
    if pages == 0:
        raise unreadable
    if pages > MAX_PAGES:
        raise UploadRefused(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"The PDF has {pages} pages; the limit is {MAX_PAGES} pages.",
        )
    return pages
