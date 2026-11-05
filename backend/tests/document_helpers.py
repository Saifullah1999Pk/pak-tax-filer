"""Synthetic files and recorded extraction results for feature 003's tests.

Every file is generated on the fly; no real document is ever used (Principle V).
"""

import io

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
    model="claude-opus-5-5",
)
BANK_RESULT = ExtractionResult(
    fields={
        "tax_year": value("2025-26", label="Tax Year"),
        "profit_amount": value("120,000.00", label="Profit Paid"),
        "tax_withheld": value("24,000.00", label="Tax Withheld u/s 151"),
    },
    model="claude-opus-5-5",
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
