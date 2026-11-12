"""Ask the eval questions for real and see what users would get (feature 006, task T024).

    docker compose exec backend python -m evals.answers.run

Local only, never in CI: it calls Gemini for every question that passes the cut-off, so it uses
the free quota. Each question goes through ask()'s own steps (app.rag.service.answer_question:
language, search and cut-off, Gemini, the plain-code checks) without counting against the
question limits, and the report says which step refused it, so a check failure isn't mistaken
for the model's own refusal. Exit code 0 when it ran (the report is for reading, not a gate), 2
when it can't run.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.rag.answer import GeminiAnswerer
from app.rag.embed import Embedder, GeminiEmbedder
from app.rag.service import Answerer, answer_question
from app.settings import get_settings
from evals.retrieval.run import QUESTIONS, load_questions

REPORT = Path(__file__).parent / "report.md"
# Gemini's free tier allows a few requests a minute per model.
DEFAULT_PAUSE_SECONDS = 5.0


@dataclass(frozen=True)
class Row:
    """What one question got, and from which step."""

    question: str
    expected: tuple[str, ...] | None
    outcome: str
    detail: str


async def ask_one(
    db: AsyncSession,
    embedder: Embedder,
    answerer: Answerer,
    question: str,
    expected: tuple[str, ...] | None,
) -> Row:
    """One question through ask()'s own steps (app.rag.service.answer_question), without the
    limits."""
    outcome = await answer_question(db, question, embedder, answerer)
    return Row(question, expected, outcome.step, outcome.detail)


def render(rows: Sequence[Row], model: str) -> str:
    """The Markdown report."""
    inside = [r for r in rows if r.expected is not None]
    outside = [r for r in rows if r.expected is None]
    answered = sum(r.outcome == "answered" for r in inside)
    refused = sum(r.outcome.startswith("refused") for r in outside)
    lines = [
        f"# Answers eval ({model})",
        "",
        f"- In-corpus answered: {answered} of {len(inside)}",
        f"- Out-of-corpus refused: {refused} of {len(outside)}",
        f"- Refused by the checks: {sum(r.outcome == 'refused: checks' for r in rows)}",
        f"- Unavailable: {sum(r.outcome == 'unavailable' for r in rows)}",
        "",
        "| Question | Expected | Outcome | Detail |",
        "|---|---|---|---|",
    ]
    for r in rows:
        expected = "out of corpus" if r.expected is None else ", ".join(r.expected)
        detail = r.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r.question} | {expected} | {r.outcome} | {detail} |")
    return "\n".join(lines) + "\n"


async def _run(pause: float) -> list[Row]:
    settings = get_settings()
    embedder = GeminiEmbedder(api_key=settings.gemini_api_key)
    answerer = GeminiAnswerer(
        api_key=settings.gemini_api_key, model=settings.answer_model, effort=settings.answer_effort
    )
    rows = []
    async with get_sessionmaker()() as db:
        for index, question in enumerate(load_questions(QUESTIONS)):
            if index:
                await asyncio.sleep(pause)
            rows.append(await ask_one(db, embedder, answerer, question.question, question.expected))
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    """Command line: ask every eval question and write the report."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--pause", type=float, default=DEFAULT_PAUSE_SECONDS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    settings = get_settings()
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set; this script calls the real API.", file=sys.stderr)
        return 2
    report = render(asyncio.run(_run(args.pause)), settings.answer_model)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
