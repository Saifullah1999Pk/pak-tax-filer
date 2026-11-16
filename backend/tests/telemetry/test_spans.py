"""What telemetry records (feature 008, task T017; research R1-R3, FR-010, FR-011, FR-013).

Requests are named by their route template; every AI use (all eight features) records Gemini's
provider, the operation, the model and how it ended; the real clients add token counts. Tests use
the fake AI clients, as everywhere else.
"""

# pytest fixtures receive other fixtures by name.
# pylint: disable=redefined-outer-name

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from document_helpers import PROFILE_YEAR, add_confirmed_document, make_pdf, upload
from httpx2 import AsyncClient
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.trace import StatusCode
from rag_helpers import QUESTION, a_corpus, a_user, reply
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from telemetry_helpers import Spans

from app.auth.models import User
from app.documents.extraction.client import FakeExtractor
from app.documents.models import DocType
from app.rag.answer import AnswerError, FakeAnswerer, GeminiAnswerer
from app.rag.embed import FakeEmbedder
from app.rag.models import AskRequest
from app.rag.service import ask
from app.settings import get_settings
from app.telemetry.setup import _Filtered, _provider, exporter_for

pytestmark = pytest.mark.anyio

SALARY = {"gross_salary": "2000000", "taxable_salary": "1800000", "tax_deducted": "75000"}
FEATURES = {
    "extraction",
    "assistant",
    "embeddings",
}


def attributes(span: ReadableSpan) -> dict[str, Any]:
    """A span's attributes as a plain dict."""
    return dict(span.attributes or {})


def outcomes(spans: Spans, feature: str) -> list[str]:
    """How each of this feature's AI uses ended, in order."""
    return [attributes(span)["app.outcome"] for span in spans.ai(feature)]


# ---- Requests ----


async def test_a_request_span_is_named_by_its_route_template(
    client: AsyncClient, user_with_profile: User, spans: Spans
) -> None:
    """Fails if a request span is missing, or named by the raw path (which can hold ids)."""
    assert user_with_profile

    await client.get(f"/api/tax/{PROFILE_YEAR}")

    names = [span.name for span in spans.all()]
    assert "GET /api/tax/{tax_year}" in names
    assert not any(PROFILE_YEAR in name for name in names)
    server = next(s for s in spans.all() if s.name == "GET /api/tax/{tax_year}")
    assert attributes(server)["http.route"] == "/api/tax/{tax_year}"
    assert attributes(server)["http.response.status_code"] == 200


# ---- AI uses: every feature, every outcome ----


async def test_every_ai_span_names_gemini_the_operation_the_model_and_the_outcome(
    client: AsyncClient, db: AsyncSession, user_with_profile: User, spans: Spans
) -> None:
    """Fails if any of the three AI uses records no span, or a span lacks the GenAI attributes
    (extraction, the assistant and its embeddings: the only AI left, 2026-11-16)."""
    settings = get_settings()
    await a_corpus(db)
    await upload(client, make_pdf())  # extraction (the default fake fails: a fallback)
    await add_confirmed_document(db, user_with_profile.id, DocType.SALARY_CERTIFICATE, SALARY)
    await client.post("/api/ask", json={"question": QUESTION})

    assert {attributes(span)["app.feature"] for span in spans.ai()} == FEATURES
    models = {
        "extraction": settings.extraction_model,
        "assistant": settings.answer_model,
        "embeddings": "gemini-embedding-001",
    }
    for span in spans.ai():
        values = attributes(span)
        feature = values["app.feature"]
        assert values["gen_ai.provider.name"] == "gcp.gemini", feature
        assert values["gen_ai.request.model"] == models[feature]
        assert values["gen_ai.operation.name"] in {"generate_content", "embeddings"}, feature
        assert (values["gen_ai.operation.name"] == "embeddings") == (feature == "embeddings")
        assert values["app.outcome"] in {"passed", "check_failed", "timeout", "fallback"}
    assert outcomes(spans, "extraction") == ["fallback"]


async def test_each_outcome_is_recorded(db: AsyncSession, spans: Spans) -> None:
    """Fails if an assistant answer that errors, fails its check, or comes past the limit isn't
    recorded as such."""
    await a_corpus(db)
    user = await a_user(db)
    await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(AnswerError("down")))
    await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(reply(citations=["P9"])))
    now = datetime.now(UTC)
    db.add_all(
        AskRequest(user_id=user.id, created_at=now - timedelta(minutes=i)) for i in range(30)
    )
    await db.flush()
    await ask(db, user.id, QUESTION, FakeEmbedder(), FakeAnswerer(reply()))

    assert outcomes(spans, "assistant") == ["fallback", "check_failed", "limit_reached"]


async def test_a_passed_extraction_is_recorded(
    client: AsyncClient, user_with_profile: User, fake_extractor: FakeExtractor, spans: Spans
) -> None:
    """Fails if a successful extraction isn't recorded as passed."""
    assert user_with_profile and fake_extractor

    await upload(client, make_pdf())

    assert outcomes(spans, "extraction") == ["passed"]


async def test_the_real_client_adds_its_token_counts(db: AsyncSession, spans: Spans) -> None:
    """Fails if a Gemini reply's token counts aren't on the AI span (the assistant's real client,
    through the SDK, with a mock transport in place of Google)."""
    answer = {
        "answer": "Your employer deducts tax from your salary.",
        "citations": ["P1"],
        "not_covered": False,
        "uncovered_part": None,
        "asks_own_tax_figure": False,
    }

    def handle(request: httpx2.Request) -> httpx2.Response:
        del request
        return httpx2.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": json.dumps(answer)}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 9,
                    "thoughtsTokenCount": 30,
                },
            },
        )

    answerer = GeminiAnswerer(
        api_key="test-key-not-real",
        model="gemini-test-model",
        effort="minimal",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handle)),
    )
    await a_corpus(db)

    await ask(db, (await a_user(db)).id, QUESTION, FakeEmbedder(), answerer)

    (span,) = spans.ai("assistant")
    assert attributes(span)["gen_ai.usage.input_tokens"] == 120
    assert attributes(span)["gen_ai.usage.output_tokens"] == 39  # the reply and its thinking


# ---- The exporter setting ----


def test_the_default_exporter_is_the_console_and_none_records_nothing() -> None:
    """Fails if spans go anywhere but the logs by default, or "none" still exports (FR-013)."""
    assert isinstance(exporter_for("console"), ConsoleSpanExporter)
    assert exporter_for("none") is None


def test_every_exporter_gets_only_filtered_spans() -> None:
    """Fails if any exporter (the logs' included) is added without the attribute filter, which
    would let full URLs, addresses or SQL reach the logs (FR-012)."""
    # pylint: disable=protected-access  # the provider's processors aren't public
    processors = _provider()._active_span_processor._span_processors
    assert processors
    assert all(isinstance(processor, _Filtered) for processor in processors)


def test_importing_the_app_needs_no_database_url() -> None:
    """Fails if telemetry's setup makes importing the app need DATABASE_URL (it reads only
    OTEL_EXPORTER), which would break test collection outside Docker."""
    environ = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    environ["OTEL_EXPORTER"] = "none"
    done = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        env=environ,
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr.decode()[-500:]


async def test_a_failed_statement_ends_its_span_as_an_error(db: AsyncSession, spans: Spans) -> None:
    """Fails if a statement that errors leaves no span, or one marked as a success, or one
    holding the statement or the error's text."""
    with pytest.raises(DBAPIError):
        await db.execute(text("SELECT 1 / 0"))

    (failed,) = [s for s in spans.all() if s.status.status_code is StatusCode.ERROR]
    assert failed.name == "SELECT"
    assert dict(failed.attributes or {}) == {"db.system.name": "postgresql"}
    assert failed.status.description is None
