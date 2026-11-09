"""GeminiSummariser through the real SDK, with an httpx2 MockTransport in place of Google
(feature 004 review; same approach as 003's test_gemini_extractor.py). No key or quota needed."""

import json
import logging
from collections.abc import Callable

import httpx2
import pytest

from app.tax.summary import INSTRUCTIONS, GeminiSummariser

pytestmark = pytest.mark.anyio

FAKE_KEY = "test-key-not-real"
Handler = Callable[[httpx2.Request], httpx2.Response]


def summariser(handler: Handler, api_key: str | None = FAKE_KEY) -> GeminiSummariser:
    """A GeminiSummariser whose HTTP calls go to `handler`."""
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return GeminiSummariser(
        api_key=api_key, model="gemini-test-model", effort="low", http_client=http
    )


def reply(text: str) -> httpx2.Response:
    """A generateContent reply with one text part."""
    return httpx2.Response(
        200,
        json={
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
            ]
        },
    )


async def test_without_a_key_nothing_is_sent() -> None:
    """Fails if a missing key causes a request or an error instead of no summary."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError(f"No request expected, got {request.url}")

    assert await summariser(handle, api_key=None).write("Tax year 2025-26.") is None


async def test_the_model_instructions_and_breakdown_are_sent() -> None:
    """Fails if the configured model, the instructions or the breakdown aren't what's sent."""
    sent: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return reply("Your salary tax is Rs 72,000.")

    text = await summariser(handle).write("Tax year 2025-26.\n- Salary tax: = Rs 72,000")

    assert text == "Your salary tax is Rs 72,000."
    assert "gemini-test-model" in str(sent[0].url)
    body = json.loads(sent[0].content)
    assert body["systemInstruction"]["parts"][0]["text"] == INSTRUCTIONS
    assert "Rs 72,000" in body["contents"][0]["parts"][0]["text"]


async def test_an_api_error_is_no_summary_and_logs_only_its_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fails if a Google error breaks the result, is retried, or its message is logged."""
    calls: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(500, json={"error": {"code": 500, "message": "secret detail"}})

    with caplog.at_level(logging.WARNING):
        assert await summariser(handle).write("Tax year 2025-26.") is None

    assert len(calls) == 1
    assert "secret detail" not in caplog.text
    assert "ServerError" in caplog.text
