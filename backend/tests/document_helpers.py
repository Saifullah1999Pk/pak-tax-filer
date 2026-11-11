"""Synthetic files and recorded extraction results for feature 003's tests.

Every file is generated on the fly; no real document is ever used (Principle V).
"""

import io

from google.api_core.exceptions import NotFound
from httpx2 import AsyncClient, Response
from PIL import Image
from pypdf import PdfWriter

from app.documents.extraction.client import ExtractionResult
from app.documents.extraction.schemas import ExtractedValue

PROFILE_YEAR = "2025-26"


def make_pdf(pages: int = 1, password: str | None = None) -> bytes:
    """A synthetic PDF with blank pages, optionally encrypted."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if password is not None:
        writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_image(image_format: str) -> bytes:
    """A small synthetic PNG or JPEG."""
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(out, format=image_format)
    return out.getvalue()


def value(printed: str | None, confidence: str = "high", label: str = "Label") -> ExtractedValue:
    """One field as the extractor would report it."""
    found = printed is not None
    return ExtractedValue.model_validate(
        {
            "value": printed,
            "confidence": confidence,
            "page": 1 if found else None,
            "label": label if found else None,
        }
    )


SALARY_RESULT = ExtractionResult(
    fields={
        "tax_year": value("2025-26", label="Tax Year"),
        "gross_salary": value("Rs. 1,800,000", label="Gross Salary"),
        "taxable_salary": value("1,700,000", "medium", label="Taxable Salary"),
        "tax_deducted": value("95,000/-", label="Income Tax Deducted"),
    },
    model="gemini-3.8-flash",
)
BANK_RESULT = ExtractionResult(
    fields={
        "tax_year": value("2025-26", label="Tax Year"),
        "profit_amount": value("120,000.00", label="Profit Paid"),
        "tax_withheld": value("24,000.00", label="Tax Withheld u/s 151"),
    },
    model="gemini-3.8-flash",
)


async def upload(
    client: AsyncClient,
    content: bytes,
    filename: str = "certificate.pdf",
    doc_type: str = "salary_certificate",
) -> Response:
    """POST /api/documents as the browser's form would."""
    return await client.post(
        "/api/documents",
        files={"file": (filename, content, "application/octet-stream")},
        data={"doc_type": doc_type},
    )


class FakeBucketClient:
    """google.cloud.storage.Client's shape, in memory (feature 003, FR-018): no test reaches
    Google. Set `fail` to an exception (e.g. google.api_core.exceptions.Forbidden) to make every
    call raise it, as when the VM's identity lacks access or Google is down."""

    def __init__(self) -> None:
        self.buckets: dict[str, dict[str, tuple[bytes, str]]] = {}
        self.fail: Exception | None = None
        # Raised after an upload is stored, as when Google keeps it but the reply times out.
        self.fail_after_store: Exception | None = None

    def bucket(self, name: str) -> "_FakeBucket":
        """The bucket with this name."""
        return _FakeBucket(self, self.buckets.setdefault(name, {}))


class _FakeBucket:  # pylint: disable=too-few-public-methods
    def __init__(self, client: FakeBucketClient, store: dict[str, tuple[bytes, str]]) -> None:
        self.client = client
        self.store = store

    def blob(self, name: str) -> "_FakeBlob":
        """The object with this name (it may not exist yet)."""
        return _FakeBlob(self.client, self.store, name)


class _FakeBlob:
    def __init__(
        self, client: FakeBucketClient, store: dict[str, tuple[bytes, str]], name: str
    ) -> None:
        self.client = client
        self.store = store
        self.name = name

    def _maybe_fail(self) -> None:
        if self.client.fail is not None:
            raise self.client.fail

    def upload_from_string(self, data: bytes, content_type: str) -> None:
        """Store the bytes and their media type."""
        self._maybe_fail()
        self.store[self.name] = (data, content_type)
        if self.client.fail_after_store is not None:
            raise self.client.fail_after_store

    def download_as_bytes(self) -> bytes:
        """The stored bytes, or NotFound like the real client."""
        self._maybe_fail()
        if self.name not in self.store:
            raise NotFound(self.name)  # type: ignore[no-untyped-call]  # google-api-core is untyped
        return self.store[self.name][0]

    def delete(self) -> None:
        """Remove the object, or NotFound like the real client."""
        self._maybe_fail()
        if self.store.pop(self.name, None) is None:
            raise NotFound(self.name)  # type: ignore[no-untyped-call]  # google-api-core is untyped
