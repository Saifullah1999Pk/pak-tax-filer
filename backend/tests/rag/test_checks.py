"""Checks before an answer is shown (feature 006, task T009; research R6, FR-005).

Plain code, after the model replies: every citation must be a passage found for the question,
and every number in what's shown must appear in a cited passage or its location (the shared
number check from 004/005). Anything else and the answer is never shown.
"""

import uuid

import pytest

from app.rag.answer import ModelAnswer
from app.rag.checks import checked_citations, written_in_english
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


@pytest.mark.parametrize(
    ("question", "english"),
    [
        ("Is my bonus taxed?", True),
        ("Is my bonus taxed under §12(2)? 2025-26", True),
        ("Kya meri salary par tax lagta hai?", True),  # Roman Urdu: Latin letters, sent on
        ("کیا مجھے اپنی تنخواہ پر ٹیکس دینا ہوگا؟", False),
        ("کیا salary پر ٹیکس ہے؟", False),  # mostly Urdu script
        ("12345 ?", False),  # no words at all
    ],
)
def test_only_questions_in_english_letters_are_searched(question: str, english: bool) -> None:
    """Fails if a question in Urdu script reaches search: the sources are in English, and
    Gemini's embeddings match Urdu to English passages, so the cut-off alone doesn't refuse it
    (eval run, 2026-11-11: 0.691, above most in-scope questions)."""
    assert written_in_english(question) is english


PENSION = [
    passage(
        "§12(2A)",
        "Pension exceeding Rs. 10 million in a tax year is charged at 5%. Loans not exceeding "
        "one million rupees are excluded.",
    )
]


@pytest.mark.parametrize(
    ("text", "passes"),
    [
        ("Pension above Rs. 10 million is charged at 5%.", True),  # quoted as the law writes it
        ("Loans up to one million rupees are excluded.", True),
        ("Pension above Rs. 12 million is charged at 5%.", False),  # 12 isn't in the passage
        ("Loans up to two million rupees are excluded.", False),  # a phrase the law doesn't use
        ("Pension above 10 lakh is charged at 5%.", False),
        ("Pension above Rs. 10,000,000 is charged at 5%.", False),  # converted, not quoted
    ],
)
def test_a_number_in_words_passes_only_as_a_cited_passage_writes_it(
    text: str, passes: bool
) -> None:
    """Fails if the law's own "Rs. 10 million" is refused (eval run, 2026-11-11: 2 of 30
    answers), or if a number phrase the cited passage doesn't contain can slip through."""
    assert (checked_citations(answer(text, ["P1"]), PENSION) is not None) is passes


@pytest.mark.parametrize(
    ("text", "passes"),
    [
        ("Rs. 10million is exempt.", False),  # glued: still 10 million, not in the passage
        ("Rs. 10m is exempt.", False),  # abbreviated
        ("Rs. 10 mn is exempt.", False),
        ("Rs. 10 is exempt.", False),  # the scale word dropped
        ("Rs. 10 thousand is exempt.", True),
        ("Rs. 10k is exempt.", True),  # the same figure, abbreviated
    ],
)
def test_a_number_is_checked_with_its_scale(text: str, passes: bool) -> None:
    """Fails if "10m", "10million" or a bare "10" passes because the cited passage has a 10 with
    another scale ("Rs. 10 thousand"): each is a figure it doesn't contain (backend review M1)."""
    cited = [passage("§12(9)", "Amounts up to Rs. 10 thousand are exempt.")]

    assert (checked_citations(answer(text, ["P1"]), cited) is not None) is passes


def test_a_section_letter_must_match_the_cited_location() -> None:
    """Fails if §12(2B) passes when only §12(2A) is cited (backend review L8)."""
    cited = [passage("§12(2A)", "In case of pension, the pension shall be charged to tax.")]

    assert checked_citations(answer("Under §12(2A), pension is taxed.", ["P1"]), cited)
    assert checked_citations(answer("Under §12(2B), pension is taxed.", ["P1"]), cited) is None


def test_an_ordinal_written_apart_or_together_is_the_same_number() -> None:
    """Fails if "1st" is refused when the passage's PDF text reads "1 st" (seen in §13(7))."""
    cited = [passage("§13(7)", "Where a loan is made, on or after the 1 st day of July, 2002.")]

    assert checked_citations(answer("Loans made on or after 1st July, 2002.", ["P1"]), cited)
