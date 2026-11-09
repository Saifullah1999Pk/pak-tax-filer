"""Documents and their extracted fields, exactly as specs/003-document-extraction/data-model.md.

Only figures are stored: no names, CNICs, NTNs, account numbers or addresses (FR-003,
constitution Principle V). Amounts are numeric(14,2), never floats (Principle I).
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DocType(enum.StrEnum):
    """The two certificate types the user can upload (they pick one)."""

    SALARY_CERTIFICATE = "salary_certificate"
    BANK_PROFIT_CERTIFICATE = "bank_profit_certificate"


class DocStatus(enum.StrEnum):
    """uploaded → extracting → needs_review → confirmed; extracting → failed → extracting."""

    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class FieldName(enum.StrEnum):
    """Every field either document type can have (see FIELDS_BY_TYPE)."""

    TAX_YEAR = "tax_year"
    GROSS_SALARY = "gross_salary"
    TAXABLE_SALARY = "taxable_salary"
    TAX_DEDUCTED = "tax_deducted"
    PROFIT_AMOUNT = "profit_amount"
    TAX_WITHHELD = "tax_withheld"


class Confidence(enum.StrEnum):
    """How sure the extraction is; rule checks can lower a field to LOW."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# The fields each document type has, in display order (spec User Story 1, scenarios 2-3).
FIELDS_BY_TYPE: dict[DocType, tuple[FieldName, ...]] = {
    DocType.SALARY_CERTIFICATE: (
        FieldName.TAX_YEAR,
        FieldName.GROSS_SALARY,
        FieldName.TAXABLE_SALARY,
        FieldName.TAX_DEDUCTED,
    ),
    DocType.BANK_PROFIT_CERTIFICATE: (
        FieldName.TAX_YEAR,
        FieldName.PROFIT_AMOUNT,
        FieldName.TAX_WITHHELD,
    ),
}


def _pg_enum(enum_class: type[enum.StrEnum], name: str) -> Enum:
    """A PostgreSQL enum storing the members' values (e.g. 'needs_review'), not their names."""
    return Enum(enum_class, name=name, values_callable=lambda members: [m.value for m in members])


class Document(Base):
    """An uploaded certificate and where its extraction stands."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Deleted with the user.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[DocType] = mapped_column(_pg_enum(DocType, "doc_type"))
    # The uploader's profile tax year at upload (feature 002), e.g. "2025-26".
    tax_year: Mapped[str] = mapped_column(String)
    # Random name under UPLOAD_DIR/<user_id>/, never the uploaded file name (research R4).
    file_path: Mapped[str] = mapped_column(String)
    # application/pdf, image/jpeg or image/png.
    media_type: Mapped[str] = mapped_column(String)
    # 1-5; images count as 1.
    page_count: Mapped[int]
    status: Mapped[DocStatus] = mapped_column(_pg_enum(DocStatus, "doc_status"))
    # Set only when status is failed.
    failure_reason: Mapped[str | None] = mapped_column(String)
    # Model used for the last extraction.
    model: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class ExtractedField(Base):
    """One figure found on a document, with where it was found and how sure we are."""

    __tablename__ = "extracted_fields"
    __table_args__ = (UniqueConstraint("document_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Deleted with the document.
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    name: Mapped[FieldName] = mapped_column(_pg_enum(FieldName, "field_name"))
    # Money fields; null if not found. numeric(14,2), never a float (Principle I).
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    # tax_year only, normalised to the "2025-26" form.
    text_value: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[Confidence] = mapped_column(_pg_enum(Confidence, "confidence"))
    # 1-based; null if not found.
    source_page: Mapped[int | None]
    # The label as printed; null if not found.
    source_label: Mapped[str | None] = mapped_column(String)
    # Why a rule check lowered confidence; null otherwise.
    rule_reason: Mapped[str | None] = mapped_column(String)
    user_edited: Mapped[bool] = mapped_column(default=False)
    confirmed: Mapped[bool] = mapped_column(default=False)

    document: Mapped[Document] = relationship(back_populates="fields")


class ExtractionAttempt(Base):
    """One AI call for a user's document, kept only for the daily limit (FR-017, added 2026-11-09).

    Not linked to the document, so deleting a document can't reset the count.
    """

    __tablename__ = "extraction_attempts"
    __table_args__ = (
        Index("ix_extraction_attempts_user_id_attempted_at", "user_id", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Deleted with the user.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
