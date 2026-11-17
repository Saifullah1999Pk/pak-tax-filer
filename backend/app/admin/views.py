"""The admin area's pages (feature 011, tasks T018, T025, T029; FR-006 to FR-014; research R5-R7).

Every view is read-only: nothing can be created, edited, deleted, exported or imported (FR-012),
and fields are listed explicitly, so no secret column is ever shown (FR-013). Opening an account's
details records one audit entry (FR-016); list pages record nothing.
"""

from typing import Any

from sqlalchemy import func, select
from starlette.requests import Request
from starlette_admin import (
    BooleanField,
    ComputedField,
    CustomView,
    DateTimeField,
    EnumField,
    GridWidget,
    RequestAction,
    StatWidget,
    StringField,
)
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.widgets import BaseWidget

from app.admin import audit
from app.admin.models import AdminAuditEntry
from app.admin.overview import Limit, account_overview, dashboard_counts
from app.auth.models import User
from app.documents.models import DocStatus, DocType, Document
from app.rag.models import CorpusDocument, DocumentKind, Passage


class ReadOnlyView(ModelView):
    """A model view with nothing to create, edit, delete, export or import (FR-012)."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    def can_export(self, request: Request) -> bool:
        return False

    def can_import(self, request: Request) -> bool:
        return False


async def _email(request: Request, user_id: Any) -> str:
    """An account's email while it exists, else its id (FR-018)."""
    email = (
        await request.state.session.execute(select(User.email).where(User.id == user_id))
    ).scalar_one_or_none()
    return email or str(user_id)


class AccountView(ReadOnlyView):
    """Accounts: email, created, admin, disabled; search by email; the overview on the detail."""

    fields = [
        StringField("email"),
        DateTimeField("created_at"),
        BooleanField("is_admin"),
        DateTimeField("disabled_at"),
    ]
    searchable_fields = ["email"]
    fields_default_sort = [("created_at", True)]
    detail_template = "account_detail.html"

    async def find_by_pk(self, request: Request, pk: Any) -> Any:
        """The account; on its detail page, also its overview and one audit entry (R6)."""
        account = await super().find_by_pk(request, pk)
        if account is not None and request.state.action == RequestAction.DETAIL:
            db = request.state.session
            request.state.overview = await account_overview(db, account)
            await audit.record(db, request.state.admin_id, "view_account", account.id)
        return account


class OwnerEmail(ComputedField):
    """The document's owner, by email."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.user_id)


class DocumentView(ReadOnlyView):
    """Documents: type, status, tax year, uploaded, owner; never the file, no detail page."""

    fields = [
        EnumField("doc_type", enum=DocType),
        EnumField("status", enum=DocStatus),
        StringField("tax_year"),
        DateTimeField("created_at"),
        OwnerEmail("owner"),
    ]
    fields_default_sort = [("created_at", True)]

    def can_view_detail(self, request: Request) -> bool:
        return False


class PassageCount(ComputedField):
    """How many passages a corpus document has."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        count = (
            await request.state.session.execute(
                select(func.count()).select_from(Passage).where(Passage.document_id == obj.id)
            )
        ).scalar_one()
        return str(count)


class CorpusDocumentView(ReadOnlyView):
    """The law library: each FBR document and its passage count (FR-011)."""

    fields = [
        StringField("title"),
        EnumField("kind", enum=DocumentKind),
        DateTimeField("built_at"),
        PassageCount("passages"),
    ]


class AdminEmail(ComputedField):
    """The admin who acted, by email (or id once deleted)."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.admin_id)


class AccountEmail(ComputedField):
    """The account acted on, by email (or id once deleted)."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.target_user_id)


class AuditLogView(ReadOnlyView):
    """The audit log, newest first (FR-018)."""

    fields = [
        DateTimeField("at"),
        AdminEmail("admin"),
        StringField("action"),
        AccountEmail("account"),
    ]
    fields_default_sort = [("at", True)]

    def can_view_detail(self, request: Request) -> bool:
        return False


def _shown(limit: Limit) -> str:
    return f"{limit.used} of {limit.limit}"


async def dashboard(request: Request) -> BaseWidget:
    """The dashboard's stat tiles, from one read of the counts (FR-006)."""
    counts = await dashboard_counts(request.state.session)
    runs = ", ".join(f"{step}: {n}" for step, n in sorted(counts.runs_per_step.items())) or "none"
    tiles: list[tuple[str, str]] = [
        ("Taxpayer accounts", str(counts.taxpayers)),
        ("Profiles set up", str(counts.profiles)),
        ("Documents uploaded", str(counts.documents.get("uploaded", 0))),
        ("Documents confirmed", str(counts.documents.get("confirmed", 0))),
        ("Documents failed", str(counts.documents.get("failed", 0))),
        ("Guided runs by step", runs),
        ("Document readings today", _shown(counts.readings_app)),
        ("Most readings by one user today", _shown(counts.readings_busiest_user)),
        ("Ask questions today", _shown(counts.questions_app)),
        ("Most questions by one user this hour", _shown(counts.questions_busiest_user_hour)),
    ]
    return GridWidget(children=[StatWidget(title, _constant(value)) for title, value in tiles])


def _constant(value: str) -> Any:
    async def callback(_request: Request) -> str:
        return value

    return callback


def dashboard_view() -> CustomView:
    """The admin index page."""
    return CustomView(menu_label="Dashboard", icon="fa fa-gauge", widget=dashboard)


def model_views() -> list[ModelView]:
    """Every model view, in menu order."""
    return [
        AccountView(User, key="account", menu_label="Accounts", icon="fa fa-users"),
        DocumentView(Document, key="document", menu_label="Documents", icon="fa fa-file"),
        CorpusDocumentView(
            CorpusDocument, key="corpus-document", menu_label="Law library", icon="fa fa-book"
        ),
        AuditLogView(AdminAuditEntry, key="audit-log", menu_label="Audit log", icon="fa fa-list"),
    ]
