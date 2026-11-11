"""Run the retrieval eval (feature 006, tasks T021-T022; research R10, FR-010).

    docker compose exec backend python -m evals.retrieval.run

Asks every question in questions.yaml through the app's own search, on the built corpus, and
reports hit@5 (an in-corpus question is a hit when an expected location is among the top five
passages AND the cut-off lets it through, since otherwise the user gets a refusal) and the
refusal rate (out-of-corpus questions the cut-off refuses). It also lists each question's top
score and suggests the cut-off that best separates the two groups (task T022). Exit code 0 when
both pass marks in thresholds.yaml are met, 1 when one is missed, 2 when it can't run.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import exists, select

from app.db import get_sessionmaker
from app.rag.checks import written_in_english
from app.rag.embed import GeminiEmbedder
from app.rag.models import Passage
from app.rag.search import RetrievedPassage, search
from app.rag.settings import RELEVANCE_CUTOFF
from app.settings import Settings, get_settings

HERE = Path(__file__).parent
QUESTIONS = HERE / "questions.yaml"
THRESHOLDS = HERE / "thresholds.yaml"
REPORT = HERE / "report.md"

# The top passages for a question, nearest first, with no cut-off applied.
Searcher = Callable[[str], Awaitable[list[RetrievedPassage]]]


@dataclass(frozen=True)
class Question:
    """One eval question; `expected` is None for a question the corpus doesn't cover."""

    question: str
    expected: tuple[str, ...] | None


@dataclass(frozen=True)
class Outcome:
    """What search found for one question."""

    question: str
    expected: tuple[str, ...] | None
    top_score: float
    found: bool  # an expected location among the top passages (False when out of corpus)


@dataclass(frozen=True)
class Summary:
    """The two measures against their pass marks."""

    hit_at_5: float
    refusal_rate: float
    passed: bool


def load_questions(path: Path) -> list[Question]:
    """The questions file, with "out_of_corpus" read as no expected location."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))["questions"]
    return [
        Question(
            entry["question"],
            None if entry["expected"] == "out_of_corpus" else tuple(entry["expected"]),
        )
        for entry in entries
    ]


def matches(location: str, expected: str) -> bool:
    """True if the location is the expected one or a part of it: "§13" covers "§13(3)" and
    "ch. 14" covers "ch. 14.3", but "§12(2)" doesn't cover "§12(2A)"."""
    return location == expected or location.startswith((f"{expected}(", f"{expected}."))


async def run(questions: Sequence[Question], searcher: Searcher) -> list[Outcome]:
    """Search for every question, one at a time."""
    outcomes = []
    for question in questions:
        # Refused before search in the app (English questions only), so never searched here.
        passages = (
            await searcher(question.question) if written_in_english(question.question) else []
        )
        found = question.expected is not None and any(
            matches(p.location, e) for p in passages for e in question.expected
        )
        top = passages[0].score if passages else 0.0
        outcomes.append(Outcome(question.question, question.expected, top, found))
    return outcomes


def summarise(outcomes: Sequence[Outcome], cutoff: float, thresholds: dict[str, float]) -> Summary:
    """hit@5 and the refusal rate at this cut-off, and whether both meet their marks."""
    inside = [o for o in outcomes if o.expected is not None]
    outside = [o for o in outcomes if o.expected is None]
    hits = sum(o.found and o.top_score >= cutoff for o in inside) / max(len(inside), 1)
    refused = sum(o.top_score < cutoff for o in outside) / max(len(outside), 1)
    passed = hits >= thresholds["hit_at_5"] and refused >= thresholds["refusal_rate"]
    return Summary(hits, refused, passed)


def best_cutoff(outcomes: Sequence[Outcome]) -> float:
    """The cut-off that gets the most questions right (in-corpus let through, out-of-corpus
    refused); on a tie, the lowest, so fewer answerable questions are refused."""
    candidates = sorted({round(o.top_score, 3) for o in outcomes})

    def right(cutoff: float) -> int:
        return sum((o.top_score >= cutoff) == (o.expected is not None) for o in outcomes)

    return max(candidates, key=lambda c: (right(c), -c)) if candidates else RELEVANCE_CUTOFF


def render(outcomes: Sequence[Outcome], summary: Summary, thresholds: dict[str, float]) -> str:
    """The Markdown report."""
    lines = [
        "# Retrieval eval",
        "",
        f"Result: **{'PASS' if summary.passed else 'FAIL'}** at cut-off {RELEVANCE_CUTOFF}",
        "",
        f"- hit@5: {summary.hit_at_5:.2f} (pass mark {thresholds['hit_at_5']:.2f})",
        f"- refusal rate: {summary.refusal_rate:.2f} (pass mark {thresholds['refusal_rate']:.2f})",
        f"- suggested cut-off: {best_cutoff(outcomes):.3f}",
        "",
        "| Question | Expected | Top score | Expected passage found |",
        "|---|---|---|---|",
    ]
    for o in sorted(outcomes, key=lambda o: -o.top_score):
        expected = "out of corpus" if o.expected is None else ", ".join(o.expected)
        found = "-" if o.expected is None else ("yes" if o.found else "**no**")
        lines.append(f"| {o.question} | {expected} | {o.top_score:.3f} | {found} |")
    return "\n".join(lines) + "\n"


async def _real_run(settings: Settings, questions: Sequence[Question]) -> list[Outcome] | None:
    """The questions through the app's search on the built corpus; None if there's no corpus."""
    embedder = GeminiEmbedder(api_key=settings.gemini_api_key)
    async with get_sessionmaker()() as db:
        if not (await db.execute(select(exists().where(Passage.id.is_not(None))))).scalar_one():
            return None

        async def searcher(question: str) -> list[RetrievedPassage]:
            return (await search(db, embedder, question, cutoff=0.0)).passages

        return await run(questions, searcher)


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    searcher: Searcher | None = None,
) -> int:
    """Command line: run the eval and write the report."""
    settings = settings or get_settings()
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)

    questions = load_questions(QUESTIONS)
    thresholds = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))
    if searcher is not None:
        outcomes: list[Outcome] | None = asyncio.run(run(questions, searcher))
    elif not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set; the eval embeds each question.", file=sys.stderr)
        return 2
    else:
        outcomes = asyncio.run(_real_run(settings, questions))
    if outcomes is None:
        print("No corpus: run `python -m app.rag.build` first.", file=sys.stderr)
        return 2
    summary = summarise(outcomes, RELEVANCE_CUTOFF, thresholds)
    report = render(outcomes, summary, thresholds)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
