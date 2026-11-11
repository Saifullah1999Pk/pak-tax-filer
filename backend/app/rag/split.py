"""FBR's texts as citable passages (feature 006, task T005; research R2, FR-003).

Each passage keeps an exact, stable location ("§149(1)" in the Ordinance, "ch. 14.3" in the
filing manual) and the PDF page it starts on, so every citation points somewhere a reader can
check. Only the named sections and chapters are kept (FR-001); page furniture (running headers,
page numbers, footnotes) and the Ordinance's amendment markers ("5[7B.", "1[;]") are removed, so
they can never be quoted as law. Pure functions over page texts: no PDF, network or database.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

# A passage's ceiling, so search stays precise (research R2: 150-400 words).
MAX_WORDS = 400


@dataclass(frozen=True)
class Part:
    """A section ("149") or chapter ("14") to keep, and the PDF pages it lies on (inclusive)."""

    name: str
    pages: tuple[int, int]


@dataclass(frozen=True)
class RawPassage:
    """A piece of a source before it is embedded."""

    location: str
    page: int
    text: str


# ---- Ordinance ----

# "Chapter III – Tax on Taxable Income ____ \n \n48 \n": the running header and printed page.
_LAW_HEADER = re.compile(r"\A\s*Chapter [^\n]*\n(?:\s*\n)*\s*\d+\s*\n")
# Footnotes start after a line of spaces (a rule in the PDF) and run to the page's end.
_FOOTNOTES = re.compile(r"\n[ \t]{20,}\n.*\Z", re.S)
# Amendment markers: "5[" before amended text, its closing "]", and empty "2[  ]" leftovers.
_EMPTY_AMENDMENT = re.compile(r"\d{1,2}\[\s*\]")
_AMENDMENT_OPEN = re.compile(r"\d{1,2}\[")
# "12. Salary.— (1)", "149.  Salary. —", "7C. Tax on builders. —": a section heading.
_SECTION_HEADING = re.compile(
    r"(?m)^[ \t]*(\d{1,3}[A-Z]{0,2})\.[ \t]+[A-Z][^\n.]{1,80}\.[ \t]*[—–-]"
)
# A sub-section starts a line, or follows a heading's dash: " (2) Salary means". A footnote
# number may be stuck to it with no bracket ("1(3)  Where"); it is dropped.
_SUB_SECTION = re.compile(r"(?m)(?:^|[—–])[ \t]*(?:\d{1,2})?\((\d{1,2}[A-Z]{0,2})\)[ \t]")
# That footnote number, left at the end of the passage before.
_TRAILING_FOOTNOTE_NUMBER = re.compile(r"\s\d{1,2}$")


def _clean_law_page(text: str) -> str:
    text = _LAW_HEADER.sub("", text)
    text = _FOOTNOTES.sub("", text)
    text = _EMPTY_AMENDMENT.sub("", text)
    text = _AMENDMENT_OPEN.sub("", text)
    return text.replace("]", "")


def split_law(pages: dict[int, str], parts: list[Part]) -> list[RawPassage]:
    """The named Ordinance sections, one passage per sub-section (longer ones in pieces)."""
    passages: list[RawPassage] = []
    for part in parts:
        text, page_at = _join(pages, part.pages, _clean_law_page)
        start = _section_start(text, part.name)
        if start is None:
            continue
        end = _section_end(text, start)
        layout = _Layout(
            heading=_SUB_SECTION,
            location=partial(_sub_section_location, part.name),
            fallback=f"§{part.name}",
        )
        passages += _by_heading(_Span(text, start, end, page_at), layout)
    return passages


def _sub_section_location(section: str, sub_section: str) -> str:
    """ "§149(1)": the section and its sub-section."""
    return f"§{section}({sub_section})"


def _section_start(text: str, name: str) -> int | None:
    for match in _SECTION_HEADING.finditer(text):
        if match.group(1) == name:
            return match.start()
    return None


def _section_end(text: str, start: int) -> int:
    following = _SECTION_HEADING.search(text, start + 1)
    return following.start() if following else len(text)


# ---- Filing manual ----

_MANUAL_HEADER = re.compile(
    r"Normal IT Return – User Manual\s*|Document Version\s*:[^\n]*?Page \d+ of \d+\s*"
)
# "14.3. Reconciliation of Net Assets": a numbered heading one level down (not "4.1.1.").
_MANUAL_SUB = re.compile(r"(?m)^[ \t]*(\d{1,2}\.\d{1,2})\.?[ \t]+(?=\S)")
# Any top-level chapter heading ("15. Payment"), or chapter 14's part (b).
_MANUAL_CHAPTER = re.compile(r"(?m)^[ \t]*(\d{1,2})\.[ \t]+(?=\S)|^[ \t]*\(b\)[ \t]+Immoveable")


def _clean_manual_page(text: str) -> str:
    return _MANUAL_HEADER.sub("", text)


def split_guidance(pages: dict[int, str], parts: list[Part]) -> list[RawPassage]:
    """The named manual chapters, one passage per numbered heading (longer ones in pieces)."""
    passages: list[RawPassage] = []
    for part in parts:
        text, page_at = _join(pages, part.pages, _clean_manual_page)
        start = _chapter_start(text, part.name)
        if start is None:
            continue
        end = _chapter_end(text, start, part.name)
        layout = _Layout(
            heading=_MANUAL_SUB,
            location=lambda n: f"ch. {n}",
            fallback=f"ch. {part.name}",
            keep=partial(_in_chapter, part.name),
        )
        passages += _by_heading(_Span(text, start, end, page_at), layout)
    return passages


def _in_chapter(chapter: str, heading: str) -> bool:
    """ "14.3" belongs to chapter 14; "13.3" doesn't."""
    return heading.split(".")[0] == chapter


def _chapter_start(text: str, chapter: str) -> int | None:
    for match in _MANUAL_CHAPTER.finditer(text):
        if match.group(1) == chapter:
            return match.start()
    return None


def _chapter_end(text: str, start: int, chapter: str) -> int:
    for match in _MANUAL_CHAPTER.finditer(text, start + 1):
        if match.group(1) != chapter:
            return match.start()
    return len(text)


# ---- Shared ----


@dataclass(frozen=True)
class _Layout:
    """How one kind of document is cut: its sub-heading, how a heading becomes a location, the
    location for text before the first sub-heading, and which headings belong to the part."""

    heading: re.Pattern[str]
    location: Callable[[str], str]
    fallback: str
    keep: Callable[[str], bool] = field(default=lambda _name: True)


@dataclass(frozen=True)
class _Span:
    """A part's text [start, end) within its joined pages, and where each page starts."""

    text: str
    start: int
    end: int
    page_at: list[tuple[int, int]]


@dataclass
class _Segment:
    begin: int
    location: str
    body: str


def _join(
    pages: dict[int, str], span: tuple[int, int], clean: Callable[[str], str]
) -> tuple[str, list[tuple[int, int]]]:
    """The cleaned pages as one text, and where each page starts in it."""
    text = ""
    page_at: list[tuple[int, int]] = []
    for number in range(span[0], span[1] + 1):
        if number in pages:
            page_at.append((len(text), number))
            text += clean(pages[number]) + "\n"
    return text, page_at


def _page_of(offset: int, page_at: list[tuple[int, int]]) -> int:
    page = page_at[0][1]
    for start, number in page_at:
        if start <= offset:
            page = number
    return page


def _segments(span: _Span, layout: _Layout) -> list[_Segment]:
    """Cut the span at each sub-heading; text before the first takes the fallback location."""
    marks = [(span.start, layout.fallback)]
    for match in layout.heading.finditer(span.text, span.start, span.end):
        if layout.keep(match.group(1)):
            # Start at the number itself ("(2)", "14.3"), not at a dash or footnote before it.
            begin = match.start(1) - (1 if span.text[match.start(1) - 1] == "(" else 0)
            marks.append((begin, layout.location(match.group(1))))
    ends = [begin for begin, _ in marks[1:]] + [span.end]
    return [
        _Segment(begin, place, " ".join(span.text[begin:finish].split()))
        for (begin, place), finish in zip(marks, ends)
    ]


def _by_heading(span: _Span, layout: _Layout) -> list[RawPassage]:
    """The span as passages. Text before the first sub-heading that is only the part's own
    heading ("12. Salary.—") leads the first passage instead of standing alone."""
    segments = _segments(span, layout)
    if len(segments) > 1 and _only_heading(span.text[segments[0].begin : segments[1].begin]):
        segments[1] = _Segment(
            segments[0].begin, segments[1].location, f"{segments[0].body} {segments[1].body}"
        )
        segments = segments[1:]
    passages: list[RawPassage] = []
    for segment in segments:
        body = _TRAILING_FOOTNOTE_NUMBER.sub("", segment.body)
        if body:
            page = _page_of(segment.begin, span.page_at)
            passages += [RawPassage(segment.location, page, piece) for piece in _pieces(body)]
    return passages


def _only_heading(raw: str) -> bool:
    """The text before the first sub-heading is just the part's heading line ("12. Salary.—"
    with "(1)" on the same line), not a heading followed by its own text on later lines."""
    return "\n" not in raw.strip()


def _pieces(body: str) -> list[str]:
    """A long text in pieces of at most MAX_WORDS words, cut at sentence ends where possible."""
    words = body.split()
    if len(words) <= MAX_WORDS:
        return [body]
    sentences = re.split(r"(?<=[.;:])\s+", body)
    pieces: list[str] = []
    current: list[str] = []
    for sentence in sentences:
        for chunk in _at_most(sentence.split(), MAX_WORDS):
            if current and len(current) + len(chunk) > MAX_WORDS:
                pieces.append(" ".join(current))
                current = []
            current += chunk
    if current:
        pieces.append(" ".join(current))
    return pieces


def _at_most(words: list[str], size: int) -> list[list[str]]:
    return [words[i : i + size] for i in range(0, len(words), size)] or [[]]
