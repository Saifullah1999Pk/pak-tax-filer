"""Checks before an answer is shown (feature 006, task T009; research R6, FR-005).

Plain code, after the model replies: every citation must be a passage found for the question,
and every number in what's shown must appear in a cited passage or its location (the shared
number check from 004/005). Anything else and the answer is never shown.
"""

import uuid

from app.rag.answer import ModelAnswer
from app.rag.checks import checked_citations
from app.rag.models import DocumentKind
from app.rag.search import RetrievedPassage


def passage(location: str, text: str) -> RetrievedPassage:
    """A retrieved passage from the Ordinance."""
    return RetrievedPassage(
        id=uuid.uuid4(),
        title="Income Tax Ordinance, 2001",
        kind=DocumentKind.LAW,
        location=location,
        page=327,
        text=text,
        score=0.8,
    )


RETRIEVED = [
    passage("§149(1)", "Every employer paying salary shall deduct tax at the average rate."),
    passage("§151(1)", "A bank paying profit on debt deducts tax at 20 percent."),
]


def answer(text: str, citations: list[str], uncovered: str | None = None) -> ModelAnswer:
    """A reply with these citations and no flags set."""
    return ModelAnswer(
        answer=text,
        citations=citations,
        not_covered=False,
        uncovered_part=uncovered,
        asks_own_tax_figure=False,
    )


def test_an_answer_citing_retrieved_passages_with_their_numbers_passes() -> None:
    """Fails if a faithful answer is thrown away, or its citations come back wrong."""
    reply = answer("Your bank deducts tax at 20 percent on profit (§151(1)).", ["P2"])

    assert checked_citations(reply, RETRIEVED) == [RETRIEVED[1]]


def test_a_citation_that_was_not_retrieved_fails() -> None:
    """Fails if the model can cite a passage nobody found for this question."""
    assert checked_citations(answer("Tax is deducted.", ["P1", "P7"]), RETRIEVED) is None


def test_a_number_not_in_a_cited_passage_fails() -> None:
    """Fails if a number from an uncited passage (or nowhere) could be shown."""
    reply = answer("Your employer deducts tax at 20 percent.", ["P1"])

    assert checked_citations(reply, RETRIEVED) is None


def test_a_section_number_must_be_in_a_cited_location() -> None:
    """Fails if the answer could name a section no cited passage is from."""
    assert checked_citations(answer("Under §149 the employer deducts.", ["P1"]), RETRIEVED)
    assert checked_citations(answer("Under §152 the employer deducts.", ["P1"]), RETRIEVED) is None


def test_a_number_written_as_a_word_fails() -> None:
    """Fails if "5 million" style amounts slip past the number check."""
    reply = answer("Employers deduct tax on salaries above five million.", ["P1"])

    assert checked_citations(reply, RETRIEVED) is None


def test_an_answer_with_no_citation_fails() -> None:
    """Fails if an uncited answer could be shown (Principle IV: every answer cites)."""
    assert checked_citations(answer("Employers deduct tax.", []), RETRIEVED) is None


def test_the_uncovered_part_is_checked_too() -> None:
    """Fails if a number could slip in through the "not covered" note, which is shown too."""
    reply = answer("Employers deduct tax.", ["P1"], uncovered="Rental income above 600000.")

    assert checked_citations(reply, RETRIEVED) is None
