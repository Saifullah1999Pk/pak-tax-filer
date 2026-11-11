"""Checks before an answer is shown (feature 006, task T012; research R6, FR-005).

Plain code, after the model replies: the answer must cite at least one passage, every citation
must be a passage found for this question, and every number in what is shown (the answer and any
"not covered" note) must appear in a cited passage's text or location; numbers written as words
are refused. The shared number check from 004/005 does the number part (Principle I).
"""

from collections.abc import Sequence

from app.explain.number_check import uses_only_numbers_from
from app.rag.answer import ModelAnswer
from app.rag.search import RetrievedPassage


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
    if not reply.answer.strip() or not uses_only_numbers_from(shown, allowed):
        return None
    return cited
