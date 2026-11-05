"""/api/documents (feature 003, tasks T014, T018, T022).

Contract: specs/003-document-extraction/contracts/documents-api.md. Every endpoint is the
owner's only: other users' documents are 404, never 403 (docs/api-conventions.md).
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.documents.extraction.client import ClaudeExtractor, Extractor
from app.documents.models import (
    FIELDS_BY_TYPE,
    Confidence,
    DocStatus,
    DocType,
    Document,
    ExtractedField,
    FieldName,
)
from app.documents.service import (
    DocumentLocked,
    FieldNotOnDocument,
    IncompleteDocument,
    confirm_document,
    create_document,
    delete_document,
    edit_field,
    extract_document,
    field_value,
    get_document,
    list_documents,
    remove_stored_file,
    retry_extraction,
)
from app.documents.uploads import MAX_BYTES, UploadRefused, check_file, save_file
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.settings import get_settings

router = APIRouter(prefix="/api/documents", tags=["documents"])

NOT_FOUND = "Document not found."


def get_extractor() -> Extractor:
    """The extractor the app uses (tests replace it with a FakeExtractor)."""
    settings = get_settings()
    return ClaudeExtractor(
        api_key=settings.anthropic_api_key,
        model=settings.extraction_model,
        effort=settings.extraction_effort,
    )


def get_upload_dir() -> Path:
    """Where uploaded files are stored (tests use a temporary folder)."""
    return get_settings().upload_dir


CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


class FieldOut(BaseModel):
    """One extracted figure as the review page shows it."""

    name: FieldName
    # A decimal string for amounts, "2025-26" for tax_year, null if not found.
    value: str | None
    confidence: Confidence
    source_page: int | None
    source_label: str | None
    rule_reason: str | None
    user_edited: bool
    confirmed: bool


class DocumentSummary(BaseModel):
    """A document in the list, without its figures."""

    id: uuid.UUID
    doc_type: DocType
    tax_year: str
    status: DocStatus
    failure_reason: str | None
    # application/pdf, image/jpeg or image/png: how the review page shows the original.
    media_type: str
    page_count: int
    created_at: datetime
    confirmed_at: datetime | None


class DocumentOut(DocumentSummary):
    """A document and its fields (contract "Document object")."""

    fields: list[FieldOut]


class FieldEdit(BaseModel):
    """PATCH body: a new value, a confirmation, or both. Unknown keys are refused."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    confirmed: StrictBool | None = None


def field_out(field: ExtractedField) -> FieldOut:
    """The API form of a field; amounts as decimal strings, never floats."""
    value = field_value(field)
    return FieldOut(
        name=field.name,
        value=None if value is None else str(value),
        confidence=field.confidence,
        source_page=field.source_page,
        source_label=field.source_label,
        rule_reason=field.rule_reason,
        user_edited=field.user_edited,
        confirmed=field.confirmed,
    )


def document_out(document: Document) -> DocumentOut:
    """The API form of a document, its fields in the type's display order."""
    order = FIELDS_BY_TYPE[document.doc_type]
    fields = sorted(document.fields, key=lambda field: order.index(field.name))
    return DocumentOut(
        id=document.id,
        doc_type=document.doc_type,
        tax_year=document.tax_year,
        status=document.status,
        failure_reason=document.failure_reason,
        media_type=document.media_type,
        page_count=document.page_count,
        created_at=document.created_at,
        confirmed_at=document.confirmed_at,
        fields=[field_out(field) for field in fields],
    )


async def owned_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Document:
    """The caller's document, or 404 if it doesn't exist or isn't theirs."""
    document = await get_document(db, user.id, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return document


async def locked_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Document:
    """The caller's document, row-locked for a state change; 404 if it isn't theirs."""
    document = await get_document(db, user.id, document_id, for_update=True)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return document


OwnedDocument = Annotated[Document, Depends(owned_document)]
LockedDocument = Annotated[Document, Depends(locked_document)]
ExtractorDep = Annotated[Extractor, Depends(get_extractor)]


def _summary(document: Document) -> DocumentSummary:
    return DocumentSummary.model_validate(document_out(document).model_dump(exclude={"fields"}))


@router.get("")
async def read_documents(user: CurrentUser, db: DbSession) -> list[DocumentSummary]:
    """The caller's documents, newest first, without their figures."""
    return [_summary(document) for document in await list_documents(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    user: CurrentUser,
    profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    db: DbSession,
    extractor: ExtractorDep,
    upload_dir: Annotated[Path, Depends(get_upload_dir)],
    file: UploadFile,
    doc_type: Annotated[DocType, Form()],
) -> DocumentOut:
    """Check, store and extract a certificate; the tax year is the profile's (feature 002)."""
    content = await file.read(MAX_BYTES + 1)
    try:
        checked = check_file(file.filename or "", content)
    except UploadRefused as refused:
        raise HTTPException(refused.status_code, refused.detail) from refused
    path = await save_file(upload_dir, user.id, content, checked.extension)
    try:
        document = await create_document(
            db,
            user_id=user.id,
            tax_year=profile.tax_year,
            doc_type=doc_type,
            checked=checked,
            file_path=path,
        )
        await extract_document(db, document, extractor, content)
        await db.commit()
    except BaseException:
        # Nothing records the file now, so delete could never remove it: remove it here.
        await remove_stored_file(path)
        raise
    return document_out(document)


@router.get("/{document_id}")
async def read_document(document: OwnedDocument) -> DocumentOut:
    """One of the caller's documents with its fields."""
    return document_out(document)


@router.get("/{document_id}/file")
async def read_document_file(document: OwnedDocument) -> FileResponse:
    """The original file, for the review page."""
    if not Path(document.file_path).is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The stored file is missing.")
    return FileResponse(document.file_path, media_type=document.media_type)


@router.patch("/{document_id}/fields/{name}", dependencies=[Depends(require_json)])
async def update_field(
    document: LockedDocument, name: str, body: FieldEdit, db: DbSession
) -> FieldOut:
    """Edit and/or confirm one field; the rules run again after an edit."""
    try:
        field_name = FieldName(name)
    except ValueError as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found.") from unknown
    try:
        field = await edit_field(
            db, document, field_name, value=body.value, confirmed=body.confirmed
        )
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    except FieldNotOnDocument as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found.") from missing
    except ValueError as invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    await db.commit()
    return field_out(field)


@router.post("/{document_id}/confirm", dependencies=[Depends(require_json)])
async def confirm(document: LockedDocument, db: DbSession) -> DocumentOut:
    """Confirm the document; only then can other features use its figures."""
    try:
        await confirm_document(db, document)
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    except IncompleteDocument as incomplete:
        detail = "Confirm or fill in these fields first: " + ", ".join(incomplete.names) + "."
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from incomplete
    await db.commit()
    return document_out(document)


@router.post("/{document_id}/retry", dependencies=[Depends(require_json)])
async def retry(document: LockedDocument, db: DbSession, extractor: ExtractorDep) -> DocumentOut:
    """Re-run a failed extraction."""
    try:
        await retry_extraction(db, document, extractor)
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    await db.commit()
    return document_out(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_json)],
)
async def delete(document: LockedDocument, db: DbSession) -> Response:
    """Delete the document, its fields and its stored file."""
    path = await delete_document(db, document)
    await db.commit()
    await remove_stored_file(path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
