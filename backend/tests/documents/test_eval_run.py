"""The eval runner, with a fake Batches API (feature 003, task T027; contracts/eval.md).

The real run needs ANTHROPIC_API_KEY and costs money (T029); this checks everything around it.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evals.extraction.generate import generate
from evals.extraction.run import main, reported_from_reply, request_params
from evals.extraction.scoring import Case

from app.documents.extraction.prompt import SYSTEM_PROMPT
from app.settings import load_settings

DB = "postgresql+asyncpg://user:pass@db:5432/example"
NO_KEY = load_settings({"DATABASE_URL": DB})
WITH_KEY = load_settings({"DATABASE_URL": DB, "ANTHROPIC_API_KEY": "test-key-not-real"})


def reply_for(case: Case) -> str:
    """A reply that copies every printed figure exactly (what a perfect model would say)."""
    fields = {
        name: {
            "value": truth,
            "confidence": "high" if truth is not None else "low",
            "page": 1 if truth is not None else None,
            "label": name if truth is not None else None,
        }
        for name, truth in case.truth.items()
    }
    return json.dumps(fields)


class FakeBatches:
    """Answers like the Batches API: every request succeeds with `answer(case_id)`."""

    def __init__(self, answer: Any) -> None:
        self.answer = answer
        self.requests: list[dict[str, Any]] = []

    def create(self, requests: list[dict[str, Any]]) -> Any:
        """Accept the batch; it is already finished."""
        self.requests = requests
        return SimpleNamespace(id="batch_test", processing_status="ended")

    def retrieve(self, batch_id: str) -> Any:
        """Not needed: create() returns an ended batch."""
        raise AssertionError(batch_id)

    def results(self, batch_id: str) -> list[Any]:
        """One succeeded result per request."""
        del batch_id
        return [
            SimpleNamespace(
                custom_id=request["custom_id"],
                result=SimpleNamespace(
                    type="succeeded",
                    message=SimpleNamespace(
                        stop_reason="end_turn",
                        usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
                        content=[
                            SimpleNamespace(type="text", text=self.answer(request["custom_id"]))
                        ],
                    ),
                ),
            )
            for request in self.requests
        ]


@pytest.fixture(scope="module")
def cases_dir(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Case]]:
    """The generated cases, once for this file."""
    out = tmp_path_factory.mktemp("cases")
    return out, {case.id: case for case in generate(out)}


def run(cases: tuple[Path, dict[str, Case]], answer: Any, tmp_path: Path) -> tuple[int, str]:
    """Run main() against a fake batch client; return the exit code and the report."""
    report = tmp_path / "report.md"
    client = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(answer)))
    code = main(
        ["--cases", str(cases[0]), "--report", str(report)], settings=WITH_KEY, client=client
    )
    return code, report.read_text(encoding="utf-8")


def test_perfect_answers_pass_and_the_report_is_written(
    cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path
) -> None:
    """Fails if a run where every figure is copied right doesn't pass, or no report is written."""
    code, report = run(cases_dir, lambda case_id: reply_for(cases_dir[1][case_id]), tmp_path)

    assert code == 0
    assert "Result: PASS" in report
    assert "80,000 input" in report


def test_garbled_answers_fail(cases_dir: tuple[Path, dict[str, Case]], tmp_path: Path) -> None:
    """Fails if replies that don't fit the schema are scored as anything but wrong."""
    code, report = run(cases_dir, lambda case_id: "not json", tmp_path)

    assert code == 1
    assert "Result: FAIL" in report


def test_request_uses_the_apps_prompt_and_schema(cases_dir: tuple[Path, dict[str, Case]]) -> None:
    """Fails if the eval drifts from what the app sends (it would measure something else)."""
    out, cases = cases_dir
    case = cases["bank-01-photo"]

    params = request_params(case, (out / case.file).read_bytes(), "claude-haiku-5-5", "low")

    assert params["system"] == SYSTEM_PROMPT
    assert params["model"] == "claude-haiku-5-5"
    assert params["output_config"]["effort"] == "low"
    assert set(params["output_config"]["format"]["schema"]["properties"]) == set(case.truth)
    assert params["messages"][0]["content"][0]["type"] == "image"
    assert "fallbacks" not in params  # the Batches API refuses it


def test_replies_are_normalised_and_rule_checked_like_the_app() -> None:
    """Fails if the eval scores raw text instead of what the app would store."""
    reply = {
        "tax_year": {"value": "Tax Year 2026", "confidence": "high", "page": 1, "label": "TY"},
        "profit_amount": {"value": "Rs. 100,000/-", "confidence": "high", "page": 1, "label": "P"},
        "tax_withheld": {"value": "200,000", "confidence": "high", "page": 1, "label": "T"},
    }

    reported = reported_from_reply("bank_profit_certificate", json.dumps(reply))

    assert reported is not None
    assert reported["tax_year"] == ("2025-26", "high")
    assert reported["profit_amount"] == ("100000.00", "low")  # withheld > profit: rule lowers it
    assert reported["tax_withheld"] == ("200000.00", "low")


def test_without_a_key_it_refuses_to_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if the eval starts without a key, or doesn't say why it can't run."""
    assert main(["--cases", str(tmp_path)], settings=NO_KEY) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_without_cases_it_says_to_generate_them(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fails if a missing case folder crashes instead of saying what to do."""
    client = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(str)))

    assert main(["--cases", str(tmp_path)], settings=WITH_KEY, client=client) == 2
    assert "generate" in capsys.readouterr().err
