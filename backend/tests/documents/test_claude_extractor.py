"""The real Claude client, tested through the SDK with a fake network (task T008, research R1/R8).

No API key or credits: httpx2's MockTransport answers in place of the API, so these tests check
the exact request we send and how every kind of reply or failure is handled.
"""

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic

from app.documents.extraction.client import FALLBACK_BETA, ClaudeExtractor
from app.documents.extraction.prompt import SYSTEM_PROMPT
from app.documents.models import DocType, FieldName

pytestmark = pytest.mark.anyio

PDF = b"%PDF-1.7 synthetic"
PNG = b"\x89PNG\r\n\x1a\n synthetic"
FAKE_KEY = "test-key-not-real"

BANK_REPLY = {
    "tax_year": {"value": "2025-26", "confidence": "high", "page": 1, "label": "Tax Year"},
    "profit_amount": {"value": "Rs. 120,000", "confidence": "high", "page": 1, "label": "Profit"},
    "tax_withheld": {"value": None, "confidence": "low", "page": None, "label": None},
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def message(text: str = "", stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> Any:
    """A Messages API reply body."""
    content = [{"type": "text", "text": text}] if text else []
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def extractor(handler: Handler, api_key: str | None = FAKE_KEY) -> ClaudeExtractor:
    """A ClaudeExtractor whose SDK client talks to `handler` instead of the network."""
    client = AsyncAnthropic(
        api_key=FAKE_KEY,
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeExtractor(api_key=api_key, model="claude-opus-5-5", effort="low", client=client)


def replying(body: Any, status: int = 200, sent: list[httpx2.Request] | None = None) -> Handler:
    """A handler that records each request and answers with `body`."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        if sent is not None:
            sent.append(request)
        return httpx2.Response(status, json=body)

    return handle


async def test_pdf_request_has_the_document_schema_effort_and_fallback() -> None:
    """Fails if the request drifts from research R1 (PDF block, schema, effort, fallback)."""
    sent: list[httpx2.Request] = []
    claude = extractor(replying(message(json.dumps(BANK_REPLY)), sent=sent))

    await claude.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert len(sent) == 1
    request = sent[0]
    body = json.loads(request.content)
    document, instruction = body["messages"][0]["content"]
    assert document["type"] == "document"
    assert document["source"] == {
        "type": "base64",
        "media_type": "application/pdf",
        "data": base64.standard_b64encode(PDF).decode(),
    }
    assert "profit certificate" in instruction["text"]
    assert body["model"] == "claude-opus-5-5"
    assert body["system"] == SYSTEM_PROMPT
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert set(body["output_config"]["format"]["schema"]["properties"]) == set(BANK_REPLY)
    assert body["fallbacks"] == "default"
    assert FALLBACK_BETA in request.headers["anthropic-beta"]


async def test_image_is_sent_as_an_image_block() -> None:
    """Fails if a photo is sent as a document (the API needs an image block)."""
    sent: list[httpx2.Request] = []
    salary = {name.value: BANK_REPLY["tax_year"] for name in list(FieldName)[:4]}
    claude = extractor(replying(message(json.dumps(salary)), sent=sent))

    await claude.extract(DocType.SALARY_CERTIFICATE, PNG, "image/png")

    image = json.loads(sent[0].content)["messages"][0]["content"][0]
    assert image["type"] == "image"
    assert image["source"]["media_type"] == "image/png"


async def test_reply_becomes_fields_and_records_the_model_that_answered() -> None:
    """Fails if values, not-found fields or the serving model (e.g. a fallback) are lost."""
    reply = message(json.dumps(BANK_REPLY), model="claude-opus-4-8")
    claude = extractor(replying(reply))

    result = await claude.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is None
    assert result.model == "claude-opus-4-8"
    assert result.fields["profit_amount"].value == "Rs. 120,000"
    assert result.fields["profit_amount"].label == "Profit"
    assert result.fields["tax_withheld"].value is None


async def test_without_an_api_key_nothing_is_sent() -> None:
    """Fails if a missing key makes a request, or fails without saying why."""
    sent: list[httpx2.Request] = []
    claude = extractor(replying(message(), sent=sent), api_key=None)

    result = await claude.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert not sent
    assert result.failure_reason is not None
    assert "key" in result.failure_reason
    assert not result.fields


@pytest.mark.parametrize(
    ("stop_reason", "expected"), [("refusal", "declined"), ("max_tokens", "incomplete")]
)
async def test_refusal_or_cut_off_reply_fails_cleanly(stop_reason: str, expected: str) -> None:
    """Fails if a refused or truncated answer is treated as figures (R1)."""
    claude = extractor(replying(message(stop_reason=stop_reason)))

    result = await claude.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
    assert not result.fields


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, "busy"), (500, "problem"), (529, "problem"), (401, "key"), (400, "couldn't read")],
)
async def test_api_errors_become_short_reasons(status: int, expected: str) -> None:
    """Fails if an API error escapes, or its reason is unclear (typed exceptions, R1)."""
    error = {"type": "error", "error": {"type": "x", "message": "secret details"}}
    claude = extractor(replying(error, status=status))

    result = await claude.extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
    assert "secret details" not in result.failure_reason


@pytest.mark.parametrize(
    ("network_error", "expected"),
    [(httpx2.ReadTimeout("slow"), "too long"), (httpx2.ConnectError("down"), "reach")],
)
async def test_network_failures_become_short_reasons(
    network_error: Exception, expected: str
) -> None:
    """Fails if a timeout or lost connection escapes instead of failing the document."""

    def fail(_request: httpx2.Request) -> httpx2.Response:
        raise network_error

    result = await extractor(fail).extract(DocType.BANK_PROFIT_CERTIFICATE, PDF, "application/pdf")

    assert result.failure_reason is not None
    assert expected in result.failure_reason
