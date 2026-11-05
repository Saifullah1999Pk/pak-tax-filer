"""Document logic as plain functions (feature 003, tasks T013, T018, T022; research R9).

Routers only translate HTTP; everything here can be tested without it.
"""

import uuid
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.extraction.client import Extractor
from app.documents.extraction.normalise import parse_amount, parse_tax_year
from app.documents.extraction.rules import check_rules
from app.documents.extraction.schemas import ExtractedValue
from app.documents.models import (
    FIELDS_BY_TYPE,
    Confidence,
    DocStatus,
    DocType,
    Document,
    ExtractedField,
    FieldName,
)
from app.documents.uploads import CheckedFile


async def create_document(  # pylint: disable=too-many-arguments  # all keyword-only
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tax_year: str,
    doc_type: DocType,
    checked: CheckedFile,
    file_path: Path,
) -> Document:
    """Record an uploaded, checked and stored file."""
    document = Document(
        user_id=user_id,
        doc_type=doc_type,
        tax_year=tax_year,
        file_path=str(file_path),
        media_type=checked.media_type,
        page_count=checked.page_count,
        status=DocStatus.UPLOADED,
        fields=[],
    )
    db.add(document)
    await db.flush()
    return document


async def extract_document(
    db: AsyncSession, document: Document, extractor: Extractor, content: bytes
) -> Document:
    """Run extraction, normalise, apply the rules and save the fields (or the failure)."""
    document.status = DocStatus.EXTRACTING
    await db.flush()

    result = await extractor.extract(document.doc_type, content, document.media_type)

    document.model = result.model
    if result.failure_reason is not None:
        document.status = DocStatus.FAILED
        document.failure_reason = result.failure_reason
    else:
        document.fields = _build_fields(document.doc_type, document.tax_year, result.fields)
        document.status = DocStatus.NEEDS_REVIEW
        document.failure_reason = None
    await db.flush()
    return document


def _build_fields(
    doc_type: DocType, tax_year: str, found: Mapping[str, ExtractedValue]
) -> list[ExtractedField]:
    """One field per name the type has (extra keys ignored, FR-003), checked by the rules."""
    fields = [_field(name, found.get(name.value)) for name in FIELDS_BY_TYPE[doc_type]]
    apply_rules(doc_type, tax_year, fields)
    return fields


def _field(name: FieldName, raw: ExtractedValue | None) -> ExtractedField:
    """A stored field from what the extractor reported (missing means "not found")."""
    found = raw is not None and raw.value is not None
    field = ExtractedField(
        name=name,
        confidence=Confidence(raw.confidence) if raw is not None else Confidence.LOW,
        source_page=raw.page if raw is not None and found else None,
        source_label=raw.label if raw is not None and found else None,
        user_edited=False,
        confirmed=False,
    )
    if raw is None or raw.value is None:
        return field
    if name is FieldName.TAX_YEAR:
        field.text_value = parse_tax_year(raw.value)
        return field
    try:
        field.amount = parse_amount(raw.value)
    except ValueError:
        field.confidence = Confidence.LOW
        field.rule_reason = f"Couldn't read {raw.value!r} as an amount."
    return field


def field_value(field: ExtractedField) -> Decimal | str | None:
    """The field's value: an amount, the tax year text, or None if not found."""
    return field.text_value if field.name is FieldName.TAX_YEAR else field.amount


def apply_rules(doc_type: DocType, tax_year: str, fields: list[ExtractedField]) -> None:
    """Lower each field that breaks a rule to low confidence, adding the reason (FR-005)."""
    reasons = check_rules(doc_type, {f.name: field_value(f) for f in fields}, tax_year)
    for field in fields:
        if field.name in reasons:
            field.confidence = Confidence.LOW
            existing = f"{field.rule_reason} " if field.rule_reason else ""
            field.rule_reason = existing + reasons[field.name]


async def get_document(
    db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    """The user's document, or None if it doesn't exist or belongs to someone else."""
    document = await db.get(Document, document_id)
    if document is None or document.user_id != user_id:
        return None
    return document
