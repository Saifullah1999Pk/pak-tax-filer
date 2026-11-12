"""Checks before an answer is shown (feature 006, task T012; research R6, FR-005).

Plain code, after the model replies: the answer must cite at least one passage, every citation
must be a passage found for this question, and every number in what is shown (the answer and any
"not covered" note) must appear in a cited passage's text or location (Principle I).

A number is compared with what is attached to it: "10 million", "10million", "10m" and "10 mn"
are all 10 million and must match a cited "10 million"; a bare "10" can't stand for it; "§12(2B)"
must match a cited "(2B)"; "1st" and "1 st" are the same. A number in words with no digits ("one
million") passes only if a cited passage has the very same phrase. This lets an answer quote the
Ordinance's own "Rs. 10 million" and is as checkable as digits; 004/005's summaries, which
restate computed figures, still refuse every number word (app.explain.number_check).
"""

import re
from collections.abc import Sequence
from decimal import Decimal

from app.explain.number_check import NUMBER_WORDS
from app.rag.answer import ModelAnswer
from app.rag.search import RetrievedPassage

# A number in words, with any digits before it: "10 million", "one million", "twenty-five".
_WORD = NUMBER_WORDS.pattern
_NUMBER_PHRASE = re.compile(rf"(?:\d[\d,]*(?:\.\d+)?\s*)?{_WORD}(?:[\s-]+{_WORD})*", re.IGNORECASE)

# Scale words and their abbreviations, each read as one canonical word.
_SCALES = {
    "thousand": "thousand",
    "thousands": "thousand",
    "k": "thousand",
    "lakh": "lakh",
    "lakhs": "lakh",
    "lac": "lakh",
    "lacs": "lakh",
    "crore": "crore",
    "crores": "crore",
    "cr": "crore",
    "million": "million",
    "millions": "million",
    "m": "million",
    "mn": "million",
    "billion": "billion",
    "billions": "billion",
    "bn": "billion",
}
_ORDINALS = {"st", "nd", "rd", "th"}
# Digits, then letters stuck to them ("10m", "2B", "1st") or a scale word after a space.
_NUMBER = re.compile(
    rf"(\d[\d,]*(?:\.\d+)?)(?:([a-z]+)|\s+({'|'.join(sorted(_SCALES, key=len, reverse=True))})\b)?",
    re.IGNORECASE,
)


def checked_citations(
    reply: ModelAnswer, retrieved: Sequence[RetrievedPassage]
) -> list[RetrievedPassage] | None:
    """The cited passages if the reply passes every check; None if it must not be shown."""
    by_label = {f"P{number}": passage for number, passage in enumerate(retrieved, 1)}
    if not reply.citations or any(label not in by_label for label in reply.citations):
        return None
    cited = [by_label[label] for label in dict.fromkeys(reply.citations)]
    allowed = " ".join(f"{p.location} {p.text}" for p in cited)
    shown = " ".join(part for part in (reply.answer, reply.uncovered_part) if part)
    if not reply.answer.strip() or not _quotes_numbers_from(shown, allowed):
        return None
    return cited


def _number_phrases(text: str) -> set[str]:
    """Every number in words, lower-cased with single spaces: "Rs. 10  Million" -> "10 million"."""
    return {
        " ".join(match.group().lower().replace("-", " ").split())
        for match in _NUMBER_PHRASE.finditer(text)
    }


def _numbers(text: str) -> set[tuple[Decimal, str]]:
    """Every number with what is attached to it: "Rs. 10m" -> (10, "million"), "(2A)" -> (2, "a"),
    "1st" -> (1, ""), "5%" -> (5, "")."""
    found = set()
    for digits, stuck, spaced in _NUMBER.findall(text):
        suffix = (stuck or spaced).lower()
        suffix = "" if suffix in _ORDINALS else _SCALES.get(suffix, suffix)
        found.add((Decimal(digits.replace(",", "").rstrip(".")), suffix))
    return found


def _quotes_numbers_from(shown: str, allowed: str) -> bool:
    """True if every number (with its scale or letters) and every number phrase in words is in
    the allowed text."""
    return _numbers(shown) <= _numbers(allowed) and _number_phrases(shown) <= _number_phrases(
        allowed
    )


def written_in_english(question: str) -> bool:
    """True if most of the question's letters are Latin (A-Z), so it's searched; a question in
    Urdu script is out of scope (spec: English questions only). Gemini's embeddings match Urdu
    to the English passages, so the relevance cut-off alone wouldn't refuse it."""
    letters = [c for c in question if c.isalpha()]
    latin = sum(c.isascii() for c in letters)
    return bool(letters) and latin * 2 > len(letters)
