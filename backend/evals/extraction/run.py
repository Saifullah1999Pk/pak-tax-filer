"""Run the extraction eval (feature 003, tasks T027 and T037; contracts/eval.md, research R6-R7).

    docker compose exec backend python -m evals.extraction.run --model gemini-3.8-flash

Sends every case through the app's own extractor (the same prompt, schema, normalisation and
rules), one request at a time: Gemini's free tier has no Batch API. Requests are paced under the
per-minute limit; a free-limit error waits a minute and retries once, and if the limit is still
reached the run stops and says how far it got. Exit code 0 when every bar is met, 1 when one is
missed, 2 when it can't run or finish.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from app.documents.extraction.client import ExtractionResult, Extractor, GeminiExtractor
from app.documents.models import DocType
from app.documents.service import build_fields, field_value
from app.settings import Settings, get_settings
from evals.extraction.generate import OUT_DIR, TAX_YEAR, load_cases
from evals.extraction.scoring import Case, Reported, render, score_case, summarise

REPORT = Path(__file__).parent / "report.md"
MEDIA_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
EFFORTS = ("minimal", "low", "medium", "high")
# Conservative default; raise it to the project's limit shown in AI Studio.
DEFAULT_PER_MINUTE = 5
LIMIT_RETRY_SECONDS = 60.0

Pause = Callable[[float], Awaitable[None]]


class LimitReached(Exception):
    """The free tier's limit was still reached after waiting; the run can't finish today."""

    def __init__(self, done: int) -> None:
        super().__init__(done)
        self.done = done


def reported_from(doc_type: str, result: ExtractionResult) -> Reported | None:
    """What the app would store for a result (values and confidence after its rules), or None
    if extraction failed."""
    if result.failure_reason is not None:
        return None
    fields = build_fields(DocType(doc_type), TAX_YEAR, result.fields)
    reported: dict[str, tuple[str | None, str]] = {}
    for field in fields:
        value = field_value(field)
        reported[field.name.value] = (None if value is None else str(value), field.confidence.value)
    return reported


async def run_cases(
    extractor: Extractor, cases: list[Case], cases_dir: Path, per_minute: int, pause: Pause
) -> tuple[dict[str, Reported | None], dict[str, int]]:
    """Each case's result and the tokens used; raises LimitReached if the quota runs out."""
    reported: dict[str, Reported | None] = {}
    tokens = {"input": 0, "output": 0}
    for index, case in enumerate(cases):
        if index:
            await pause(60 / per_minute)
        content = (cases_dir / case.file).read_bytes()
        media_type = MEDIA_TYPES[case.file.rsplit(".", 1)[-1]]
        result = await extractor.extract(DocType(case.doc_type), content, media_type)
        if result.limit_reached:
            await pause(LIMIT_RETRY_SECONDS)
            result = await extractor.extract(DocType(case.doc_type), content, media_type)
            if result.limit_reached:
                raise LimitReached(done=index)
        tokens["input"] += result.input_tokens
        tokens["output"] += result.output_tokens
        reported[case.id] = reported_from(case.doc_type, result)
    return reported, tokens


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    extractor: Extractor | None = None,
    pause: Pause = asyncio.sleep,
) -> int:
    """Command line: run the eval for one model and write the report."""
    settings = settings or get_settings()
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--model", default=settings.extraction_model)
    parser.add_argument("--effort", choices=EFFORTS, default=settings.extraction_effort)
    parser.add_argument("--per-minute", type=int, default=DEFAULT_PER_MINUTE)
    parser.add_argument("--cases", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)

    if extractor is None and not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set; the eval calls the real API.", file=sys.stderr)
        return 2
    try:
        cases = load_cases(args.cases)
    except FileNotFoundError:
        print("No cases: run `python -m evals.extraction.generate` first.", file=sys.stderr)
        return 2

    extractor = extractor or GeminiExtractor(
        api_key=settings.gemini_api_key, model=args.model, effort=args.effort
    )
    try:
        reported, tokens = asyncio.run(
            run_cases(extractor, cases, args.cases, args.per_minute, pause)
        )
    except LimitReached as stopped:
        print(
            f"The free limit was reached after {stopped.done} of {len(cases)} cases. Run again "
            "after the quota resets (midnight Pacific time).",
            file=sys.stderr,
        )
        return 2
    scores = [score for case in cases for score in score_case(case, reported.get(case.id))]
    summary = summarise(scores)
    report = render(summary, args.model, tokens)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
