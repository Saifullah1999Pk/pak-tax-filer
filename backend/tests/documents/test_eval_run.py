"""The eval runner, with a fake extractor and a fake clock (feature 003, tasks T027, T037).

The real run needs GEMINI_API_KEY and the free tier's quota (T029); this checks everything around
it: one request per case through the app's extractor, pacing, the free limit, and the report.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import json
from pathlib import Path

import pytest
from evals.extraction.generate import generate
from evals.extraction.run import main, reported_from
from evals.extraction.scoring import Case

from app.documents.extraction.client import ExtractionResult, failed
from app.documents.extraction.schemas import ExtractedValue
from app.documents.models import DocType
from app.settings import load_settings

DB = "postgresql+asyncpg://user:pass@db:5432/example"
NO_KEY = load_settings({"DATABASE_URL": DB})
WITH_KEY = load_settings({"DATABASE_URL": DB, "GEMINI_API_KEY": "test-key-not-real"})


def perfect(case: Case) -> ExtractionResult:
    """What a perfect model returns: every printed figure copied exactly."""
    fields = {
        name: ExtractedValue.model_validate(
            {
                "value": truth,
                "confidence": "high" if truth is not None else "low",
                "page": 1 if truth is not None else None,
                "label": name if truth is not None else None,
            }
        )
        for name, truth in case.truth.items()
    }
    return ExtractionResult(
        fields=fields, model="gemini-test", input_tokens=1000, output_tokens=100
    )


class ScriptedExtractor:
    """Answers each request from a script; records which files it was sent."""

    def __init__(
        self, cases: dict[str, Case], answers: list[ExtractionResult] | None = None
    ) -> None:
        self.by_file = {case.file: case for case in cases.values()}
        self.answers = list(answers or [])
        self.media_types: list[str] = []

    async def extract(self, doc_type: DocType, content: bytes, media_type: str) -> ExtractionResult:
        """The next scripted answer, or a perfect one for the case whose file this is."""
        del doc_type
        self.media_types.append(media_type)
        if self.answers:
            return self.answers.pop(0)
        case = next(c for c in self.by_file.values() if content == self.content[c.file])
        return perfect(case)

    content: dict[str, bytes] = {}


@pytest.fixture(scope="module")
def cases_dir(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Case]]:
    """The generated cases, once for this file."""
    out = tmp_path_factory.mktemp("cases")
    cases = {case.id: case for case in generate(out)}
    ScriptedExtractor.content = {
        case.file: (out / case.file).read_bytes() for case in cases.values()
    }
    return out, cases


class Clock:
    """A fake pause that records how long the runner would have waited."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def pause(self, seconds: float) -> None:
        """Record the wait instead of sleeping."""
        self.waits.append(seconds)


def run(
    cases: tuple[Path, dict[str, Case]],
    extractor: ScriptedExtractor,
    tmp_path: Path,
    clock: Clock,
    *extra: str,
) -> tuple[int, Path]:
    """Run main() with the fake extractor and clock; return the exit code and the report path."""
    report = tmp_path / "report.md"
    code = main(
        ["--cases", str(cases[0]), "--report", str(report), *extra],
        settings=WITH_KEY,
        extractor=extractor,
        pause=clock.pause,
    )
    return code, report


def test_perfect_answers_pass_one_request_per_case(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path
) -> None:
    """Fails if a perfect run doesn't pass, skips cases, or no report is written."""
    extractor = ScriptedExtractor(cases_dir[1])

    code, report = run(cases_dir, extractor, tmp_path, Clock())

    assert code == 0
    assert len(extractor.media_types) == 80
    assert set(extractor.media_types) == {"application/pdf", "image/jpeg"}
    text = report.read_text(encoding="utf-8")
    assert "Result: PASS" in text
    assert "80,000 input" in text


def test_requests_are_paced_under_the_per_minute_limit(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path
) -> None:
    """Fails if requests are sent faster than the free tier's per-minute limit allows."""
    clock = Clock()

    run(cases_dir, ScriptedExtractor(cases_dir[1]), tmp_path, clock, "--per-minute", "10")

    assert len(clock.waits) == 79  # between requests, not before the first
    assert set(clock.waits) == {6.0}


def test_failed_cases_count_as_wrong(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path
) -> None:
    """Fails if extraction failures are skipped instead of scored wrong."""
    answers = [failed("The AI declined to read this document.")] * 80

    code, report = run(cases_dir, ScriptedExtractor(cases_dir[1], answers), tmp_path, Clock())

    assert code == 1
    assert "Result: FAIL" in report.read_text(encoding="utf-8")


def test_a_free_limit_hit_waits_a_minute_and_retries(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path
) -> None:
    """Fails if one 429 ends the run instead of pausing and trying again."""
    limit = failed("The free AI limit may be used up for now.", limit_reached=True)
    clock = Clock()

    code, _ = run(cases_dir, ScriptedExtractor(cases_dir[1], [limit]), tmp_path, clock)

    assert code == 0
    assert 60.0 in clock.waits


def test_the_daily_limit_stops_the_run_cleanly(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a used-up daily quota crashes, loops, or writes a half report as a result."""
    limit = failed("The free AI limit may be used up for now.", limit_reached=True)

    code, report = run(
        cases_dir, ScriptedExtractor(cases_dir[1], [limit, limit]), tmp_path, Clock()
    )

    assert code == 2
    assert not report.exists()
    assert "0 of 80" in capsys.readouterr().err


def test_results_are_normalised_and_rule_checked_like_the_app() -> None:
    """Fails if the eval scores raw text instead of what the app would store."""
    found = {
        "tax_year": {"value": "Tax Year 2026", "confidence": "high", "page": 1, "label": "TY"},
        "profit_amount": {"value": "Rs. 100,000/-", "confidence": "high", "page": 1, "label": "P"},
        "tax_withheld": {"value": "200,000", "confidence": "high", "page": 1, "label": "T"},
    }
    result = ExtractionResult(
        fields={name: ExtractedValue.model_validate(v) for name, v in found.items()}
    )

    reported = reported_from("bank_profit_certificate", result)

    assert reported is not None
    assert reported["tax_year"] == ("2025-26", "high")
    assert reported["profit_amount"] == ("100000.00", "low")  # withheld > profit: rule lowers it
    assert reported["tax_withheld"] == ("200000.00", "low")


def test_a_failed_result_reports_nothing() -> None:
    """Fails if a failure is turned into empty figures instead of "no answer"."""
    assert reported_from("salary_certificate", failed("busy")) is None


def test_without_a_key_it_refuses_to_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if the eval starts without a key, or doesn't say why it can't run."""
    assert main(["--cases", str(tmp_path)], settings=NO_KEY) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_without_cases_it_says_to_generate_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a missing case folder crashes instead of saying what to do."""
    extractor = ScriptedExtractor({})

    assert main(["--cases", str(tmp_path)], settings=WITH_KEY, extractor=extractor) == 2
    assert "generate" in capsys.readouterr().err


def test_requests_carry_the_cases_real_bytes(cases_dir: tuple[Path, dict[str, Case]]) -> None:
    """Fails if the fixture's content map is wrong (it would make the other tests meaningless)."""
    out, cases = cases_dir
    case = cases["bank-01-photo"]

    assert ScriptedExtractor.content[case.file] == (out / case.file).read_bytes()
    assert json.dumps(case.truth)
