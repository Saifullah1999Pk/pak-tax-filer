"""The fingerprint of a run's inputs (feature 007, task T003; research R3).

A SHA-256 over the user's confirmed certificates (id, when confirmed, every value) and the
profile's tax year and ATL status. Step outputs and an approval are valid only while the
fingerprint they were made for equals the current one, so any change to the inputs (a
certificate added, deleted, re-confirmed or edited, or the profile changed) is noticed with one
comparison, without hooks into 003 or 002. Unconfirmed documents never count (Principle III).
"""

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.service import ConfirmedDocument, confirmed_documents
from app.profile.service import get_profile


def fingerprint(documents: Iterable[ConfirmedDocument], tax_year: str, on_atl: bool) -> str:
    """The inputs' fingerprint; the same inputs in any order give the same one."""
    certificates = sorted(
        (
            str(d.id),
            d.doc_type.value,
            d.confirmed_at.astimezone(UTC).isoformat() if d.confirmed_at else "",
            sorted((name.value, _canonical(value)) for name, value in d.values.items()),
        )
        for d in documents
    )
    payload = json.dumps(
        {"tax_year": tax_year, "on_atl": on_atl, "certificates": certificates},
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _canonical(value: Decimal | str) -> str:
    """One spelling per amount: 1800000, 1800000.00 and 1.8E+6 are all "1800000" (a value
    cached in the session and the same value read back from the database must match)."""
    return format(value.normalize(), "f") if isinstance(value, Decimal) else value


async def current_fingerprint(db: AsyncSession, user: User) -> str | None:
    """The fingerprint of the user's inputs now, or None without a profile."""
    profile = await get_profile(db, user)
    if profile is None:
        return None
    documents = await confirmed_documents(db, user.id, profile.tax_year)
    return fingerprint(documents, profile.tax_year, profile.on_atl)
