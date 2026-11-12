"""The agents' tools (feature 007, task T005; contracts/workflow-api.md "Agent tools").

Read-only by construction (FR-010): exactly four tools, bound to one user's run, none of which
writes, confirms, approves or calculates. They call the app's own functions: 003's confirmed
documents and rules (through the check shared with 006's MCP tool) and 006's search.
"""

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.certificate_check import check_figures
from app.documents.models import DocType, FieldName
from app.documents.service import confirmed_documents
from app.rag.embed import Embedder
from app.rag.search import RetrievedPassage, search

# Where a user uploads and confirms certificates (003's pages).
UPLOAD_PAGE = "/documents"

TOOL_NAMES = frozenset(
    {
        "list_confirmed_documents",
        "validate_salary_information",
        "check_bank_certificate",
        "search_tax_documents",
    }
)
# Which agent may call which tool (research R4).
AGENT_TOOLS: dict[str, frozenset[str]] = {
    "document": frozenset({"list_confirmed_documents"}),
    "validation": frozenset({"validate_salary_information", "check_bank_certificate"}),
    "research": frozenset({"search_tax_documents"}),
}


@dataclass
class Toolbox:
    """One run's tools. `found` keeps every passage search returned, in order, so the research
    agent's citations (P1, P2, ...) can be checked against exactly these."""

    # A fresh session per tool call (backend review M3): a step that times out cancels only
    # that session's query, never the request's own session.
    sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    user_id: uuid.UUID
    profile_tax_year: str
    embedder: Embedder
    found: list[RetrievedPassage] = field(default_factory=list)

    async def list_confirmed_documents(self) -> dict[str, Any]:
        """The user's confirmed certificates for the profile's tax year (type, label, when
        confirmed), and the page where more are uploaded."""
        async with self.sessions() as db:
            documents = await confirmed_documents(db, self.user_id, self.profile_tax_year)
        return {
            "certificates": [
                {
                    "id": str(d.id),
                    "type": d.doc_type.value,
                    "label": _label(d.doc_type, d.uploaded_at),
                    "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
                }
                for d in documents
            ],
            "upload_page": UPLOAD_PAGE,
        }

    async def validate_salary_information(
        self, tax_year: str, gross_salary: str, taxable_salary: str, tax_deducted: str
    ) -> dict[str, Any]:
        """003's rule checks on a salary certificate's figures; never a tax figure."""
        return _result(
            check_figures(
                DocType.SALARY_CERTIFICATE,
                tax_year,
                {
                    FieldName.GROSS_SALARY: gross_salary,
                    FieldName.TAXABLE_SALARY: taxable_salary,
                    FieldName.TAX_DEDUCTED: tax_deducted,
                },
                self.profile_tax_year,
            )
        )

    async def check_bank_certificate(
        self, tax_year: str, profit_amount: str, tax_withheld: str
    ) -> dict[str, Any]:
        """003's rule checks on a bank profit certificate's figures; never a tax figure."""
        return _result(
            check_figures(
                DocType.BANK_PROFIT_CERTIFICATE,
                tax_year,
                {FieldName.PROFIT_AMOUNT: profit_amount, FieldName.TAX_WITHHELD: tax_withheld},
                self.profile_tax_year,
            )
        )

    async def search_tax_documents(self, query: str) -> dict[str, Any]:
        """006's search: up to five passages with their citation and a label (P1, P2, ...) to
        cite them by, or none and not_covered below the relevance cut-off."""
        async with self.sessions() as db:
            result = await search(db, self.embedder, query)
        if not result.covered:
            return {"passages": [], "not_covered": True}
        passages = []
        for passage in result.passages:
            if passage.id not in {p.id for p in self.found}:
                self.found.append(passage)
            number = next(i for i, p in enumerate(self.found, 1) if p.id == passage.id)
            passages.append(
                {
                    "label": f"P{number}",
                    "source": passage.title,
                    "kind": passage.kind.value,
                    "location": passage.location,
                    "page": passage.page,
                    "text": passage.text,
                }
            )
        return {"passages": passages, "not_covered": False}


def _label(doc_type: DocType, uploaded_at: Any) -> str:
    name = "Salary certificate" if doc_type is DocType.SALARY_CERTIFICATE else "Bank certificate"
    return f"{name} uploaded {uploaded_at:%d %b %Y}" if uploaded_at else name


def _result(issues: list[tuple[str, str]]) -> dict[str, Any]:
    return {"ok": not issues, "issues": [{"field": f, "reason": r} for f, r in issues]}
