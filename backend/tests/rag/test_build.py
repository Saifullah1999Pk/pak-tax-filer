"""Building the corpus (feature 006, task T007; research R1, FR-002).

Downloads and PDF reading are replaced by fakes, so no network or real PDF is needed; the
database is the migrated test database.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.build import BuildError, Source, build_corpus
from app.rag.embed import EmbeddingError, FakeEmbedder
from app.rag.models import CorpusDocument, DocumentKind, Passage
from app.rag.split import Part

pytestmark = pytest.mark.anyio

LAW_FILE = b"%PDF fake ordinance"
LAW_PAGES = {
    58: "5[7B.  Tax on profit on debt. —(1) A tax is imposed on profit on debt.\n"
    " (2) The rate is in the First Schedule.\n"
    "3[7C. Tax on builders. — (1) Builders pay tax.\n"
}
GUIDE_FILE = b"%PDF fake manual"
GUIDE_PAGES = {
    80: "14. (a) Wealth Statement \nList assets and liabilities.\n"
    "14.3. Reconciliation of Net Assets \nInflows explain the change.\n"
}


def source(doc_id: str, content: bytes, kind: DocumentKind, part: Part) -> Source:
    """A source whose checksum matches `content`."""
    return Source(
        id=doc_id,
        title=doc_id.title(),
        kind=kind,
        url=f"https://fbr.example/{doc_id}.pdf",
        sha256=hashlib.sha256(content).hexdigest(),
        parts=(part,),
    )


SOURCES = [
    source("law", LAW_FILE, DocumentKind.LAW, Part("7B", (58, 58))),
    source("guide", GUIDE_FILE, DocumentKind.GUIDANCE, Part("14", (80, 80))),
]
FILES = {"https://fbr.example/law.pdf": LAW_FILE, "https://fbr.example/guide.pdf": GUIDE_FILE}
PAGES = {LAW_FILE: LAW_PAGES, GUIDE_FILE: GUIDE_PAGES}


class Downloads:
    """A fake downloader that records each URL it fetches."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.fetched: list[str] = []

    async def __call__(self, url: str) -> bytes:
        self.fetched.append(url)
        return self.files[url]


def read_pages(path: Path, numbers: set[int]) -> dict[int, str]:
    """A fake PDF reader: the page texts made up for this file's contents."""
    pages = PAGES[path.read_bytes()]
    return {n: pages[n] for n in numbers if n in pages}


async def an_old_corpus(db: AsyncSession) -> None:
    """A corpus from an earlier build, which a failed build must leave alone."""
    db.add(
        CorpusDocument(
            id="old",
            title="Old",
            kind=DocumentKind.LAW,
            url="https://fbr.example/old.pdf",
            sha256="0" * 64,
            built_at=datetime.now(UTC),
        )
    )
    await db.flush()
    db.add(Passage(document_id="old", location="§1(1)", page=1, text="Old.", embedding=[1.0] * 768))
    await db.flush()


async def locations(db: AsyncSession) -> list[str]:
    """The stored passages' locations, sorted."""
    return sorted((await db.scalars(select(Passage.location))).all())


async def test_a_build_replaces_the_whole_corpus(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if old passages survive a build, or new ones lack their location or embedding."""
    await an_old_corpus(db)

    await build_corpus(db, SOURCES, tmp_path, Downloads(FILES), read_pages, FakeEmbedder())

    assert await locations(db) == sorted(["ch. 14", "ch. 14.3", "§7B(1)", "§7B(2)"])
    documents = (await db.scalars(select(CorpusDocument.id).order_by(CorpusDocument.id))).all()
    assert documents == ["guide", "law"]
    stored = (await db.scalars(select(Passage).where(Passage.location == "§7B(1)"))).one()
    assert len(stored.embedding) == 768
    assert stored.page == 58


async def test_a_changed_file_stops_the_build_and_keeps_the_old_corpus(
    db: AsyncSession, tmp_path: Path
) -> None:
    """Fails if a file FBR changed silently could reach the corpus (FR-002)."""
    await an_old_corpus(db)
    changed = {**FILES, "https://fbr.example/law.pdf": b"%PDF a different ordinance"}

    with pytest.raises(BuildError, match="law"):
        await build_corpus(db, SOURCES, tmp_path, Downloads(changed), read_pages, FakeEmbedder())

    assert await locations(db) == ["§1(1)"]


async def test_failed_embeddings_keep_the_old_corpus(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if a build could store part of the corpus when Gemini fails midway."""
    await an_old_corpus(db)

    class Failing(FakeEmbedder):
        """Gemini failing midway through the build."""

        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingError("down")

    with pytest.raises(BuildError):
        await build_corpus(db, SOURCES, tmp_path, Downloads(FILES), read_pages, Failing())

    assert await locations(db) == ["§1(1)"]


async def test_a_cached_file_is_reused_and_a_download_is_cached(
    db: AsyncSession, tmp_path: Path
) -> None:
    """Fails if every build re-downloads FBR's files, or a download isn't kept for next time."""
    (tmp_path / "law.pdf").write_bytes(LAW_FILE)
    downloads = Downloads(FILES)

    await build_corpus(db, SOURCES, tmp_path, downloads, read_pages, FakeEmbedder())

    assert downloads.fetched == ["https://fbr.example/guide.pdf"]
    assert (tmp_path / "guide.pdf").read_bytes() == GUIDE_FILE


async def test_a_corrupt_cached_file_is_downloaded_again(db: AsyncSession, tmp_path: Path) -> None:
    """Fails if a damaged cached copy blocks the build instead of being replaced."""
    (tmp_path / "law.pdf").write_bytes(b"half a download")
    downloads = Downloads(FILES)

    await build_corpus(db, SOURCES, tmp_path, downloads, read_pages, FakeEmbedder())

    assert "https://fbr.example/law.pdf" in downloads.fetched
    count = (await db.execute(select(func.count()).select_from(Passage))).scalar_one()
    assert count == 4


def test_the_real_sources_file_loads() -> None:
    """Fails if sources.yaml can't be read into the two FBR sources the spec names."""
    from app.rag.build import load_sources  # pylint: disable=import-outside-toplevel

    sources = load_sources()
    assert [(s.id, s.kind) for s in sources] == [
        ("ito-2001-2025-07-31", DocumentKind.LAW),
        ("pral-itr-manual-2026", DocumentKind.GUIDANCE),
    ]
    assert [p.name for p in sources[0].parts] == ["7B", "12", "13", "149", "151"]
    assert all(len(s.sha256) == 64 for s in sources)
