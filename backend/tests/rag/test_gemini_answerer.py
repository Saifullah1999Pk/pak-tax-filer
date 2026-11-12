"""GeminiAnswerer through the real SDK, with an httpx2 MockTransport in place of Google (feature
006, task T011; same approach as 004's test_gemini_summariser.py). No key or quota needed."""

import json
import uuid
from collections.abc import Callable

import httpx2
import pytest

from app.rag.answer import INSTRUCTIONS, AnswerError, GeminiAnswerer, ModelAnswer
from app.rag.models import DocumentKind
from app.rag.search import RetrievedPassage

pytestmark = pytest.mark.anyio

FAKE_KEY = "test-key-not-real"
Handler = Callable[[httpx2.Request], httpx2.Response]
QUESTION = "Does my bank deduct tax on my profit?"
PASSAGES = [
    RetrievedPassage(
        id=uuid.uuid4(),
        title="Income Tax Ordinance, 2001",
        kind=DocumentKind.LAW,
        location="§151(1)",
        page=329,
        text="A bank paying profit on debt shall deduct tax from the profit paid.",
        score=0.71,
    )
]
GOOD = {
    "answer": "Yes: a bank paying profit deducts tax from it.",
    "citations": ["P1"],
    "not_covered": False,
    "uncovered_part": None,
    "asks_own_tax_figure": False,
}


def answerer(handler: Handler, api_key: str | None = FAKE_KEY) -> GeminiAnswerer:
    """A GeminiAnswerer whose HTTP calls go to `handler`."""
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return GeminiAnswerer(
        api_key=api_key, model="gemini-test-model", effort="minimal", http_client=http
    )


def reply(body: object, finish: str = "STOP") -> httpx2.Response:
    """A generateContent reply whose one text part is `body` as JSON (or as given, if a str)."""
    text = body if isinstance(body, str) else json.dumps(body)
    return httpx2.Response(
        200,
        json={
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": finish}
            ]
        },
    )


def busy() -> httpx2.Response:
    """Gemini's "high demand" reply (seen on 2 of 10 real questions, 2026-11-11)."""
    return httpx2.Response(
        503, json={"error": {"code": 503, "message": "High demand.", "status": "UNAVAILABLE"}}
    )


async def test_the_question_passages_and_instructions_are_sent() -> None:
    """Fails if the labelled passages, the question, the model or the instructions aren't sent,
    or the structured reply isn't read back."""
    sent: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return reply(GOOD)

    answer = await answerer(handle).answer(QUESTION, PASSAGES)

    assert answer == ModelAnswer(**GOOD)  # type: ignore[arg-type]
    assert "gemini-test-model" in str(sent[0].url)
    body = sent[0].content.decode()
    assert (
        "[P1] Income Tax Ordinance, 2001, §151(1) (law, page 329)"
        in json.loads(body)["contents"][0]["parts"][0]["text"]
    )
    assert QUESTION in body
    assert json.dumps(INSTRUCTIONS)[1:40] in body


@pytest.mark.parametrize(
    "response",
    [
        reply(GOOD, finish="MAX_TOKENS"),
        reply(GOOD, finish="SAFETY"),
        reply("not json"),
        reply({"answer": "Missing fields."}),
        httpx2.Response(400, json={"error": {"code": 400, "message": "Bad request."}}),
    ],
    ids=["cut-short", "blocked", "not-json", "wrong-shape", "client-error"],
)
async def test_an_unusable_reply_is_an_answer_error(response: httpx2.Response) -> None:
    """Fails if a partial, blocked, malformed or refused reply could be used."""
    with pytest.raises(AnswerError):
        await answerer(lambda request: response).answer(QUESTION, PASSAGES)


async def test_without_a_key_nothing_is_sent() -> None:
    """Fails if a missing key causes a request instead of an AnswerError."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError(f"No request expected, got {request.url}")

    with pytest.raises(AnswerError):
        await answerer(handle, api_key=None).answer(QUESTION, PASSAGES)


async def test_one_busy_reply_is_retried() -> None:
    """Fails if a single 503 "high demand" (common on the free tier, and quick) isn't tried
    once more before the user is told to try again later."""
    replies = [busy(), reply(GOOD)]

    def handle(request: httpx2.Request) -> httpx2.Response:
        del request
        return replies.pop(0)

    assert (await answerer(handle).answer(QUESTION, PASSAGES)).citations == ["P1"]


async def test_two_busy_replies_are_an_answer_error() -> None:
    """Fails if retries go on past the second attempt (the answer has 15 seconds in all)."""
    calls: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return busy()

    with pytest.raises(AnswerError):
        await answerer(handle).answer(QUESTION, PASSAGES)
    assert len(calls) == 2
