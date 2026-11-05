"""Run the extraction eval (feature 003, task T027; contracts/eval.md, research R6-R7).

    docker compose exec backend python -m evals.extraction.run --model claude-opus-5-5

Sends every case through the Message Batches API (half price) with the app's own prompt,
schema, normalisation and rules, scores the replies and writes report.md. The batch request is
the app's request minus the refusal fallback, which the Batches API doesn't accept. Exit code 0
when every bar is met, 1 when one is missed, 2 when it can't run.
"""

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, cast

import anthropic
from pydantic import ValidationError

from app.documents.extraction.client import MAX_TOKENS, file_block
from app.documents.extraction.prompt import SYSTEM_PROMPT, user_instruction
from app.documents.extraction.schemas import OUTPUT_SCHEMAS, ExtractedValue
from app.documents.models import DocType
from app.documents.service import build_fields, field_value
from app.settings import Settings, get_settings
from evals.extraction.generate import OUT_DIR, TAX_YEAR, load_cases
from evals.extraction.scoring import Case, Reported, render, score_case, summarise

POLL_SECONDS = 30
REPORT = Path(__file__).parent / "report.md"
MEDIA_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")


class BatchClient(Protocol):  # pylint: disable=too-few-public-methods
    """The part of anthropic.Anthropic the runner uses (tests pass a fake)."""

    @property
    def messages(self) -> Any:
        """client.messages, with .batches.create/retrieve/results."""


def request_params(case: Case, content: bytes, model: str, effort: str) -> dict[str, Any]:
    """The Messages request for one case: the app's prompt, file block and schema."""
    doc_type = DocType(case.doc_type)
    media_type = MEDIA_TYPES[case.file.rsplit(".", 1)[-1]]
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    file_block(content, media_type),
                    {"type": "text", "text": user_instruction(doc_type)},
                ],
            }
        ],
        "output_config": {
            "effort": effort,
            "format": {
                "type": "json_schema",
                "schema": anthropic.transform_schema(OUTPUT_SCHEMAS[doc_type]),
            },
        },
    }


def reported_from_reply(doc_type: str, text: str) -> Reported | None:
    """What the app would store for a reply (values and confidence after its rules), or None
    if the reply doesn't fit the schema."""
    try:
        parsed = OUTPUT_SCHEMAS[DocType(doc_type)].model_validate_json(text)
    except ValidationError:
        return None
    found = {name: value for name, value in parsed if isinstance(value, ExtractedValue)}
    fields = build_fields(DocType(doc_type), TAX_YEAR, found)
    reported: dict[str, tuple[str | None, str]] = {}
    for field in fields:
        value = field_value(field)
        reported[field.name.value] = (None if value is None else str(value), field.confidence.value)
    return reported


def run_batch(
    client: BatchClient, cases: list[Case], cases_dir: Path, model: str, effort: str
) -> tuple[dict[str, Reported | None], dict[str, int]]:
    """Send every case as one batch, wait for it, and read each case's reply."""
    requests = [
        {
            "custom_id": case.id,
            "params": request_params(case, (cases_dir / case.file).read_bytes(), model, effort),
        }
        for case in cases
    ]
    batch = client.messages.batches.create(requests=cast(Any, requests))
    print(f"Batch {batch.id}: {len(requests)} requests sent; waiting for results...")
    while batch.processing_status != "ended":
        time.sleep(POLL_SECONDS)
        batch = client.messages.batches.retrieve(batch.id)

    by_id = {case.id: case for case in cases}
    reported: dict[str, Reported | None] = {}
    tokens = {"input": 0, "output": 0}
    for item in client.messages.batches.results(batch.id):
        case = by_id[item.custom_id]
        reported[case.id] = None
        if item.result.type != "succeeded":
            continue
        message = item.result.message
        tokens["input"] += message.usage.input_tokens
        tokens["output"] += message.usage.output_tokens
        if message.stop_reason in ("refusal", "max_tokens"):
            continue
        text = "".join(block.text for block in message.content if block.type == "text")
        reported[case.id] = reported_from_reply(case.doc_type, text)
    return reported, tokens


def main(
    argv: Sequence[str] | None = None,
    settings: Settings | None = None,
    client: BatchClient | None = None,
) -> int:
    """Command line: run the eval for one model and write the report."""
    settings = settings or get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.extraction_model)
    parser.add_argument("--effort", choices=EFFORTS, default=settings.extraction_effort)
    parser.add_argument("--cases", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)

    if client is None and not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set; the eval calls the real API.", file=sys.stderr)
        return 2
    try:
        cases = load_cases(args.cases)
    except FileNotFoundError:
        print("No cases: run `python -m evals.extraction.generate` first.", file=sys.stderr)
        return 2

    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    reported, tokens = run_batch(client, cases, args.cases, args.model, args.effort)
    scores = [score for case in cases for score in score_case(case, reported.get(case.id))]
    summary = summarise(scores)
    report = render(summary, args.model, tokens)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    return 0 if summary.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
