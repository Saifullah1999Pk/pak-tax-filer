"""Gemini embeddings through the real SDK, with an httpx2 MockTransport in place of Google
(feature 006, task T006; research R3 amended). No key or quota is used."""

import json
import math
from collections.abc import Callable

import httpx2
import pytest

from app.rag.embed import EmbeddingError, FakeEmbedder, GeminiEmbedder
from app.rag.models import EMBEDDING_DIMENSIONS

pytestmark = pytest.mark.anyio

FAKE_KEY = "test-key-not-real"
Handler = Callable[[httpx2.Request], httpx2.Response]


def embedder(
    handler: Handler, *, api_key: str | None = FAKE_KEY, **kwargs: object
) -> tuple[GeminiEmbedder, list[float]]:
    """A GeminiEmbedder whose HTTP calls go to `handler`, and the pauses it took."""
    pauses: list[float] = []

    async def pause(seconds: float) -> None:
        pauses.append(seconds)

    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return (
        GeminiEmbedder(api_key=api_key, http_client=http, sleep=pause, **kwargs),  # type: ignore[arg-type]
        pauses,
    )


def requests_in(request: httpx2.Request) -> list[dict[str, object]]:
    """The embedding requests in one HTTP call (batched or single)."""
    body = json.loads(request.content)
    return body["requests"] if "requests" in body else [body]


def vectors_for(request: httpx2.Request, size: int = EMBEDDING_DIMENSIONS) -> httpx2.Response:
    """A reply with one vector per requested text: [index, 0, 0, ...]."""
    count = len(requests_in(request))
    embeddings = [{"values": [float(i + 1)] + [0.0] * (size - 1)} for i in range(count)]
    return httpx2.Response(200, json={"embeddings": embeddings})


async def test_passages_are_embedded_in_batches_as_documents() -> None:
    """Fails if passages aren't sent as retrieval documents at 768 dimensions, or the vectors
    come back out of order."""
    seen: list[list[dict[str, object]]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.append(requests_in(request))
        return vectors_for(request)

    gemini, _ = embedder(handle, batch_size=2)
    vectors = await gemini.embed_documents(["a", "b", "c"])

    assert [len(batch) for batch in seen] == [2, 1]
    first = seen[0][0]
    assert first["taskType"] == "RETRIEVAL_DOCUMENT"
    assert first["outputDimensionality"] == EMBEDDING_DIMENSIONS
    assert [v[0] for v in vectors] == [1.0, 2.0, 1.0]
    assert all(len(v) == EMBEDDING_DIMENSIONS for v in vectors)


async def test_a_question_is_embedded_as_a_query() -> None:
    """Fails if a question is embedded as a document (Gemini tunes the two differently)."""
    seen: list[dict[str, object]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.extend(requests_in(request))
        return vectors_for(request)

    gemini, _ = embedder(handle)
    vector = await gemini.embed_query("What tax is deducted from my salary?")

    assert seen[0]["taskType"] == "RETRIEVAL_QUERY"
    assert len(vector) == EMBEDDING_DIMENSIONS


async def test_too_many_requests_is_retried_after_a_pause() -> None:
    """Fails if a free-tier "429 too many requests" ends the build instead of waiting a bit."""
    calls = 0

    def handle(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx2.Response(429, json={"error": {"code": 429, "message": "Slow down."}})
        return vectors_for(request)

    gemini, pauses = embedder(handle)
    vectors = await gemini.embed_documents(["a"])

    assert calls == 2
    assert pauses and pauses[0] > 0
    assert len(vectors) == 1


async def test_lasting_failure_raises_instead_of_returning_part_of_the_corpus() -> None:
    """Fails if a build could go on with some passages missing (the build is all-or-nothing)."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        del request
        return httpx2.Response(503, json={"error": {"code": 503, "message": "Unavailable."}})

    gemini, _ = embedder(handle, attempts=3)
    with pytest.raises(EmbeddingError):
        await gemini.embed_documents(["a", "b"])


async def test_without_a_key_nothing_is_sent() -> None:
    """Fails if a missing key sends a request rather than failing clearly."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError(f"No request expected, got {request.url}")

    gemini, _ = embedder(handle, api_key=None)
    with pytest.raises(EmbeddingError):
        await gemini.embed_query("Anything?")


async def test_a_vector_of_the_wrong_size_is_refused() -> None:
    """Fails if a vector that doesn't fit the database column (768) gets through."""

    def handle(request: httpx2.Request) -> httpx2.Response:
        return vectors_for(request, size=3072)

    gemini, _ = embedder(handle)
    with pytest.raises(EmbeddingError):
        await gemini.embed_query("Anything?")


def cosine(a: list[float], b: list[float]) -> float:
    """How alike two vectors are: 1 the same direction, 0 unrelated."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


async def test_the_fake_embedder_is_repeatable_and_puts_similar_words_close() -> None:
    """Fails if tests can't rely on the fake: same text, same vector; shared words, closer."""
    fake = FakeEmbedder()
    salary = await fake.embed_query("tax deducted from salary")

    assert salary == await fake.embed_query("tax deducted from salary")
    assert len(salary) == EMBEDDING_DIMENSIONS
    near, far = await fake.embed_documents(["salary tax deducted by employer", "rental income"])
    assert cosine(salary, near) > cosine(salary, far)
