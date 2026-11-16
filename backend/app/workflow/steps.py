"""The guided run's document, validation and research steps (feature 007, task T009; amended
2026-11-16).

Plain code, no AI: the lead, "if our code doesn't need reasoning capability then no need to add
AI". Code always decided each step's facts (what's missing, which of 003's rules break, which
sections apply); the AI only reworded them, and was slow. Now each step's plain result is its
result. Nothing here confirms, edits, approves or calculates (Principle III).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.certificate_check import check_figures
from app.documents.models import DocType, FieldName
from app.documents.service import ConfirmedDocument
from app.rag.models import CorpusDocument, Passage

# Where a user uploads and confirms certificates (003's pages).
UPLOAD_PAGE = "/documents"
# The Ordinance's sections for each kind of income, in the order shown: how it is taxed, then
# who deducts tax from it (the same sections the AI used to find; 006's corpus has them).
SECTIONS: dict[DocType, tuple[str, ...]] = {
    DocType.SALARY_CERTIFICATE: ("§12(1)", "§149(1)"),
    DocType.BANK_PROFIT_CERTIFICATE: ("§7B(1)", "§151(1)"),
}
_ORDINANCE = "ito"  # the corpus id prefix of the Income Tax Ordinance


def label(document: ConfirmedDocument) -> str:
    """'Salary certificate uploaded 10 Nov 2026': how a certificate is named on the page."""
    name = (
        "Salary certificate"
        if document.doc_type is DocType.SALARY_CERTIFICATE
        else "Bank certificate"
    )
    return f"{name} uploaded {document.uploaded_at:%d %b %Y}" if document.uploaded_at else name


# ---- Document step (FR-003) ----


def document_step(documents: Sequence[ConfirmedDocument]) -> dict[str, Any]:
    """What's confirmed and what's missing; a confirmed salary certificate is required."""
    confirmed = ", ".join(label(d) for d in documents) or "none yet"
    if not any(d.doc_type is DocType.SALARY_CERTIFICATE for d in documents):
        return {
            "message": (
                f"Confirmed certificates: {confirmed}. You need at least one confirmed salary "
                f"certificate: upload and confirm it on the Documents page ({UPLOAD_PAGE}). "
                "A bank profit certificate is optional."
            ),
            "missing": ["salary_certificate"],
        }
    return {
        "message": (
            f"Confirmed certificates: {confirmed}. A bank profit certificate is optional; add "
            "one on the Documents page if you have one."
        ),
        "missing": [],
    }


# ---- Validation step (FR-004) ----


def validation_step(
    documents: Sequence[ConfirmedDocument], profile_tax_year: str
) -> dict[str, Any]:
    """003's rule checks on every confirmed certificate; issues warn, never block."""
    issues = []
    for document in documents:
        figures = {name: str(value) for name, value in document.values.items()}
        year = figures.pop(FieldName.TAX_YEAR, "")
        result = check_figures(document.doc_type, year, figures, profile_tax_year)
        issues += [
            {
                "document_id": str(document.id),
                "certificate": label(document),
                "field": field,
                "reason": reason,
            }
            for field, reason in result
        ]
    if not issues:
        message = "The figures on your confirmed certificates are consistent."
    else:
        lines = "; ".join(f"{i['certificate']}: {i['reason']}" for i in issues)
        message = f"Please check these before you approve: {lines}"
    return {"message": message, "issues": issues}


# ---- Research step (FR-005) ----


async def research_step(db: AsyncSession, documents: Sequence[ConfirmedDocument]) -> dict[str, Any]:
    """The Ordinance's sections for the user's income, each with its citation, read straight from
    006's corpus (no search: the sections are known)."""
    income = {d.doc_type for d in documents} or {DocType.SALARY_CERTIFICATE}
    wanted = [s for doc_type, sections in SECTIONS.items() if doc_type in income for s in sections]
    rows = (
        await db.execute(
            select(Passage, CorpusDocument)
            .join(CorpusDocument, CorpusDocument.id == Passage.document_id)
            .where(Passage.location.in_(wanted), Passage.document_id.startswith(_ORDINANCE))
        )
    ).all()
    found = {passage.location: (passage, document) for passage, document in rows}
    passages = [
        {
            "id": str(passage.id),
            "source": document.title,
            "kind": document.kind.value,
            "location": passage.location,
            "page": passage.page,
            "text": passage.text,
        }
        for passage, document in (found[s] for s in wanted if s in found)
    ]
    if not passages:
        return {"note": "No passages found in the FBR texts for your income.", "passages": []}
    return {
        "note": "These sections of the Income Tax Ordinance apply to your income.",
        "passages": passages,
    }
