"""The retrieval eval's gate, with scripted searches (feature 006, task T021; research R10).

The real run needs GEMINI_API_KEY and a built corpus (T022); this checks the scoring and that
the run fails when retrieval is bad, so the CI job can't pass on a broken search.
"""

import asyncio
import random
import uuid
from pathlib import Path

import pytest
from evals.retrieval.run import (
    QUESTIONS,
    Outcome,
    Question,
    best_cutoff,
    load_questions,
    main,
    matches,
    run,
)

from app.rag.models import DocumentKind
from app.rag.search import RetrievedPassage
from app.settings import load_settings

DB = "postgresql+asyncpg://user:pass@db:5432/example"
NO_KEY = load_settings({"DATABASE_URL": DB})
LOCATIONS = [f"§13({n})" for n in range(1, 15)] + ["§149(1)", "§151(1)", "§7B(1)", "ch. 6.1"]


def passage(location: str, score: float) -> RetrievedPassage:
    """A retrieved passage at this location and score."""
    return RetrievedPassage(
        id=uuid.uuid4(),
        title="Income Tax Ordinance, 2001",
        kind=DocumentKind.LAW,
        location=location,
        page=1,
        text="…",
        score=score,
    )


async def random_search(question: str) -> list[RetrievedPassage]:
    """Five random passages with plausible scores: what a broken search might return."""
    pick = random.Random(question)
    return [passage(pick.choice(LOCATIONS), pick.uniform(0.6, 0.75)) for _ in range(5)]


async def perfect_search(question: str) -> list[RetrievedPassage]:
    """The expected passage first with a high score; out-of-corpus questions score low."""
    expected = {q.question: q.expected for q in load_questions(QUESTIONS)}[question]
    if expected is None:
        return [passage("§12(1)", 0.55)]
    return [passage(expected[0], 0.8), passage("§12(1)", 0.6)]


def test_a_random_search_fails_the_run(tmp_path: Path) -> None:
    """Fails if the eval can pass when search returns unrelated passages (FR-010)."""
    report = tmp_path / "report.md"

    assert main(["--report", str(report)], NO_KEY, random_search) == 1
    assert "FAIL" in report.read_text(encoding="utf-8")


def test_a_perfect_search_passes_and_reports_the_scores(tmp_path: Path) -> None:
    """Fails if good retrieval is refused, or the report lacks what tuning the cut-off needs."""
    report = tmp_path / "report.md"

    assert main(["--report", str(report)], NO_KEY, perfect_search) == 0
    text = report.read_text(encoding="utf-8")
    assert "hit@5: 1.00" in text and "refusal rate: 1.00" in text
    assert "Is my monthly salary counted as taxable income?" in text  # per-question scores


def test_without_a_key_it_cannot_run() -> None:
    """Fails if the real run starts with no key instead of saying so (exit 2)."""
    assert main([], NO_KEY) == 2


@pytest.mark.parametrize(
    ("location", "expected", "hit"),
    [
        ("§13(3)", "§13(3)", True),
        ("§13(3)", "§13", True),
        ("ch. 14.3", "ch. 14", True),
        ("§12(2A)", "§12(2)", False),
        ("§149(1)", "§14", False),
        ("ch. 14.3", "ch. 1", False),
    ],
)
def test_an_expected_location_matches_itself_and_its_parts(
    location: str, expected: str, hit: bool
) -> None:
    """Fails if "§13" doesn't cover §13(3), or §12(2) wrongly covers §12(2A)."""
    assert matches(location, expected) is hit


def test_the_best_cutoff_separates_in_from_out_of_corpus() -> None:
    """Fails if the suggested cut-off doesn't sit between the two groups' top scores."""
    outcomes = [
        Outcome("a", ("§12",), 0.70, True),
        Outcome("b", ("§12",), 0.66, True),
        Outcome("c", None, 0.62, False),
        Outcome("d", None, 0.60, False),
    ]

    assert 0.62 < best_cutoff(outcomes) <= 0.66


def test_every_question_file_entry_is_well_formed() -> None:
    """Fails if the questions file loses its out-of-corpus share or has an empty expectation."""
    questions = load_questions(QUESTIONS)

    assert len(questions) >= 40
    assert sum(q.expected is None for q in questions) >= 10
    assert all(q.expected is None or q.expected for q in questions)


def test_a_question_the_app_refuses_before_search_is_never_searched() -> None:
    """Fails if the eval measures a path the app doesn't take: a question in Urdu script is
    refused before search (app.rag.checks.written_in_english), so it counts as refused."""

    async def no_search(question: str) -> list[RetrievedPassage]:
        raise AssertionError(f"Searched for {question!r}")

    outcomes = asyncio.run(run([Question("کیا مجھے ٹیکس دینا ہوگا؟", None)], no_search))

    assert outcomes[0].top_score == 0.0
